"""Financial analysis over the shared loan application records."""

from __future__ import annotations

import html
import csv
import io
import textwrap
import unicodedata
from datetime import date, datetime
from collections import defaultdict
from typing import Any, Mapping, Sequence
from uuid import uuid4

import streamlit as st

from data.loan_applications_demo import create_loan_application_demo_data
from modules.credit_assessment import eligible_applications


APPLICATIONS_KEY = "loan_application_records"
ASSESSMENT_STATUSES = ("Not Started", "In Progress", "Awaiting Information", "Completed")
BORROWER_TYPES = ("All", "Personal", "Business", "Not specified")
INCOME_FREQUENCIES = ("Monthly", "Weekly", "Biweekly", "Annual")
VERIFICATION_STATES = ("Unverified", "Needs Review", "Verified")
BUSINESS_EXPENSE_CATEGORIES = (
    "Employee salaries",
    "Rent",
    "Utilities",
    "Inventory or raw materials",
    "Transportation",
    "Operating and administrative expenses",
    "Taxes",
    "Other business expenses",
)
PERSONAL_EXPENSE_CATEGORIES = (
    "Housing / Rent",
    "Food",
    "Transportation",
    "Education",
    "Healthcare",
    "Utilities",
    "Other Expenses",
)
PERSONAL_DEBT_TYPES = ("Existing Loans", "Credit Card Obligations", "Other Debt Commitments")
BUSINESS_DEBT_TYPES = ("Existing Business Loans", "Lease Obligations", "Other Business Debt Commitments")
BUSINESS_OBLIGATION_EXPENSE_CATEGORIES = (
    "Employee Salaries",
    "Rent",
    "Utilities",
    "Inventory / Raw Materials",
    "Transportation",
    "Administrative Expenses",
    "Taxes",
    "Other Operating Expenses",
)
_PART_TWO_BUSINESS_CATEGORY_MAP = {
    "Employee salaries": "Employee Salaries",
    "Inventory or raw materials": "Inventory / Raw Materials",
    "Operating and administrative expenses": "Administrative Expenses",
    "Other business expenses": "Other Operating Expenses",
}
OBLIGATION_ENTRY_SOURCES = ("Applicant-declared", "Staff adjustment")
OBLIGATION_COLLECTIONS = {
    "Personal": ("personal_living_expenses", "personal_debts", PERSONAL_EXPENSE_CATEGORIES, PERSONAL_DEBT_TYPES),
    "Business": ("business_operating_expenses", "business_debts", BUSINESS_OBLIGATION_EXPENSE_CATEGORIES, BUSINESS_DEBT_TYPES),
}

_GENERIC_FINANCIAL_FIELDS = (
    ("Monthly income", "monthly_income"),
    ("Monthly expenses", "monthly_expenses"),
    ("Existing debt field", "existing_debt"),
    ("Other obligations", "other_obligations"),
    ("Available monthly income", "available_monthly_income"),
)

_PERSONAL_OVERVIEW_FIELDS = (
    ("Income amount as recorded", "monthly_income", "Monthly field; gross/net type not specified"),
    ("Gross monthly income", "gross_monthly_income", "Not collected in current records"),
    ("Net monthly income", "net_monthly_income", "Not collected in current records"),
    ("Monthly living expenses", "monthly_expenses", "Applicant-entered total; no category breakdown"),
    ("Existing monthly debt payments", "monthly_debt_payments", "Not collected in current records"),
    ("Proposed installment", "estimated_monthly_installment", "Unavailable unless explicitly stored"),
    ("Disposable income", "disposable_income", "Not calculated in Part 1"),
)

_BUSINESS_OVERVIEW_FIELDS = (
    ("Business name", "business_name", "Not collected in current records"),
    ("Monthly business revenue", "monthly_business_revenue", "Not normalized from unspecified periods"),
    ("Operating expenses", "monthly_operating_expenses", "Business expense breakdown unavailable"),
    ("Cash flow available for debt service", "cash_flow_available_for_debt_service", "Not calculated in Part 1"),
    ("Existing business debt service", "existing_business_debt_service", "Not collected in current records"),
    ("Proposed installment", "estimated_monthly_installment", "Unavailable unless explicitly stored"),
    ("Cash flow after debt service", "cash_flow_after_debt_service", "Not calculated in Part 1"),
)


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _borrower_type(record: Mapping[str, Any]) -> str:
    """Use an explicit type; business-specific fields are evidence of business type."""
    raw_type = record.get("borrower_type") or record.get("applicant_type")
    normalized = str(raw_type or "").strip().casefold()
    if normalized in {"personal", "individual", "person"}:
        return "Personal"
    if normalized in {"business", "company", "corporate", "organization"}:
        return "Business"
    if any(_has_value(record.get(field)) for field in ("business_name", "business_type", "industry")):
        return "Business"
    return "Not specified"


def _assessment_status(record: Mapping[str, Any]) -> str:
    assessment = record.get("credit_assessment")
    nested_status = assessment.get("status") if isinstance(assessment, Mapping) else None
    return str(record.get("assessment_status") or nested_status or "Not Started")


def _application_name(record: Mapping[str, Any]) -> str:
    if _borrower_type(record) == "Business":
        return str(record.get("business_name") or record.get("applicant_name") or "Name not provided")
    return str(record.get("applicant_name") or "Name not provided")


def _format_amount(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "Not available"


def _format_updated(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%b %d, %Y %H:%M") if value.tzinfo else value.strftime("%b %d, %Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%b %d, %Y")
    if value not in (None, ""):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%b %d, %Y %H:%M")
        except ValueError:
            return str(value)
    return "Not recorded"


def _source_label(record: Mapping[str, Any]) -> str:
    application_id = str(record.get("application_id", ""))
    source = str(record.get("data_source", "")).casefold()
    return "Demo data" if application_id.startswith("APP-DEMO-") or source == "demo" else "Loan Applications record"


def _expected_fields(borrower_type: str) -> tuple[tuple[str, str], ...]:
    if borrower_type == "Personal":
        return (
            ("Gross monthly income", "gross_monthly_income"),
            ("Net monthly income", "net_monthly_income"),
            ("Monthly expenses", "monthly_expenses"),
            ("Monthly debt payments", "monthly_debt_payments"),
            ("Borrower type", "borrower_type"),
            ("Currency", "currency"),
        )
    if borrower_type == "Business":
        return (
            ("Business name", "business_name"),
            ("Business type", "business_type"),
            ("Industry", "industry"),
            ("Business operating period", "business_operating_period"),
            ("Revenue amount and frequency", "revenue_amount"),
            ("Operating expenses", "monthly_operating_expenses"),
            ("Existing business debt service", "existing_business_debt_service"),
            ("Currency", "currency"),
        )
    return (
        ("Borrower type", "borrower_type"),
        ("Income classification (gross/net)", "gross_monthly_income"),
        ("Monthly debt payments", "monthly_debt_payments"),
        ("Currency", "currency"),
    )


def _financial_values(record: Mapping[str, Any], borrower_type: str) -> list[tuple[str, Any, str]]:
    if borrower_type == "Personal":
        fields: Sequence[tuple[str, str, str]] = _PERSONAL_OVERVIEW_FIELDS
    elif borrower_type == "Business":
        fields = _BUSINESS_OVERVIEW_FIELDS
    else:
        fields = tuple(
            (label, field, "Source field; borrower type and financial classification are not specified")
            for label, field in _GENERIC_FINANCIAL_FIELDS
        )

    return [
        (label, _format_amount(record.get(field)), note)
        for label, field, note in fields
    ]


def _information_state(record: Mapping[str, Any]) -> dict[str, Any]:
    borrower_type = _borrower_type(record)
    assessment = record.get("credit_assessment")
    verification = assessment.get("verification_statuses", {}) if isinstance(assessment, Mapping) else {}
    if not isinstance(verification, Mapping):
        verification = {}

    financial_fields = (
        ("Monthly income", "monthly_income"),
        ("Monthly expenses", "monthly_expenses"),
        ("Existing debt field", "existing_debt"),
        ("Other obligations", "other_obligations"),
        ("Available monthly income", "available_monthly_income"),
        ("Gross monthly income", "gross_monthly_income"),
        ("Net monthly income", "net_monthly_income"),
        ("Monthly debt payments", "monthly_debt_payments"),
        ("Business revenue", "monthly_business_revenue"),
        ("Business operating expenses", "monthly_operating_expenses"),
        ("Existing business debt service", "existing_business_debt_service"),
    )
    available = [(label, field) for label, field in financial_fields if _has_value(record.get(field))]
    missing = [label for label, field in _expected_fields(borrower_type) if not _has_value(record.get(field))]
    if borrower_type == "Not specified":
        missing.append("Borrower-specific personal or business classification")

    verified = [label for label, field in financial_fields if _has_value(record.get(field)) and verification.get(field) == "Verified"]
    unverified = [label for label, field in financial_fields if _has_value(record.get(field)) and verification.get(field) != "Verified"]

    history = record.get("history", [])
    last_activity = history[-1].get("timestamp") if history and isinstance(history[-1], Mapping) else None
    last_updated = (
        (assessment.get("last_updated") if isinstance(assessment, Mapping) else None)
        or record.get("updated_at")
        or last_activity
        or record.get("application_date")
    )
    return {
        "available": available,
        "missing": missing,
        "verified": verified,
        "unverified": unverified,
        "last_updated": _format_updated(last_updated),
        "source": _source_label(record),
    }


def _page_styles(dark: bool) -> str:
    if dark:
        surface, text, muted, border, soft = "#172338", "#F1F5F9", "#A7B4C5", "#33445C", "#1A2940"
    else:
        surface, text, muted, border, soft = "#FFFFFF", "#1E293B", "#64748B", "#E2E8F0", "#F5F7FA"
    return f"""
    <style>
    .st-key-debt-analysis-page {{ color:{text}; }}
    .st-key-debt-analysis-page .financial-workspace-heading h1 {{ color:{text}; font-size:1.62rem; font-weight:750; margin:0; }}
    .st-key-debt-analysis-page .financial-workspace-heading p {{ color:{muted}; font-size:0.9rem; margin:5px 0 17px; }}
    .st-key-debt-analysis-page .da-summary-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:9px; margin:4px 0 16px; }}
    .st-key-debt-analysis-page .da-summary-card {{ min-width:0; min-height:75px; box-sizing:border-box; border:1px solid {border}; border-radius:11px; background:{surface}; padding:12px 13px; }}
    .st-key-debt-analysis-page .da-summary-label {{ color:{muted}; font-size:0.7rem; font-weight:650; margin-bottom:6px; }}
    .st-key-debt-analysis-page .da-summary-value {{ color:{text}; font-size:0.87rem; font-weight:700; line-height:1.25; overflow-wrap:anywhere; }}
    .st-key-debt-analysis-page .da-section {{ background:{surface}; border:1px solid {border}; border-radius:12px; padding:14px 16px; margin:0 0 13px; }}
    .st-key-debt-analysis-page .da-section-title {{ color:{text}; font-size:0.98rem; font-weight:700; margin:0 0 4px; }}
    .st-key-debt-analysis-page .da-section-copy {{ color:{muted}; font-size:0.78rem; margin:0 0 10px; }}
    .st-key-debt-analysis-page .da-value-card {{ height:100%; min-height:88px; box-sizing:border-box; border:1px solid {border}; border-radius:10px; background:{surface}; padding:12px 13px; }}
    .st-key-debt-analysis-page .da-value-label {{ color:{muted}; font-size:0.71rem; font-weight:650; }}
    .st-key-debt-analysis-page .da-value-number {{ color:{text}; font-size:1.05rem; font-weight:750; margin-top:7px; line-height:1.2; overflow-wrap:anywhere; }}
    .st-key-debt-analysis-page .da-value-note {{ color:{muted}; font-size:0.69rem; margin-top:5px; line-height:1.35; }}
    .st-key-debt-analysis-page .da-note {{ background:{soft}; border-left:3px solid #2563EB; border-radius:0 8px 8px 0; color:{text}; font-size:0.8rem; line-height:1.5; padding:10px 13px; margin:8px 0 13px; }}
    .st-key-debt-analysis-page .da-list-item {{ color:{text}; font-size:0.78rem; line-height:1.45; padding:6px 0; border-bottom:1px solid {border}; }}
    .st-key-debt-analysis-page .da-list-item:last-child {{ border-bottom:0; }}
    .st-key-debt-analysis-page .stTabs [data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid {border}; }}
    .st-key-debt-analysis-page .stTabs [data-baseweb="tab"] {{ color:{muted}; font-weight:650; }}
    .st-key-debt-analysis-page .stTabs [aria-selected="true"] {{ color:#2563EB; }}
    @media (max-width: 1000px) {{ .st-key-debt-analysis-page .da-summary-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} }}
    @media (max-width: 650px) {{ .st-key-debt-analysis-page .da-summary-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
    </style>
    """


def _summary_card(label: str, value: Any) -> str:
    if label in {"Requested loan amount"}:
        rendered_value = _format_amount(value) if _has_value(value) else "Not available"
    else:
        rendered_value = str(value) if _has_value(value) else "Not available"
    return (
        '<div class="da-summary-card">'
        f'<div class="da-summary-label">{html.escape(label)}</div>'
        f'<div class="da-summary-value">{html.escape(rendered_value)}</div></div>'
    )


def _value_card(label: str, value: Any, note: str = "") -> str:
    if isinstance(value, (float, int)):
        rendered = _format_amount(value)
    else:
        rendered = str(value) if _has_value(value) else "Not available"
    return (
        '<div class="da-value-card">'
        f'<div class="da-value-label">{html.escape(label)}</div>'
        f'<div class="da-value-number">{html.escape(rendered)}</div>'
        f'<div class="da-value-note">{html.escape(note)}</div></div>'
    )


def _render_value_grid(values: Sequence[tuple[str, Any, str]], columns_count: int = 3) -> None:
    for start in range(0, len(values), columns_count):
        batch = values[start : start + columns_count]
        columns = st.columns(columns_count, gap="small")
        for column, item in zip(columns, batch):
            with column:
                st.markdown(_value_card(*item), unsafe_allow_html=True)


def _render_capacity_value_grid(
    values: Sequence[tuple[str, Any, str]],
    columns_count: int = 3,
) -> None:
    """Add controlled vertical separation between capacity card rows only."""
    for row_index, start in enumerate(range(0, len(values), columns_count)):
        if row_index:
            st.markdown(
                '<div aria-hidden="true" style="display:block;width:100%;height:24px;min-height:24px;margin:0;padding:0;border:0;background:transparent;line-height:0;"></div>',
                unsafe_allow_html=True,
            )
        batch = values[start : start + columns_count]
        columns = st.columns(columns_count, gap="small")
        for column, item in zip(columns, batch):
            with column:
                st.markdown(_value_card(*item), unsafe_allow_html=True)


def _render_information_completeness(record: Mapping[str, Any]) -> None:
    state = _information_state(record)
    verified_count = len(state["verified"])
    available_count = len(state["available"])
    missing_count = len(state["missing"])
    _render_value_grid(
        (
            ("Available financial fields", f"{available_count}", "Values present in the shared application record"),
            ("Missing items", f"{missing_count}", "Required to complete borrower-specific review"),
            ("Explicitly verified", f"{verified_count}", "Only fields marked Verified in Credit Assessment"),
            ("Last updated", state["last_updated"], "Most recent available record or assessment activity"),
        ),
        columns_count=4,
    )
    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(key="debt-available-information"):
            st.markdown('<div class="da-section-title">Available information</div>', unsafe_allow_html=True)
            if state["available"]:
                for label, field in state["available"]:
                    value = _format_amount(record.get(field))
                    st.markdown(
                        f'<div class="da-list-item"><strong>{html.escape(label)}</strong> · {html.escape(value)} · Applicant-declared</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No financial values are present in this record.")
            if _has_value(record.get("available_monthly_income")):
                st.caption(
                    "Stored calculated value: Available monthly income was computed in Loan Applications as monthly income minus monthly expenses and other obligations. It is not verified net income."
                )
    with right:
        with st.container(key="debt-missing-information"):
            st.markdown('<div class="da-section-title">Missing and verification status</div>', unsafe_allow_html=True)
            if state["missing"]:
                for item in state["missing"]:
                    st.markdown(f'<div class="da-list-item">Missing: {html.escape(item)}</div>', unsafe_allow_html=True)
            else:
                st.caption("No expected fields are missing for the selected borrower type.")
            if state["unverified"]:
                st.caption("Present but not marked Verified:")
                st.write(", ".join(state["unverified"]))
            else:
                st.caption("No present financial fields are marked unverified.")


def _render_financial_overview(record: Mapping[str, Any]) -> None:
    borrower_type = _borrower_type(record)
    st.markdown(
        '<div class="da-note"><strong>Data handling:</strong> Amounts are shown exactly as recorded, without a currency symbol because the source does not specify currency. Applicant-declared values are not treated as verified. No repayment calculations are performed in Part 1.</div>',
        unsafe_allow_html=True,
    )

    if borrower_type == "Personal":
        st.markdown('<div class="da-section-title">Personal financial overview</div>', unsafe_allow_html=True)
        overview = _PERSONAL_OVERVIEW_FIELDS
    elif borrower_type == "Business":
        st.markdown('<div class="da-section-title">Business financial overview</div>', unsafe_allow_html=True)
        overview = _BUSINESS_OVERVIEW_FIELDS
    else:
        st.warning("Borrower type is not specified in the application record. The loan purpose is not used to infer personal or business borrower type.")
        st.markdown('<div class="da-section-title">Financial values as recorded</div>', unsafe_allow_html=True)
        overview = tuple(
            (label, field, "Recorded field; meaning or borrower category is not inferred")
            for label, field in _GENERIC_FINANCIAL_FIELDS
        )

    display_values = []
    for label, field, note in overview:
        value = record.get(field)
        if field == "available_monthly_income" and _has_value(value):
            note = "Stored calculated value; not verified net income"
        display_values.append((label, value, note))
    _render_value_grid(display_values, columns_count=4)

    st.markdown('<div class="da-section-title" style="margin-top:14px">Financial information completeness</div>', unsafe_allow_html=True)
    _render_information_completeness(record)

    status = _assessment_status(record)
    st.caption(
        f"Source: {_source_label(record)} · Assessment status: {status} · Currency: Not specified in current application data."
    )


def _assessment_status(record: Mapping[str, Any]) -> str:
    assessment = record.get("credit_assessment")
    nested = assessment.get("status") if isinstance(assessment, Mapping) else None
    return str(record.get("assessment_status") or nested or "Not Started")


def _assessment_filter_records(
    records: Sequence[Mapping[str, Any]],
    search: str,
    borrower_type: str,
    purpose: str,
    application_status: str,
    assessment_status: str,
) -> list[Mapping[str, Any]]:
    normalized = search.strip().casefold()
    filtered = []
    for record in eligible_applications(records):
        kind = _borrower_type(record)
        name = _application_name(record)
        application_id = str(record.get("application_id", ""))
        if normalized and normalized not in application_id.casefold() and normalized not in name.casefold():
            continue
        if borrower_type != "All" and kind != borrower_type:
            continue
        if purpose != "All" and str(record.get("loan_purpose") or "Not specified") != purpose:
            continue
        if application_status != "All" and record.get("status") != application_status:
            continue
        if assessment_status != "All" and _assessment_status(record) != assessment_status:
            continue
        filtered.append(record)
    return filtered


def _records() -> list[dict[str, Any]]:
    if APPLICATIONS_KEY not in st.session_state:
        st.session_state[APPLICATIONS_KEY] = create_loan_application_demo_data()
    records = st.session_state.get(APPLICATIONS_KEY, [])
    return [record for record in records if isinstance(record, dict)]


def _render_not_implemented(part: int, name: str) -> None:
    st.markdown(f"### {html.escape(name)}")
    st.info(f"Part {part} is staged for a later implementation step.")


def normalize_monthly_amount(amount: Any, frequency: str) -> float | None:
    """Normalize a positive, explicitly-periodized amount to a monthly value."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    factors = {"Monthly": 1.0, "Weekly": 52.0 / 12.0, "Biweekly": 26.0 / 12.0, "Annual": 1.0 / 12.0}
    factor = factors.get(str(frequency))
    return value * factor if factor is not None else None


def calculate_business_cfads(
    monthly_revenue: float | None,
    monthly_other_operating_income: float | None,
    normalized_monthly_expenses: Sequence[float | None],
    *,
    expense_categories_complete: bool,
    other_income_reviewed: bool,
    currency_confirmed: bool,
) -> float | None:
    """CFADS = normalized operating income less all required operating costs."""
    if (
        monthly_revenue is None
        or not expense_categories_complete
        or not other_income_reviewed
        or not currency_confirmed
        or not normalized_monthly_expenses
        or any(value is None for value in normalized_monthly_expenses)
    ):
        return None
    return (monthly_revenue + (monthly_other_operating_income or 0.0)) - sum(
        value for value in normalized_monthly_expenses if value is not None
    )


def calculate_amortizing_loan(
    loan_amount: Any,
    annual_interest_rate: Any,
    loan_term_months: Any,
    repayment_frequency: str = "Monthly",
) -> dict[str, float | int] | None:
    """Calculate a fixed-rate installment and monthly equivalent, excluding fees."""
    amount = _amount(loan_amount)
    rate_percent = _amount(annual_interest_rate)
    term = _amount(loan_term_months)
    if amount is None or amount <= 0 or rate_percent is None or term is None or term <= 0:
        return None
    periods_per_year = {"Monthly": 12, "Biweekly": 26, "Weekly": 52}.get(repayment_frequency)
    if periods_per_year is None:
        return None
    periods = max(1, int(round(float(term) * periods_per_year / 12)))
    periodic_rate = float(rate_percent) / 100.0 / periods_per_year
    if periodic_rate == 0:
        installment = float(amount) / periods
    else:
        discount_factor = (1.0 + periodic_rate) ** (-periods)
        installment = float(amount) * periodic_rate / (1.0 - discount_factor)
    total_repayment = installment * periods
    return {
        "installment": installment,
        "monthly_installment": installment * periods_per_year / 12.0,
        "periods": periods,
        "periods_per_year": periods_per_year,
        "total_repayment": total_repayment,
        "total_interest": total_repayment - float(amount),
    }


def calculate_personal_capacity(
    gross_monthly_income: float | None,
    net_monthly_income: float | None,
    monthly_living_expenses: float | None,
    existing_monthly_debt_payments: float | None,
    proposed_monthly_installment: float | None,
) -> dict[str, float | None]:
    """Calculate personal ratios and cash remaining, leaving unavailable metrics as None."""
    gross = _amount(gross_monthly_income)
    net = _amount(net_monthly_income)
    expenses = _amount(monthly_living_expenses)
    existing = _amount(existing_monthly_debt_payments)
    proposed = _amount(proposed_monthly_installment)
    dti = existing / gross * 100 if existing is not None and gross is not None and gross > 0 else None
    dsti = (existing + proposed) / gross * 100 if existing is not None and proposed is not None and gross is not None and gross > 0 else None
    disposable = net - expenses - existing if net is not None and expenses is not None and existing is not None else None
    remaining = disposable - proposed if disposable is not None and proposed is not None else None
    return {
        "dti_percent": dti,
        "dsti_percent": dsti,
        "disposable_income": disposable,
        "remaining_income": remaining,
    }


def calculate_business_capacity(
    cfads: float | None,
    existing_monthly_debt_service: float | None,
    proposed_monthly_installment: float | None,
) -> dict[str, float | None]:
    """Calculate DSCR and remaining monthly cash flow from period-matched inputs."""
    available = _numeric_value(cfads)
    existing = _amount(existing_monthly_debt_service)
    proposed = _amount(proposed_monthly_installment)
    total = existing + proposed if existing is not None and proposed is not None else None
    dscr = available / total if available is not None and total is not None and total > 0 else None
    remaining = available - total if available is not None and total is not None else None
    return {
        "cfads": available,
        "existing_monthly_debt_service": existing,
        "proposed_monthly_installment": proposed,
        "total_monthly_debt_service": total,
        "dscr": dscr,
        "remaining_cash_flow": remaining,
    }


def simulate_personal_scenario(
    *,
    gross_monthly_income: float | None,
    net_monthly_income: float | None,
    monthly_living_expenses: float | None,
    existing_monthly_debt_payments: float | None,
    loan_amount: float | None,
    annual_interest_rate: float | None,
    loan_term_months: int | None,
    repayment_frequency: str,
    income_reduction_percent: float = 0,
    living_expense_increase_percent: float = 0,
    existing_debt_increase_percent: float = 0,
    interest_rate_increase_points: float = 0,
) -> dict[str, Any]:
    """Calculate a clearly hypothetical personal stress case without mutating source data."""
    shocks = [income_reduction_percent, living_expense_increase_percent, existing_debt_increase_percent, interest_rate_increase_points]
    if any(_amount(value) is None for value in shocks):
        raise ValueError("Scenario changes must be nonnegative finite values.")
    income_factor = 1 - min(float(income_reduction_percent), 100) / 100
    gross = float(gross_monthly_income) * income_factor if _amount(gross_monthly_income) is not None else None
    net = float(net_monthly_income) * income_factor if _amount(net_monthly_income) is not None else None
    expenses = float(monthly_living_expenses) * (1 + float(living_expense_increase_percent) / 100) if _amount(monthly_living_expenses) is not None else None
    existing = float(existing_monthly_debt_payments) * (1 + float(existing_debt_increase_percent) / 100) if _amount(existing_monthly_debt_payments) is not None else None
    rate = float(annual_interest_rate) + float(interest_rate_increase_points) if _amount(annual_interest_rate) is not None else None
    loan = calculate_amortizing_loan(loan_amount, rate, loan_term_months, repayment_frequency) if rate is not None else None
    metrics = calculate_personal_capacity(gross, net, expenses, existing, loan.get("monthly_installment") if loan else None)
    return {
        "gross_monthly_income": gross,
        "net_monthly_income": net,
        "monthly_living_expenses": expenses,
        "existing_monthly_debt_payments": existing,
        "annual_interest_rate": rate,
        "loan_calculation": loan,
        **metrics,
    }


def simulate_business_scenario(
    *,
    monthly_revenue: float | None,
    monthly_other_operating_income: float | None,
    monthly_operating_expenses: float | None,
    existing_monthly_debt_service: float | None,
    loan_amount: float | None,
    annual_interest_rate: float | None,
    loan_term_months: int | None,
    repayment_frequency: str,
    revenue_reduction_percent: float = 0,
    operating_expense_increase_percent: float = 0,
    existing_debt_service_increase_percent: float = 0,
    interest_rate_increase_points: float = 0,
) -> dict[str, Any]:
    """Calculate hypothetical monthly business CFADS and debt service; revenue stays revenue."""
    shocks = [revenue_reduction_percent, operating_expense_increase_percent, existing_debt_service_increase_percent, interest_rate_increase_points]
    if any(_amount(value) is None for value in shocks):
        raise ValueError("Scenario changes must be nonnegative finite values.")
    revenue = float(monthly_revenue) * (1 - min(float(revenue_reduction_percent), 100) / 100) if _amount(monthly_revenue) is not None else None
    other_income = _amount(monthly_other_operating_income)
    expenses = float(monthly_operating_expenses) * (1 + float(operating_expense_increase_percent) / 100) if _amount(monthly_operating_expenses) is not None else None
    existing = float(existing_monthly_debt_service) * (1 + float(existing_debt_service_increase_percent) / 100) if _amount(existing_monthly_debt_service) is not None else None
    rate = float(annual_interest_rate) + float(interest_rate_increase_points) if _amount(annual_interest_rate) is not None else None
    cfads = revenue + other_income - expenses if revenue is not None and other_income is not None and expenses is not None else None
    loan = calculate_amortizing_loan(loan_amount, rate, loan_term_months, repayment_frequency) if rate is not None else None
    metrics = calculate_business_capacity(cfads, existing, loan.get("monthly_installment") if loan else None)
    return {
        "monthly_revenue": revenue,
        "monthly_other_operating_income": other_income,
        "monthly_operating_expenses": expenses,
        "annual_interest_rate": rate,
        "loan_calculation": loan,
        **metrics,
    }


def build_financial_report_data(record: Mapping[str, Any], application_id: str) -> dict[str, Any]:
    """Build a read-only report model from the selected shared application record."""
    analysis = record.get("financial_analysis", {})
    analysis = analysis if isinstance(analysis, Mapping) else {}
    part_two = analysis.get("income_cash_flow", {})
    part_two = part_two if isinstance(part_two, Mapping) else {}
    borrower_type = _borrower_type(record)
    if borrower_type not in {"Personal", "Business"}:
        borrower_type = part_two.get("borrower_type") if part_two.get("borrower_type") in {"Personal", "Business"} else None
    if borrower_type is None:
        return {"application_id": application_id, "borrower_type": None, "sections": [], "export_rows": [], "missing": ["Choose a Personal or Business analysis view in Income & Cash Flow."], "concerns": [], "scenarios": [], "currency": "", "currency_confirmed": False}

    capacity_root = analysis.get("repayment_capacity", {})
    capacity_root = capacity_root if isinstance(capacity_root, Mapping) else {}
    capacity = capacity_root.get(borrower_type.casefold(), {})
    capacity = capacity if isinstance(capacity, Mapping) else {}
    calculator = capacity_root.get("calculator", {})
    calculator = calculator if isinstance(calculator, Mapping) else {}
    currency = str(part_two.get("currency") or calculator.get("currency") or "").strip()
    currency_confirmed = bool(part_two.get("currency_confirmed") and currency and str(part_two.get("currency", "")).strip().casefold() == currency.casefold() and str(calculator.get("currency", currency)).strip().casefold() == currency.casefold())
    currency_label = currency if currency_confirmed else f"{currency or 'Currency not specified'} (unconfirmed)"

    obligations_root = analysis.get("obligations", {})
    obligations_root = obligations_root if isinstance(obligations_root, Mapping) else {}
    expense_key, debt_key, categories, _ = OBLIGATION_COLLECTIONS[borrower_type]
    expenses = obligations_root.get(expense_key, [])
    debts = obligations_root.get(debt_key, [])
    expenses = [item for item in expenses if isinstance(item, Mapping)] if isinstance(expenses, Sequence) else []
    debts = [item for item in debts if isinstance(item, Mapping)] if isinstance(debts, Sequence) else []
    part_two_expenses = part_two.get("business_expenses", []) if borrower_type == "Business" else []
    if not isinstance(part_two_expenses, Sequence) or isinstance(part_two_expenses, (str, bytes)):
        part_two_expenses = []
    no_debts = bool(obligations_root.get(f"{borrower_type.casefold()}_no_debts_reported")) and not debts
    obligations = calculate_obligations_summary(
        expenses, debts, categories, currency_confirmed=currency_confirmed,
        no_debts_reported=no_debts, part_two_business_expenses=part_two_expenses,
    )

    missing: list[str] = []
    if not currency_confirmed:
        missing.append("Confirm a common currency in Parts 2 and 4 before comparing amounts.")
    income_sources = [item for item in part_two.get("income_sources", []) if isinstance(item, Mapping)] if isinstance(part_two.get("income_sources", []), Sequence) else []
    income_rows: list[dict[str, Any]] = []
    if borrower_type == "Personal":
        gross, net = personal_monthly_income(record)
        if not income_sources and not (record.get("currency") and str(record.get("currency")).strip().casefold() == str(calculator.get("currency", "")).strip().casefold()):
            gross = net = None
        for source in income_sources:
            monthly_gross = normalize_monthly_amount(source.get("gross_amount"), str(source.get("frequency", "")))
            monthly_net = normalize_monthly_amount(source.get("net_amount"), str(source.get("frequency", "")))
            income_rows.append({"Source": source.get("name") or source.get("type") or "Income source", "Type": source.get("type", "Not specified"), "Reporting period": source.get("frequency", "Not specified"), "Gross amount": source.get("gross_amount"), "Monthly gross": monthly_gross, "Net amount": source.get("net_amount"), "Monthly net": monthly_net, "Verification": source.get("verification_status", "Unverified")})
        if gross is None:
            missing.append("Complete and periodize all gross income sources.")
        if net is None:
            missing.append("Complete net income amounts for all personal income sources.")
        if obligations.get("total_expenses") is None:
            missing.extend(f"Living expense: {category}" for category in obligations.get("missing_expense_categories", []))
            missing.extend(f"Verify monthly reporting period for living expense: {category}" for category in obligations.get("invalid_expense_categories", []))
        if obligations.get("total_monthly_debt_payments") is None:
            missing.append("Record existing debt monthly payments or confirm no existing debts.")
        if capacity.get("dti_percent") is None or capacity.get("dsti_percent") is None:
            missing.append("DTI/DSTI require gross income greater than zero and complete debt/payment inputs.")
        if capacity.get("disposable_income") is None or capacity.get("remaining_income") is None:
            missing.append("Net income, living expenses, existing debt payments, and proposed installment are needed for remaining-income calculations.")
        sections = [
            {"title": "Applicant and application", "rows": [("Applicant", _application_name(record)), ("Application ID", application_id), ("Borrower type", borrower_type), ("Loan purpose", record.get("loan_purpose", "Not specified")), ("Application status", record.get("status", "Not specified")), ("Application date", record.get("application_date", record.get("submitted_at", "Not specified")))]},
            {"title": "Income sources and normalized monthly income", "rows": [("Gross monthly income", gross), ("Net monthly income", net), ("Currency", currency_label)]},
            {"title": "Living expenses and existing personal debts", "rows": [("Total monthly living expenses", obligations.get("total_expenses")), ("Existing monthly debt payments", obligations.get("total_monthly_debt_payments")), ("Total outstanding debt balance", obligations.get("total_outstanding_debt")), ("Debt payments are excluded from living expense totals", "Yes")]},
            {"title": "Proposed loan and repayment capacity", "rows": [("Proposed amount", calculator.get("loan_amount")), ("Annual interest rate (%)", calculator.get("annual_interest_rate")), ("Term (months)", calculator.get("loan_term_months")), ("Repayment frequency", calculator.get("repayment_frequency", "Not specified")), ("Monthly installment", calculator.get("monthly_installment")), ("Total repayment", calculator.get("total_repayment")), ("Total interest", calculator.get("total_interest")), ("DTI (%)", capacity.get("dti_percent")), ("DSTI (%)", capacity.get("dsti_percent")), ("Disposable monthly income", capacity.get("disposable_income")), ("Remaining income after installment", capacity.get("remaining_income")), ("Analyst interpretation", capacity.get("interpretation", "Not assessed — bank policy not configured"))]},
        ]
        if gross is not None and gross <= 0:
            missing.append("Gross income is zero; DTI/DSTI ratios are unavailable.")
        if capacity.get("disposable_income") is not None and capacity["disposable_income"] < 0:
            pass
        concern_values = [("Negative disposable income", capacity.get("disposable_income")), ("Negative remaining income after proposed installment", capacity.get("remaining_income"))]
    else:
        revenue, other_income, _ = business_monthly_operating_income(record)
        for source in income_sources:
            monthly = normalize_monthly_amount(source.get("gross_amount"), str(source.get("frequency", "")))
            income_rows.append({"Source": source.get("name") or source.get("type") or "Operating income", "Type": source.get("type", "Not specified"), "Reporting period": source.get("frequency", "Not specified"), "Amount": source.get("gross_amount"), "Normalized monthly amount": monthly, "Verification": source.get("verification_status", "Unverified")})
        if revenue is None:
            missing.append("Complete business revenue amount and reporting period.")
        if other_income is None:
            missing.append("Review other operating income, including confirming zero if none.")
        if obligations.get("total_expenses") is None:
            missing.extend(f"Operating expense: {category}" for category in obligations.get("missing_expense_categories", []))
            missing.extend(f"Verify monthly reporting period for operating expense: {category}" for category in obligations.get("invalid_expense_categories", []))
        if obligations.get("total_monthly_debt_payments") is None:
            missing.append("Record existing business debt service or confirm no business debts.")
        if capacity.get("cfads") is None:
            missing.append("Complete the period-matched CFADS inputs from Parts 2 and 3.")
        if capacity.get("dscr") is None:
            missing.append("DSCR requires complete monthly CFADS and total monthly debt service greater than zero.")
        sections = [
            {"title": "Business and application", "rows": [("Business", record.get("business_name") or _application_name(record)), ("Application ID", application_id), ("Borrower type", borrower_type), ("Business type", record.get("business_type", "Not specified")), ("Industry", record.get("industry", "Not specified")), ("Loan purpose", record.get("loan_purpose", "Not specified")), ("Application status", record.get("status", "Not specified")), ("Application date", record.get("application_date", record.get("submitted_at", "Not specified")))]},
            {"title": "Business revenue and operating income", "rows": [("Monthly business revenue", revenue), ("Other monthly operating income", other_income), ("Currency", currency_label), ("Reporting periods", "; ".join(dict.fromkeys(str(row.get("Reporting period")) for row in income_rows)) or ("Monthly" if record.get("monthly_business_revenue") is not None else record.get("revenue_frequency", "Not specified")))]},
            {"title": "Operating expenses and existing business debt", "rows": [("Total monthly operating expenses", obligations.get("total_expenses")), ("Existing monthly business debt service", obligations.get("total_monthly_debt_payments")), ("Total outstanding business debt", obligations.get("total_outstanding_debt")), ("Personal obligations included", "No")]},
            {"title": "Proposed loan and repayment capacity", "rows": [("Proposed amount", calculator.get("loan_amount")), ("Annual interest rate (%)", calculator.get("annual_interest_rate")), ("Term (months)", calculator.get("loan_term_months")), ("Repayment frequency", calculator.get("repayment_frequency", "Not specified")), ("Monthly installment", calculator.get("monthly_installment")), ("Total repayment", calculator.get("total_repayment")), ("Total interest", calculator.get("total_interest")), ("Cash flow available for debt service (CFADS)", capacity.get("cfads")), ("Existing monthly business debt service", capacity.get("existing_monthly_debt_service")), ("Proposed monthly installment", capacity.get("proposed_monthly_installment")), ("Total monthly debt service", capacity.get("total_monthly_debt_service")), ("DSCR", capacity.get("dscr")), ("Remaining cash flow after debt service", capacity.get("remaining_cash_flow")), ("Analyst interpretation", capacity.get("interpretation", "Not assessed — bank policy not configured"))]},
        ]
        concern_values = [("Negative CFADS", capacity.get("cfads")), ("Negative remaining cash flow after debt service", capacity.get("remaining_cash_flow"))]
        income_missing_metrics = {"Monthly business revenue": revenue, "Monthly other operating income": other_income}

    expense_source = part_two_expenses if borrower_type == "Business" else ()
    active_expenses = _active_expense_entries(expenses, expense_source)
    expense_rows = []
    for category in categories:
        entry = active_expenses.get(category)
        if entry is None:
            expense_rows.append({"Category": category, "Amount": None, "Frequency": "Missing", "Normalized monthly amount": None, "Source": "Missing"})
        else:
            expense_rows.append({"Category": category, "Amount": entry.get("amount"), "Frequency": entry.get("frequency", "Not specified"), "Normalized monthly amount": normalize_monthly_amount(entry.get("amount"), str(entry.get("frequency", ""))), "Source": entry.get("entry_source", "Part 2 entry")})
    debt_rows = []
    for debt in _active_debt_entries(debts):
        debt_rows.append({"Debt": debt.get("debt_type", "Debt"), "Lender / description": debt.get("lender") or debt.get("description") or "Not specified", "Outstanding balance": debt.get("outstanding_balance"), "Monthly payment": normalize_monthly_amount(debt.get("monthly_payment"), str(debt.get("payment_frequency", ""))), "Payment frequency": debt.get("payment_frequency", "Not specified"), "Source": debt.get("entry_source", "Applicant-declared")})
    if borrower_type == "Personal":
        sections[1]["rows"].append(("Income source count", len(income_rows)))
    else:
        sections[1]["rows"].append(("Income source count", len(income_rows)))

    if not calculator.get("monthly_installment"):
        if calculator.get("monthly_installment") is None:
            missing.append("Complete proposed loan amount, rate, term, frequency, and matching currency for installment calculations.")
    scenarios_root = analysis.get("scenario_analysis", {})
    scenarios_root = scenarios_root if isinstance(scenarios_root, Mapping) else {}
    scenarios = [dict(item) for item in scenarios_root.get(application_id, []) if isinstance(item, Mapping) and item.get("borrower_type") == borrower_type] if isinstance(scenarios_root.get(application_id, []), Sequence) else []
    for scenario in scenarios:
        result = scenario.get("results", {})
        main_key = "remaining_income" if borrower_type == "Personal" else "remaining_cash_flow"
        scenario["report_summary"] = result.get(main_key) if isinstance(result, Mapping) else None
    if scenarios:
        scenario_rows = []
        metric_keys = (
            ("Gross monthly income", "gross_monthly_income"), ("Net monthly income", "net_monthly_income"),
            ("Living expenses", "monthly_living_expenses"), ("Existing debt payments", "existing_monthly_debt_payments"),
            ("DTI (%)", "dti_percent"), ("DSTI (%)", "dsti_percent"), ("Disposable income", "disposable_income"),
            ("Remaining income", "remaining_income"),
        ) if borrower_type == "Personal" else (
            ("Business revenue", "monthly_revenue"), ("Operating expenses", "monthly_operating_expenses"),
            ("CFADS", "cfads"), ("Existing business debt service", "existing_monthly_debt_service"),
            ("Total debt service", "total_monthly_debt_service"), ("DSCR", "dscr"), ("Remaining cash flow", "remaining_cash_flow"),
        )
        for item in scenarios:
            result = item.get("results", {})
            result = result if isinstance(result, Mapping) else {}
            prefix = str(item.get("name", "Scenario"))
            scenario_rows.append((f"{prefix} - loan terms", f"{item.get('loan_amount')} {currency_label}; {item.get('annual_interest_rate')}% APR; {item.get('loan_term_months')} months; {item.get('repayment_frequency', 'Not specified')}"))
            for label, value in (item.get("stress", {}) or {}).items():
                scenario_rows.append((f"{prefix} - stress: {label.replace('_', ' ')}", value))
            if item.get("loan_calculation"):
                scenario_rows.append((f"{prefix} - monthly installment", item["loan_calculation"].get("monthly_installment")))
                scenario_rows.append((f"{prefix} - total repayment", item["loan_calculation"].get("total_repayment")))
                scenario_rows.append((f"{prefix} - total interest", item["loan_calculation"].get("total_interest")))
            for label, key in metric_keys:
                scenario_rows.append((f"{prefix} - {label}", result.get(key)))
        sections.append({"title": "Saved scenario analysis", "rows": scenario_rows})

    financial = analysis.get("financial_report", {})
    financial = financial if isinstance(financial, Mapping) else {}
    analyst_findings = financial.get("analyst_findings", {})
    analyst_findings = analyst_findings if isinstance(analyst_findings, Mapping) else {}
    concerns = [label for label, value in concern_values if isinstance(value, (int, float)) and value < 0]
    export_rows: list[dict[str, Any]] = []
    for section in sections:
        for label, value in section["rows"]:
            export_rows.append({"Section": section["title"], "Metric": label, "Value": _report_export_value(value), "Currency": currency_label if any(token in label.casefold() for token in ("income", "expense", "debt", "amount", "payment", "cash flow", "balance", "installment", "repayment")) else ""})
    for row in income_rows:
        export_rows.extend({"Section": "Income source detail", "Metric": label, "Value": _report_export_value(value), "Currency": currency_label if "amount" in label.casefold() or "monthly" in label.casefold() else ""} for label, value in row.items())
    for row in expense_rows:
        export_rows.extend({"Section": "Expense detail", "Metric": f"{row['Category']} - {label}", "Value": _report_export_value(value), "Currency": currency_label if label in {"Amount", "Normalized monthly amount"} else ""} for label, value in row.items())
    for row in debt_rows:
        export_rows.extend({"Section": "Debt detail", "Metric": f"{row['Debt']} - {label}", "Value": _report_export_value(value), "Currency": currency_label if label in {"Outstanding balance", "Monthly payment"} else ""} for label, value in row.items())
    for item in scenarios:
        export_rows.append({"Section": "Saved scenario", "Metric": str(item.get("name", "Scenario")), "Value": _report_export_value(item.get("report_summary")), "Currency": currency_label})
    for item in missing:
        export_rows.append({"Section": "Missing information", "Metric": "Item", "Value": item, "Currency": ""})
    for item in concerns:
        export_rows.append({"Section": "Financial concerns for human review", "Metric": "Flag", "Value": item, "Currency": ""})
    return {
        "application_id": application_id, "borrower_type": borrower_type, "applicant_name": _application_name(record),
        "currency": currency_label, "currency_confirmed": currency_confirmed, "sections": sections,
        "income_rows": income_rows, "expense_rows": expense_rows, "debt_rows": debt_rows,
        "missing": list(dict.fromkeys(missing)), "concerns": concerns, "scenarios": scenarios,
        "analyst_findings": dict(analyst_findings), "export_rows": export_rows,
    }


def _report_export_value(value: Any) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return f"{value:.4f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
    return str(value)


def _financial_report_pdf(lines: Sequence[str]) -> bytes:
    """Create a compact, multi-page, printable PDF using only the Python standard library."""
    wrapped: list[str] = []
    for line in lines:
        ascii_line = unicodedata.normalize("NFKD", str(line)).encode("ascii", "ignore").decode("ascii")
        wrapped.extend(textwrap.wrap(ascii_line, width=96, replace_whitespace=True) or [""])
    page_lines = [wrapped[index:index + 48] for index in range(0, max(len(wrapped), 1), 48)]
    objects: list[bytes] = []
    page_refs = []
    pages_obj_id = 2
    font_obj_id = 3 + len(page_lines) * 2
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")
    for index, page in enumerate(page_lines):
        page_id = 3 + index * 2
        content_id = page_id + 1
        page_refs.append(f"{page_id} 0 R")
        text_ops = ["BT", "/F1 10 Tf", "48 790 Td", "14 TL"]
        for line in page:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            text_ops.append(f"({safe}) Tj T*")
        text_ops.append("ET")
        stream = "\n".join(text_ops).encode("ascii")
        objects.append(f"<< /Type /Page /Parent {pages_obj_id} 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 {font_obj_id} 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii"))
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_lines)} >>".encode("ascii")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.extend(body + b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("ascii"))
    return bytes(pdf)


def _financial_report_csv(report: Mapping[str, Any], findings: Mapping[str, str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=("Section", "Metric", "Value", "Currency"))
    writer.writeheader()
    writer.writerows(report.get("export_rows", []))
    for label, value in findings.items():
        writer.writerow({"Section": "Analyst findings", "Metric": label.replace("_", " ").title(), "Value": value or "", "Currency": ""})
    return output.getvalue().encode("utf-8-sig")


def _financial_report_lines(report: Mapping[str, Any], findings: Mapping[str, str]) -> list[str]:
    lines = [
        "INTERNAL FINANCIAL ANALYSIS - FOR REVIEW PURPOSES ONLY",
        f"Applicant: {report.get('applicant_name', 'Not specified')}",
        f"Application ID: {report.get('application_id', 'Not specified')} | Borrower type: {report.get('borrower_type', 'Not specified')}",
        f"Currency: {report.get('currency', 'Not specified')}",
        "This report is an internal analysis aid. It is not a bank statement, guarantee, or loan approval.",
        "",
    ]
    for section in report.get("sections", []):
        lines.append(str(section.get("title", "Financial information")).upper())
        for label, value in section.get("rows", []):
            lines.append(f"{label}: {_report_export_value(value)}")
        lines.append("")
    for title, key in (("INCOME SOURCES", "income_rows"), ("EXPENSE DETAIL", "expense_rows"), ("EXISTING DEBT OBLIGATIONS", "debt_rows")):
        entries = report.get(key, [])
        lines.append(title)
        if not entries:
            lines.append("No recorded items")
        for entry in entries:
            lines.append(" | ".join(f"{label}: {_report_export_value(value)}" for label, value in entry.items()))
        lines.append("")
    lines.append("SAVED SCENARIOS")
    for scenario in report.get("scenarios", []):
        lines.append(f"{scenario.get('name', 'Scenario')}: loan {scenario.get('loan_amount')}, rate {scenario.get('annual_interest_rate')}%, term {scenario.get('loan_term_months')} months, frequency {scenario.get('repayment_frequency')}")
        lines.extend(f"  Stress {label.replace('_', ' ')}: {_report_export_value(value)}" for label, value in (scenario.get("stress", {}) or {}).items())
        results = scenario.get("results", {})
        if isinstance(results, Mapping):
            lines.extend(f"  {label.replace('_', ' ').title()}: {_report_export_value(value)}" for label, value in results.items() if value is not None)
        loan_result = scenario.get("loan_calculation")
        if isinstance(loan_result, Mapping):
            lines.extend(f"  {label.replace('_', ' ').title()}: {_report_export_value(value)}" for label, value in loan_result.items() if value is not None)
    if not report.get("scenarios"):
        lines.append("No saved scenarios")
    lines.extend(("", "MISSING INFORMATION"))
    lines.extend(f"- {item}" for item in report.get("missing", []))
    if not report.get("missing"):
        lines.append("No required fields flagged as missing by current analysis")
    lines.extend(("", "FINANCIAL CONCERNS FOR HUMAN REVIEW"))
    lines.extend(f"- {item}" for item in report.get("concerns", []))
    if not report.get("concerns"):
        lines.append("No negative cash-flow flags identified; this does not imply approval")
    lines.extend(("", "ANALYST FINDINGS - SEPARATE FROM CALCULATED RESULTS"))
    lines.extend(f"{label.replace('_', ' ').title()}: {findings.get(label, '') or 'Not entered'}" for label in (
        "positive_findings", "negative_findings", "missing_information", "documentation_concerns", "follow_up_requirements", "analyst_comments",
    ))
    lines.extend(("", "For review purposes only. Human review and applicable bank policy are required."))
    return lines


def _render_financial_report(record: dict[str, Any], application_id: str) -> None:
    st.markdown("### Financial Report")
    st.caption("A live report preview from this selected application and its Parts 1–5 analysis. Applicant records, calculated values, analyst findings, and saved scenarios remain separate.")
    report = build_financial_report_data(record, application_id)
    if report.get("borrower_type") is None:
        st.info(report.get("missing", ["Select a borrower type first."])[0])
        return

    analysis = record.setdefault("financial_analysis", {})
    if not isinstance(analysis, dict):
        analysis = {}
        record["financial_analysis"] = analysis
    report_store = analysis.setdefault("financial_report", {})
    if not isinstance(report_store, dict):
        report_store = {}
        analysis["financial_report"] = report_store
    saved_findings = report_store.setdefault("analyst_findings", {})
    if not isinstance(saved_findings, dict):
        saved_findings = {}
        report_store["analyst_findings"] = saved_findings

    st.markdown("#### Analyst findings")
    st.caption("These notes are analyst-entered and stored separately from calculated results and any ML outputs. Changes are saved to the shared application record in this session.")
    finding_fields = (
        ("positive_findings", "Positive financial findings"),
        ("negative_findings", "Negative financial findings"),
        ("missing_information", "Missing information (analyst notes)"),
        ("documentation_concerns", "Documentation concerns"),
        ("follow_up_requirements", "Follow-up requirements"),
        ("analyst_comments", "Analyst comments"),
    )
    findings: dict[str, str] = {}
    findings_cols = st.columns(2)
    for index, (key, label) in enumerate(finding_fields):
        with findings_cols[index % 2]:
            findings[key] = st.text_area(label, value=str(saved_findings.get(key, "")), key=f"financial-report-{key}-{application_id}", height=88)
        saved_findings[key] = findings[key]
    if any(saved_findings.get(key) != value for key, value in findings.items()):
        report_store["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")

    st.markdown("#### Report preview")
    st.caption("Internal Financial Analysis — For Review Purposes Only")
    preview_html = [
        "<style>@media print { body * { visibility:hidden !important; } .fin-report-preview, .fin-report-preview * { visibility:visible !important; } .fin-report-preview { position:absolute; left:0; top:0; width:100%; color:#172b4d !important; background:#fff !important; box-shadow:none !important; border:0 !important; } }</style>",
        '<div class="fin-report-preview" style="background:#fff;border:1px solid #dce5f1;border-radius:14px;padding:28px 32px;box-shadow:0 6px 20px rgba(20,48,82,.06);">',
        '<div style="color:#fff;background:#173a63;border-radius:10px;padding:18px 22px;margin-bottom:20px;">',
        '<div style="font-size:22px;font-weight:700;">Internal Financial Analysis — For Review Purposes Only</div>',
        f"<div style='margin-top:10px;color:#e6eef9;'>{html.escape(str(report['applicant_name']))} &nbsp; · &nbsp; {html.escape(str(application_id))} &nbsp; · &nbsp; {html.escape(str(report['borrower_type']))}</div>",
        "</div>",
    ]
    for section in report["sections"]:
        preview_html.append('<section style="margin:18px 0 22px;break-inside:avoid;">')
        preview_html.append(f"<h3 style='font-size:16px;color:#173a63;border-bottom:1px solid #dce5f1;padding-bottom:8px;margin-bottom:8px;'>{html.escape(str(section['title']))}</h3>")
        preview_html.append('<table style="width:100%;border-collapse:collapse;font-size:13px;">')
        for label, value in section["rows"]:
            shown = _report_export_value(value)
            if value is not None and isinstance(value, (int, float)) and any(word in label.casefold() for word in ("income", "expense", "debt", "amount", "payment", "cash flow", "balance", "installment", "repayment")):
                shown = f"{report['currency']} {shown}"
            preview_html.append(f"<tr><td style='padding:7px 8px;border-bottom:1px solid #edf1f6;color:#53657e;width:55%;'>{html.escape(str(label))}</td><td style='padding:7px 8px;border-bottom:1px solid #edf1f6;color:#172b4d;font-weight:600;'>{html.escape(shown)}</td></tr>")
        preview_html.append("</table></section>")
    for title, key in (("Income sources", "income_rows"), ("Expense details", "expense_rows"), ("Existing debt obligations", "debt_rows")):
        preview_html.append(f"<h3 style='font-size:16px;color:#173a63;border-bottom:1px solid #dce5f1;padding-bottom:8px;'>{html.escape(title)}</h3>")
        details = report.get(key, [])
        if details:
            headers = list(details[0])
            preview_html.append('<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:18px;"><thead><tr>')
            preview_html.extend(f"<th style='text-align:left;padding:7px;background:#f2f6fb;border-bottom:1px solid #dce5f1;'>{html.escape(str(header))}</th>" for header in headers)
            preview_html.append("</tr></thead><tbody>")
            for entry in details:
                preview_html.append("<tr>" + "".join(f"<td style='padding:7px;border-bottom:1px solid #edf1f6;'>{html.escape(_report_export_value(entry.get(header)))}</td>" for header in headers) + "</tr>")
            preview_html.append("</tbody></table>")
        else:
            preview_html.append('<p style="font-size:13px;color:#687b94;">No itemized records available.</p>')
    preview_html.append('<h3 style="font-size:16px;color:#173a63;border-bottom:1px solid #dce5f1;padding-bottom:8px;">Saved scenario analysis</h3>')
    if report["scenarios"]:
        preview_html.append('<ul style="font-size:13px;">')
        for scenario in report["scenarios"]:
            preview_html.append(f"<li>{html.escape(str(scenario.get('name', 'Scenario')))} — loan {_report_export_value(scenario.get('loan_amount'))}, rate {_report_export_value(scenario.get('annual_interest_rate'))}%, term {_report_export_value(scenario.get('loan_term_months'))} months; remaining {_report_export_value(scenario.get('report_summary'))}</li>")
        preview_html.append("</ul>")
    else:
        preview_html.append('<p style="font-size:13px;color:#687b94;">No saved scenarios for this application.</p>')
    for title, values in (("Missing information", report["missing"]), ("Financial concerns for human review", report["concerns"])):
        preview_html.append(f"<h3 style='font-size:16px;color:#173a63;border-bottom:1px solid #dce5f1;padding-bottom:8px;'>{html.escape(title)}</h3>")
        if values:
            preview_html.append("<ul style='font-size:13px;color:#344968;'>" + "".join(f"<li>{html.escape(str(value))}</li>" for value in values) + "</ul>")
        else:
            preview_html.append('<p style="font-size:13px;color:#687b94;">None identified from available analysis data.</p>')
    preview_html.append('<h3 style="font-size:16px;color:#173a63;border-bottom:1px solid #dce5f1;padding-bottom:8px;">Analyst findings</h3>')
    preview_html.append('<table style="width:100%;border-collapse:collapse;font-size:13px;">')
    for key, label in finding_fields:
        preview_html.append(f"<tr><td style='vertical-align:top;padding:8px;border-bottom:1px solid #edf1f6;color:#53657e;width:30%;'>{html.escape(label)}</td><td style='white-space:pre-wrap;padding:8px;border-bottom:1px solid #edf1f6;color:#172b4d;'>{html.escape(findings.get(key, '') or 'Not entered')}</td></tr>")
    preview_html.append("</table><p style='font-size:11px;color:#687b94;margin-top:22px;'>This internal report is for review purposes only. It is not an official bank statement, guaranteed financial assessment, or final loan approval. Apply relevant policy and human review.</p></div>")
    st.markdown("".join(preview_html), unsafe_allow_html=True)
    st.caption("Use your browser's Print command to print the preview; print styles isolate the report. The downloadable PDF uses a compact print-ready layout.")

    pdf_bytes = _financial_report_pdf(_financial_report_lines(report, findings))
    csv_bytes = _financial_report_csv(report, findings)
    slug = "".join(character for character in str(application_id) if character.isalnum() or character in "-_-") or "application"
    pdf_col, csv_col, _ = st.columns([1, 1, 4])
    with pdf_col:
        st.download_button("Download PDF", data=pdf_bytes, file_name=f"financial-analysis-{slug}.pdf", mime="application/pdf", key=f"financial-report-pdf-{application_id}")
    with csv_col:
        st.download_button("Download CSV", data=csv_bytes, file_name=f"financial-analysis-{slug}.csv", mime="text/csv", key=f"financial-report-csv-{application_id}")


def _financial_analysis_data(record: dict[str, Any]) -> dict[str, Any]:
    """Analysis inputs live beside, not over, the original application fields."""
    analysis = record.setdefault("financial_analysis", {})
    if not isinstance(analysis, dict):
        analysis = {}
        record["financial_analysis"] = analysis
    part_two = analysis.setdefault("income_cash_flow", {})
    if not isinstance(part_two, dict):
        part_two = {}
        analysis["income_cash_flow"] = part_two
    part_two.setdefault("income_sources", [])
    part_two.setdefault("business_expenses", [])
    part_two.setdefault("currency", "")
    part_two.setdefault("currency_confirmed", False)
    part_two.setdefault("other_operating_income_reviewed", False)
    return part_two


def _obligations_data(record: dict[str, Any]) -> dict[str, Any]:
    analysis = record.setdefault("financial_analysis", {})
    if not isinstance(analysis, dict):
        analysis = {}
        record["financial_analysis"] = analysis
    obligations = analysis.setdefault("obligations", {})
    if not isinstance(obligations, dict):
        obligations = {}
        analysis["obligations"] = obligations
    for expense_key, debt_key, _, _ in OBLIGATION_COLLECTIONS.values():
        obligations.setdefault(expense_key, [])
        obligations.setdefault(debt_key, [])
    obligations.setdefault("personal_no_debts_reported", False)
    obligations.setdefault("business_no_debts_reported", False)
    return obligations


def _active_expense_entries(
    detailed: Sequence[Mapping[str, Any]],
    part_two_business: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Mapping[str, Any]]:
    """Use one value per category; a staff adjustment supersedes declared data."""
    active: dict[str, Mapping[str, Any]] = {}
    for item in part_two_business:
        raw_category = str(item.get("category", ""))
        category = _PART_TWO_BUSINESS_CATEGORY_MAP.get(raw_category, raw_category)
        if category:
            active[category] = {**item, "category": category, "entry_source": "Part 2 entry (source not specified)"}
    for item in detailed:
        category = str(item.get("category", ""))
        if not category:
            continue
        current = active.get(category)
        source = item.get("entry_source")
        current_source = current.get("entry_source") if current else None
        if current is None or source == "Staff adjustment" or current_source != "Staff adjustment":
            active[category] = item
    return active


def _debt_identity(item: Mapping[str, Any]) -> str:
    identity = item.get("debt_identity")
    if identity:
        return str(identity)
    return "|".join((
        str(item.get("debt_type", "" )).strip().casefold(),
        str(item.get("lender", "")).strip().casefold(),
        str(item.get("description", "")).strip().casefold(),
    ))


def _active_debt_entries(entries: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in entries:
        grouped[_debt_identity(item)].append(item)
    active = []
    for group in grouped.values():
        adjustments = [item for item in group if item.get("entry_source") == "Staff adjustment"]
        active.append(adjustments[-1] if adjustments else group[-1])
    return active


def calculate_obligations_summary(
    expense_entries: Sequence[Mapping[str, Any]],
    debt_entries: Sequence[Mapping[str, Any]],
    required_expense_categories: Sequence[str],
    *,
    currency_confirmed: bool,
    no_debts_reported: bool = False,
    part_two_business_expenses: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return monthly category totals and debt totals, excluding superseded values."""
    active_expenses = _active_expense_entries(expense_entries, part_two_business_expenses)
    missing_categories = [category for category in required_expense_categories if category not in active_expenses]
    normalized_expenses = {
        category: normalize_monthly_amount(item.get("amount"), str(item.get("frequency", "")))
        for category, item in active_expenses.items()
    }
    invalid_expenses = [category for category in required_expense_categories if category in active_expenses and normalized_expenses.get(category) is None]
    partial_expense_total = sum(value for category, value in normalized_expenses.items() if category in required_expense_categories and value is not None) if currency_confirmed else None
    expense_complete = not missing_categories and not invalid_expenses and currency_confirmed
    total_expenses = partial_expense_total if expense_complete else None

    active_debts = _active_debt_entries(debt_entries)
    normalized_payments = [
        normalize_monthly_amount(item.get("monthly_payment"), str(item.get("payment_frequency", "")))
        if item.get("monthly_payment") is not None else None
        for item in active_debts
    ]
    balance_values = [item.get("outstanding_balance") for item in active_debts]
    debts_confirmed_none = no_debts_reported and not active_debts
    payments_complete = debts_confirmed_none or bool(active_debts) and all(value is not None for value in normalized_payments)
    balances_complete = debts_confirmed_none or bool(active_debts) and all(_amount(value) is not None for value in balance_values)
    monthly_payment_subtotal = sum(value for value in normalized_payments if value is not None) if currency_confirmed else None
    balance_subtotal = sum(float(value) for value in balance_values if _amount(value) is not None) if currency_confirmed else None
    return {
        "active_expenses": active_expenses,
        "missing_expense_categories": missing_categories,
        "invalid_expense_categories": invalid_expenses,
        "expense_subtotal": partial_expense_total,
        "total_expenses": total_expenses,
        "expense_complete": expense_complete,
        "active_debts": active_debts,
        "monthly_payment_subtotal": monthly_payment_subtotal,
        "total_monthly_debt_payments": monthly_payment_subtotal if payments_complete and currency_confirmed else (0.0 if debts_confirmed_none and currency_confirmed else None),
        "balance_subtotal": balance_subtotal,
        "total_outstanding_debt": balance_subtotal if balances_complete and currency_confirmed else (0.0 if debts_confirmed_none and currency_confirmed else None),
        "missing_debt_payment_count": sum(value is None for value in normalized_payments) if active_debts else (0 if debts_confirmed_none else 1),
        "missing_debt_balance_count": sum(_amount(value) is None for value in balance_values) if active_debts else (0 if debts_confirmed_none else 1),
        "debt_information_complete": payments_complete and balances_complete and currency_confirmed,
    }


def _effective_borrower_type(record: dict[str, Any], application_id: str) -> str | None:
    source_type = _borrower_type(record)
    part_two = _financial_analysis_data(record)
    saved_type = part_two.get("borrower_type")
    if source_type in {"Personal", "Business"}:
        return source_type
    if saved_type not in {"Personal", "Business"}:
        st.info("Choose Personal or Business in the Income & Cash Flow tab to set a working analysis view. This does not alter the original application classification.")
        return None
    return str(saved_type)


def _record_expense(
    entries: list[dict[str, Any]],
    *,
    category: str,
    amount: float,
    frequency: str,
    entry_source: str,
    verification_status: str,
) -> None:
    row = next((item for item in entries if item.get("category") == category and item.get("entry_source") == entry_source), None)
    values = {
        "category": category,
        "amount": float(amount),
        "frequency": frequency,
        "entry_source": entry_source,
        "verification_status": verification_status,
        "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
    }
    if row is None:
        entries.append(values)
    else:
        row.update(values)


def _render_expense_category_form(
    record: dict[str, Any],
    application_id: str,
    entries: list[dict[str, Any]],
    categories: Sequence[str],
    *,
    label: str,
) -> None:
    st.markdown(f"#### {label}")
    st.caption("Each category is a recurring amount with an explicit reporting frequency. Enter zero when a category has no cost; leave it unentered when information is missing.")
    with st.form(f"expense-entry-form-{application_id}-{label.casefold().replace(' ', '-')}", clear_on_submit=True):
        category_col, source_col, amount_col, frequency_col = st.columns([1.7, 1.2, 1, 1])
        with category_col:
            category = st.selectbox("Expense category", categories)
        with source_col:
            entry_source = st.selectbox("Value source", OBLIGATION_ENTRY_SOURCES)
        with amount_col:
            amount = st.number_input("Amount (blank if unknown; use zero if confirmed none)", min_value=0.0, value=None, step=100.0, format="%.2f")
        with frequency_col:
            frequency = st.selectbox("Reporting frequency", INCOME_FREQUENCIES)
        status_col, submit_col = st.columns([1.3, 1])
        with status_col:
            verification = st.selectbox("Verification status", VERIFICATION_STATES)
        with submit_col:
            submitted = st.form_submit_button("Save expense", type="primary", use_container_width=True)
        if submitted:
            if amount is None:
                st.error("Enter an amount, using zero only when that category is confirmed to have no cost.")
            else:
                _record_expense(
                    entries,
                    category=category,
                    amount=amount,
                    frequency=frequency,
                    entry_source=entry_source,
                    verification_status=verification,
                )
                _obligations_data(record)["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")


def _render_expense_entries(
    record: dict[str, Any],
    application_id: str,
    entries: list[dict[str, Any]],
    *,
    part_two_business_expenses: Sequence[Mapping[str, Any]] = (),
) -> None:
    if part_two_business_expenses:
        st.caption("Part 2 operating expense entries appear below as existing analysis values and are reused in this summary unless superseded by a Part 3 applicant-declared value or staff adjustment.")
    combined = list(entries)
    known_part_two = {(str(item.get("category")), str(item.get("frequency")), str(item.get("amount"))) for item in entries}
    for item in part_two_business_expenses:
        signature = (str(item.get("category")), str(item.get("frequency")), str(item.get("amount")))
        if signature not in known_part_two:
            category = _PART_TWO_BUSINESS_CATEGORY_MAP.get(str(item.get("category", "")), str(item.get("category", "")))
            combined.append({**item, "category": category, "entry_source": "Part 2 entry (source not specified)"})
    if not combined:
        st.info("No categorized expenses have been entered yet.")
        return
    active_expenses = _active_expense_entries(entries, part_two_business_expenses)
    for index, item in enumerate(combined):
        category = str(item.get("category", "Expense"))
        source = str(item.get("entry_source", "Applicant-declared"))
        identity = f"{category}-{source}".casefold().replace(" ", "-").replace("/", "-")
        col, status_col, remove_col = st.columns([5, 1.35, 0.8], vertical_alignment="center")
        monthly = normalize_monthly_amount(item.get("amount"), str(item.get("frequency", "")))
        amount_text = _format_amount(item.get("amount")) if _amount(item.get("amount")) is not None else "Not supplied"
        with col:
            selected = active_expenses.get(category, {})
            active = (
                str(selected.get("entry_source", "")) == source
                and str(selected.get("amount", "")) == str(item.get("amount", ""))
                and str(selected.get("frequency", "")) == str(item.get("frequency", ""))
            )
            suffix = " · used in totals" if active else " · retained as declared history"
            st.markdown(
                f"**{html.escape(category)}** · {html.escape(source)}{suffix}  \n"
                f"{amount_text} / {html.escape(str(item.get('frequency', 'Unknown')))} → monthly {_format_amount(monthly)}",
            )
        if item in entries:
            with status_col:
                current = item.get("verification_status", "Unverified")
                if current not in VERIFICATION_STATES:
                    current = "Needs Review"
                selected = st.selectbox("Verification", VERIFICATION_STATES, index=VERIFICATION_STATES.index(current), key=f"expense-row-verification-{application_id}-{identity}", label_visibility="collapsed")
                if selected != item.get("verification_status"):
                    item["verification_status"] = selected
                    item["verified_at"] = datetime.now().astimezone().isoformat(timespec="minutes") if selected == "Verified" else None
                    _obligations_data(record)["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
            with remove_col:
                if st.button("Remove", key=f"expense-row-remove-{application_id}-{identity}"):
                    entries.remove(item)
                    st.rerun()
        else:
            with status_col:
                st.caption(str(item.get("verification_status", "Unverified")))


def _render_debt_entry_form(
    record: dict[str, Any],
    application_id: str,
    entries: list[dict[str, Any]],
    debt_types: Sequence[str],
    *,
    borrower_type: str,
) -> None:
    st.markdown("#### Existing debts")
    st.caption("Balances are point-in-time amounts. Monthly repayment/service is a separate recurring amount. Debt service is not added to living or operating expense totals.")
    active_existing = _active_debt_entries(entries)
    identities = [str(item.get("debt_identity") or _debt_identity(item)) for item in active_existing]
    identity_to_row = {identity: row for identity, row in zip(identities, active_existing)}
    choices = [""] + identities
    target = st.selectbox(
        "Debt record (choose one to add a staff adjustment)",
        choices,
        format_func=lambda value: "Add a debt record" if not value else " · ".join(
            str(identity_to_row[value].get(field) or "") for field in ("debt_type", "lender", "description") if identity_to_row[value].get(field)
        ) or "Debt record",
        key=f"debt-target-{application_id}-{borrower_type.casefold()}",
    )
    existing = identity_to_row.get(target) if target else None
    debt_default_type = existing.get("debt_type") if existing else debt_types[0]
    with st.form(f"debt-entry-form-{application_id}-{borrower_type.casefold()}", clear_on_submit=True):
        type_col, source_col = st.columns([1.5, 1])
        with type_col:
            debt_type = st.selectbox("Debt category", debt_types, index=debt_types.index(debt_default_type) if debt_default_type in debt_types else 0)
        with source_col:
            entry_source = st.selectbox("Value source", OBLIGATION_ENTRY_SOURCES)
        lender_col, description_col = st.columns(2)
        with lender_col:
            lender = st.text_input("Lender (optional)", value=str(existing.get("lender", "")) if existing else "")
        with description_col:
            description = st.text_input("Debt description (optional)", value=str(existing.get("description", "")) if existing else "")
        balance_col, payment_col = st.columns(2)
        with balance_col:
            balance = st.number_input(
                "Outstanding balance (blank if unknown)", min_value=0.0,
                value=float(existing["outstanding_balance"]) if existing and existing.get("outstanding_balance") is not None else None,
                step=100.0, format="%.2f", key=f"debt-balance-{application_id}-{borrower_type.casefold()}-{target or 'new'}",
            )
        with payment_col:
            payment = st.number_input(
                "Monthly repayment / service (blank if unknown)", min_value=0.0,
                value=float(existing["monthly_payment"]) if existing and existing.get("monthly_payment") is not None else None,
                step=50.0, format="%.2f", key=f"debt-payment-{application_id}-{borrower_type.casefold()}-{target or 'new'}",
            )
        frequency_col, verification_col, submit_col = st.columns([1, 1.3, 1])
        with frequency_col:
            payment_frequency = st.selectbox("Payment frequency", INCOME_FREQUENCIES, index=INCOME_FREQUENCIES.index(existing.get("payment_frequency")) if existing and existing.get("payment_frequency") in INCOME_FREQUENCIES else 0, key=f"debt-payment-frequency-{application_id}-{borrower_type.casefold()}-{target or 'new'}")
        with verification_col:
            verification = st.selectbox("Verification status", VERIFICATION_STATES)
        with submit_col:
            submitted = st.form_submit_button("Save debt", type="primary", use_container_width=True)
        if submitted:
            if balance is None and payment is None:
                st.error("Enter a balance or monthly payment, including zero when confirmed.")
            else:
                debt_identity = target or "|".join((debt_type.casefold(), lender.strip().casefold(), description.strip().casefold()))
                if debt_identity.endswith("||") or debt_identity == debt_type.casefold() + "||":
                    debt_identity = f"{debt_type.casefold()}|{uuid4().hex}"
                row = next((item for item in entries if item.get("debt_identity") == debt_identity and item.get("entry_source") == entry_source), None)
                values = {
                    "debt_identity": debt_identity, "debt_type": debt_type, "lender": lender.strip(),
                    "description": description.strip(), "outstanding_balance": float(balance) if balance is not None else None,
                    "monthly_payment": float(payment) if payment is not None else None,
                    "payment_frequency": payment_frequency if payment is not None else None,
                    "entry_source": entry_source, "verification_status": verification,
                    "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
                }
                if row is None:
                    entries.append(values)
                else:
                    row.update(values)
                obligations = _obligations_data(record)
                no_debts_key = f"{borrower_type.casefold()}_no_debts_reported"
                obligations[no_debts_key] = False
                obligations["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")


def _render_debt_entries(record: dict[str, Any], application_id: str, entries: list[dict[str, Any]]) -> None:
    if not entries:
        st.info("No debt records have been entered.")
        return
    active_debts = { _debt_identity(item): item for item in _active_debt_entries(entries) }
    for index, item in enumerate(list(entries)):
        identity = str(item.get("debt_identity") or _debt_identity(item))
        key_part = f"{application_id}-{abs(hash(identity))}-{str(item.get('entry_source', 'entry')).casefold().replace(' ', '-')}"
        balance_text = _format_amount(item.get("outstanding_balance")) if item.get("outstanding_balance") is not None else "Not supplied"
        monthly = normalize_monthly_amount(item.get("monthly_payment"), str(item.get("payment_frequency", ""))) if item.get("monthly_payment") is not None else None
        monthly_text = f"{_format_amount(item.get('monthly_payment'))} / {item.get('payment_frequency')} → monthly {_format_amount(monthly)}" if item.get("monthly_payment") is not None else "Not supplied"
        adjustment = " · staff adjustment" if item.get("entry_source") == "Staff adjustment" else " · applicant-declared"
        active = active_debts.get(identity) is item
        active_label = " · used in totals" if active else " · retained as declared history"
        col, status_col, remove_col = st.columns([5, 1.35, 0.8], vertical_alignment="center")
        with col:
            st.markdown(
                f"**{html.escape(str(item.get('debt_type', 'Debt')))}**{adjustment}{active_label}  \n"
                f"{html.escape(str(item.get('lender') or 'Lender not specified'))} · {html.escape(str(item.get('description') or 'Description not specified'))}  \n"
                f"Outstanding balance: {balance_text} · Monthly payment/service: {monthly_text}",
            )
        with status_col:
            current = item.get("verification_status", "Unverified")
            if current not in VERIFICATION_STATES:
                current = "Needs Review"
            selected = st.selectbox("Verification", VERIFICATION_STATES, index=VERIFICATION_STATES.index(current), key=f"debt-row-verification-{key_part}", label_visibility="collapsed")
            if selected != item.get("verification_status"):
                item["verification_status"] = selected
                item["verified_at"] = datetime.now().astimezone().isoformat(timespec="minutes") if selected == "Verified" else None
                _obligations_data(record)["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
        with remove_col:
            if st.button("Remove", key=f"debt-row-remove-{key_part}"):
                entries.remove(item)
                _obligations_data(record)["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
                st.rerun()


def _render_obligations_summary(
    record: dict[str, Any],
    application_id: str,
    borrower_type: str,
    expense_entries: list[dict[str, Any]],
    debt_entries: list[dict[str, Any]],
    expense_categories: Sequence[str],
    part_two_business_expenses: Sequence[Mapping[str, Any]],
) -> None:
    part_two = _financial_analysis_data(record)
    currency = str(part_two.get("currency", "")).strip()
    currency_confirmed = bool(currency and part_two.get("currency_confirmed"))
    if currency_confirmed:
        st.caption(f"Currency: {currency} · recurring amounts are normalized to monthly values; debt balances are point-in-time amounts.")
    else:
        st.warning("Currency is not confirmed for this application. Enter and confirm it in Income & Cash Flow before totals can be aggregated.")

    obligations = _obligations_data(record)
    no_debts_key = f"{borrower_type.casefold()}_no_debts_reported"
    no_debts = bool(obligations.get(no_debts_key, False)) and not debt_entries
    if not debt_entries:
        confirmed_none = st.checkbox(
            f"No existing {('personal debts' if borrower_type == 'Personal' else 'business debts')} were reported",
            value=no_debts,
            key=f"no-debts-{application_id}-{borrower_type.casefold()}",
        )
        if confirmed_none != no_debts:
            obligations[no_debts_key] = confirmed_none
            obligations["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
            no_debts = confirmed_none
    elif no_debts:
        obligations[no_debts_key] = False
        no_debts = False

    summary = calculate_obligations_summary(
        expense_entries,
        debt_entries,
        expense_categories,
        currency_confirmed=currency_confirmed,
        no_debts_reported=no_debts,
        part_two_business_expenses=part_two_business_expenses,
    )
    expense_label = "Total living expenses" if borrower_type == "Personal" else "Total operating expenses"
    expense_value = _format_amount(summary["total_expenses"]) if summary["total_expenses"] is not None else "Incomplete"
    expense_note = (
        f"{len(expense_categories) - len(summary['missing_expense_categories'])} of {len(expense_categories)} categories; "
        f"recorded subtotal {_format_amount(summary['expense_subtotal']) if summary['expense_subtotal'] is not None else 'not aggregable'}"
    )
    payment_value = _format_amount(summary["total_monthly_debt_payments"]) if summary["total_monthly_debt_payments"] is not None else "Incomplete"
    payment_note = (
        "No existing debts reported" if no_debts else
        f"{summary['missing_debt_payment_count']} debt record(s) lack a known monthly payment or frequency"
    )
    balance_value = _format_amount(summary["total_outstanding_debt"]) if summary["total_outstanding_debt"] is not None else "Incomplete"
    balance_note = (
        "No existing debts reported" if no_debts else
        f"{summary['missing_debt_balance_count']} debt record(s) lack a known balance"
    )
    completeness = "Complete" if summary["expense_complete"] and summary["debt_information_complete"] else "Information required"
    _render_value_grid((
        (expense_label, expense_value, f"{expense_note} · {currency if currency_confirmed else 'currency unconfirmed'}"),
        ("Total existing monthly debt payments", payment_value, f"{payment_note} · debt is excluded from expense totals"),
        ("Total outstanding debt balance", balance_value, balance_note),
        ("Financial information completeness", completeness, "Expense categories, debt balance/payment fields, currency and periods"),
    ), columns_count=4)

    missing = list(summary["missing_expense_categories"])
    if summary["invalid_expense_categories"]:
        missing.extend(f"{category} reporting frequency" for category in summary["invalid_expense_categories"])
    if not summary["debt_information_complete"]:
        if not debt_entries and not no_debts:
            missing.append("Existing debts: confirm no debt or enter debt records")
        if summary["missing_debt_balance_count"]:
            missing.append(f"Outstanding balances for {summary['missing_debt_balance_count']} debt record(s)")
        if summary["missing_debt_payment_count"]:
            missing.append(f"Monthly payment and frequency for {summary['missing_debt_payment_count']} debt record(s)")
    if not currency_confirmed:
        missing.append("Confirmed currency")
    if missing:
        st.markdown("**Missing or incomplete information**")
        st.write(" · ".join(missing))
    else:
        st.success("All required Part 3 expense and debt fields are available for this view.")
    return summary


def _render_expenses_debts(record: dict[str, Any], application_id: str) -> None:
    st.markdown("### Expenses & Existing Debts")
    st.caption("Record recurring expenses and debt obligations separately. Applicant declarations and staff adjustments remain traceable, and adjustments supersede declared values in summaries rather than adding to them.")
    borrower_type = _effective_borrower_type(record, application_id)
    if borrower_type is None:
        return
    if _borrower_type(record) == "Not specified":
        st.caption(f"Working analysis view: {borrower_type}. The application itself still has no recorded borrower type.")
    expense_key, debt_key, expense_categories, debt_types = OBLIGATION_COLLECTIONS[borrower_type]
    obligations = _obligations_data(record)
    expense_entries: list[dict[str, Any]] = obligations[expense_key]
    debt_entries: list[dict[str, Any]] = obligations[debt_key]
    part_two = _financial_analysis_data(record)
    part_two_expenses = part_two.get("business_expenses", []) if borrower_type == "Business" else []

    if borrower_type == "Personal":
        st.markdown("#### Living Expenses")
    else:
        st.markdown("#### Business Operating Expenses")
    _render_expense_category_form(record, application_id, expense_entries, expense_categories, label=borrower_type)
    _render_expense_entries(record, application_id, expense_entries, part_two_business_expenses=part_two_expenses)

    debt_label = "Existing Personal Debts" if borrower_type == "Personal" else "Existing Business Debts"
    st.markdown(f"#### {debt_label}")
    _render_debt_entry_form(record, application_id, debt_entries, debt_types, borrower_type=borrower_type)
    _render_debt_entries(record, application_id, debt_entries)

    st.markdown("#### Financial Summary")
    _render_obligations_summary(
        record,
        application_id,
        borrower_type,
        expense_entries,
        debt_entries,
        expense_categories,
        part_two_expenses,
    )

    if borrower_type == "Personal":
        if _has_value(record.get("monthly_expenses")):
            st.caption(f"Original application field: monthly expenses {_format_amount(record.get('monthly_expenses'))}. This is an unclassified aggregate and is not added to the category total.")
        if _has_value(record.get("existing_debt")):
            st.caption(f"Original application field: existing debt {_format_amount(record.get('existing_debt'))}. The source does not specify whether this is a balance or payment, so it is not included in either Part 3 debt total.")
        if _has_value(record.get("other_obligations")):
            st.caption(f"Original application field: other obligations {_format_amount(record.get('other_obligations'))}. Its type and reporting period are unspecified, so it is not included in the Part 3 totals.")
    updated = obligations.get("updated_at")
    st.caption(f"Part 3 analysis last updated: {_format_updated(updated)}. Original applicant fields remain unchanged.")
def _amount(value: Any) -> float | None:
    try:
        amount = float(value)
        return amount if amount >= 0 else None
    except (TypeError, ValueError):
        return None


def _numeric_value(value: Any) -> float | None:
    """Parse a finite numeric result; unlike an input amount, it may be negative."""
    try:
        parsed = float(value)
        return parsed if parsed == parsed and abs(parsed) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _monthly_sources(sources: Sequence[Mapping[str, Any]], amount_field: str) -> list[tuple[Mapping[str, Any], float]]:
    normalized = []
    for source in sources:
        amount = normalize_monthly_amount(source.get(amount_field), str(source.get("frequency", "")))
        if amount is not None:
            normalized.append((source, amount))
    return normalized


def _complete_monthly_source_total(sources: Sequence[Mapping[str, Any]], amount_field: str, *, gross_field: bool = False) -> float | None:
    if not sources:
        return None
    normalized = []
    for source in sources:
        amount = _amount(source.get(amount_field))
        if amount is None:
            return None
        if gross_field and amount == 0 and _amount(source.get("net_amount")) not in (None, 0):
            return None
        monthly = normalize_monthly_amount(amount, str(source.get("frequency", "")))
        if monthly is None:
            return None
        normalized.append(monthly)
    return sum(normalized)


def personal_monthly_income(record: Mapping[str, Any]) -> tuple[float | None, float | None]:
    """Return complete monthly gross/net totals; ambiguous legacy monthly_income is excluded."""
    part_two = record.get("financial_analysis", {})
    part_two = part_two.get("income_cash_flow", {}) if isinstance(part_two, Mapping) else {}
    sources = part_two.get("income_sources", []) if isinstance(part_two, Mapping) else []
    personal_sources = [item for item in sources if isinstance(item, Mapping)]
    if personal_sources:
        gross = _complete_monthly_source_total(personal_sources, "gross_amount", gross_field=True)
        net = _complete_monthly_source_total(personal_sources, "net_amount") if all(item.get("net_amount") is not None for item in personal_sources) else None
        return gross, net
    gross = _amount(record.get("gross_monthly_income"))
    net = _amount(record.get("net_monthly_income"))
    return gross, net


def business_monthly_operating_income(record: Mapping[str, Any]) -> tuple[float | None, float | None, bool]:
    """Return monthly revenue, other operating income, and whether all rows normalize."""
    part_two = record.get("financial_analysis", {})
    part_two = part_two.get("income_cash_flow", {}) if isinstance(part_two, Mapping) else {}
    sources = part_two.get("income_sources", []) if isinstance(part_two, Mapping) else []
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
        sources = []
    rows = [item for item in sources if isinstance(item, Mapping)]
    if not rows:
        monthly_revenue = _amount(record.get("monthly_business_revenue"))
        if monthly_revenue is None and _has_value(record.get("revenue_amount")) and _has_value(record.get("revenue_frequency")):
            monthly_revenue = normalize_monthly_amount(record.get("revenue_amount"), str(record.get("revenue_frequency")))
        other_income = _amount(record.get("monthly_other_operating_income"))
        reviewed = bool(part_two.get("other_operating_income_reviewed")) if isinstance(part_two, Mapping) else False
        if other_income is None and reviewed:
            other_income = 0.0
        return monthly_revenue, other_income, monthly_revenue is not None
    normalized: list[tuple[Mapping[str, Any], float]] = []
    complete = bool(rows)
    for row in rows:
        monthly = normalize_monthly_amount(row.get("gross_amount"), str(row.get("frequency", "")))
        if monthly is None:
            complete = False
        else:
            normalized.append((row, monthly))
    revenue_rows = [(row, value) for row, value in normalized if row.get("type") == "Business revenue"]
    other_rows = [(row, value) for row, value in normalized if row.get("type") == "Other operating income"]
    has_unknown_rows = len(normalized) != len(rows)
    revenue = sum(value for _, value in revenue_rows) if revenue_rows and not has_unknown_rows else None
    reviewed = bool(part_two.get("other_operating_income_reviewed")) if isinstance(part_two, Mapping) else False
    if has_unknown_rows:
        other_income = None
    elif other_rows:
        other_income = sum(value for _, value in other_rows)
    elif reviewed:
        other_income = 0.0
    else:
        other_income = None
    return revenue, other_income, complete


def _render_repayment_capacity(record: dict[str, Any], application_id: str) -> None:
    st.markdown("### Repayment Capacity")
    st.caption("Estimate repayment burden using normalized monthly values from this application’s existing financial analysis.")
    borrower_type = _effective_borrower_type(record, application_id)
    if borrower_type is None:
        return

    part_two = _financial_analysis_data(record)
    analysis_root = record.setdefault("financial_analysis", {})
    if not isinstance(analysis_root, dict):
        analysis_root = {}
        record["financial_analysis"] = analysis_root
    saved = analysis_root.setdefault("repayment_capacity", {})
    if not isinstance(saved, dict):
        saved = {}
        analysis_root["repayment_capacity"] = saved
    saved_calculator = saved.get("calculator", {}) if isinstance(saved.get("calculator"), Mapping) else {}
    currency_default = str(saved_calculator.get("currency") or part_two.get("currency") or "")
    currency = st.text_input(
        "Calculator currency",
        value=currency_default,
        placeholder="Enter currency code or label",
        key=f"capacity-currency-{application_id}",
    ).strip()
    loan_amount_default = saved_calculator.get("loan_amount", record.get("loan_amount"))
    rate_default = saved_calculator.get("annual_interest_rate", record.get("annual_interest_rate"))
    term_default = saved_calculator.get("loan_term_months", record.get("loan_term_months"))
    frequency_default = saved_calculator.get("repayment_frequency", record.get("repayment_frequency", "Monthly"))
    frequency_default = {"Bi-weekly": "Biweekly", "Bi-weekly (every two weeks)": "Biweekly"}.get(frequency_default, frequency_default)
    frequencies = ("Monthly", "Biweekly", "Weekly")
    if frequency_default not in frequencies:
        frequency_default = "Monthly"

    st.markdown("#### Proposed loan calculator")
    st.caption("Calculator values are analysis inputs. They do not change the original application loan request.")
    amount_col, rate_col, term_col, frequency_col = st.columns([1.2, 1, 1, 1.15])
    with amount_col:
        loan_amount = st.number_input(
            f"Loan amount ({currency or 'currency not specified'})",
            min_value=0.0,
            value=float(loan_amount_default) if _amount(loan_amount_default) is not None else None,
            step=500.0,
            format="%.2f",
            key=f"capacity-loan-amount-{application_id}",
        )
    with rate_col:
        annual_rate = st.number_input(
            "Annual interest rate (%)",
            min_value=0.0,
            value=float(rate_default) if _amount(rate_default) is not None else None,
            step=0.1,
            format="%.3f",
            key=f"capacity-annual-rate-{application_id}",
        )
    with term_col:
        term_months = st.number_input(
            "Loan term (months)",
            min_value=1,
            value=int(term_default) if _amount(term_default) is not None and int(float(term_default)) > 0 else None,
            step=1,
            key=f"capacity-term-{application_id}",
        )
    with frequency_col:
        frequency = st.selectbox(
            "Repayment frequency",
            frequencies,
            index=frequencies.index(frequency_default),
            key=f"capacity-frequency-{application_id}",
        )

    calculator = calculate_amortizing_loan(loan_amount, annual_rate, term_months, frequency)
    data_currency = str(part_two.get("currency", "")).strip()
    currency_matches = bool(currency and part_two.get("currency_confirmed") and currency.casefold() == data_currency.casefold())
    if calculator is None:
        st.info("Enter a positive loan amount, a nonnegative annual rate (zero is supported), and a loan term to estimate installments.")
    else:
        _render_capacity_value_grid((
            ("Estimated installment", f"{_format_amount(calculator['installment'])} / {frequency}", currency or "Currency not specified"),
            ("Monthly equivalent", calculator["monthly_installment"], currency or "Currency not specified"),
            ("Total repayment", calculator["total_repayment"], f"{calculator['periods']} installments; excludes fees"),
            ("Total interest", calculator["total_interest"], "Fixed-rate estimate"),
        ), columns_count=4)
    if currency_matches:
        st.caption(f"Calculator currency matches the confirmed Part 2 analysis currency ({data_currency}).")
    else:
        st.warning("The proposed installment is not combined with affordability metrics until the calculator currency matches the confirmed Part 2 currency.")
    st.caption("Assumptions: fixed nominal annual interest rate divided across the selected payment frequency; level payments; term in months converted to the matching number of payment periods; fees and charges excluded.")

    obligations = _obligations_data(record)
    expense_key, debt_key, expense_categories, _ = OBLIGATION_COLLECTIONS[borrower_type]
    expense_entries = obligations[expense_key]
    debt_entries = obligations[debt_key]
    no_debts = bool(obligations.get(f"{borrower_type.casefold()}_no_debts_reported")) and not debt_entries
    part_two_business_expenses = part_two.get("business_expenses", []) if borrower_type == "Business" else []
    obligation_summary = calculate_obligations_summary(
        expense_entries,
        debt_entries,
        expense_categories,
        currency_confirmed=currency_matches,
        no_debts_reported=no_debts,
        part_two_business_expenses=part_two_business_expenses,
    )
    proposed_monthly = calculator.get("monthly_installment") if calculator and currency_matches else None
    missing: list[str] = []

    if borrower_type == "Personal":
        gross_income, net_income = personal_monthly_income(record)
        personal_source_rows = part_two.get("income_sources", [])
        application_currency_matches = bool(
            record.get("currency") and str(record.get("currency")).strip().casefold() == currency.casefold()
        )
        if not personal_source_rows and not application_currency_matches:
            gross_income = None
            net_income = None
        living_expenses = obligation_summary["total_expenses"]
        existing_payments = obligation_summary["total_monthly_debt_payments"]
        if living_expenses is None and not expense_entries and currency_matches and application_currency_matches:
            living_expenses = _amount(record.get("monthly_expenses"))
            legacy_expenses_used = living_expenses is not None
        else:
            legacy_expenses_used = False
        if existing_payments is None and not debt_entries and not no_debts and currency_matches and application_currency_matches:
            existing_payments = _amount(record.get("monthly_debt_payments"))
            legacy_debt_payments_used = existing_payments is not None
        else:
            legacy_debt_payments_used = False
        metrics = calculate_personal_capacity(gross_income, net_income, living_expenses, existing_payments, proposed_monthly)
        gross_note = "Normalized from Part 2 income sources" if gross_income is not None else "Gross amount and frequency required; ambiguous monthly_income is excluded"
        net_note = "Normalized from Part 2 net-source amounts" if net_income is not None else "Net amount and frequency required for every included source"
        expense_note = "Original monthly aggregate used; category detail remains unavailable" if legacy_expenses_used else "Complete Part 3 category total" if living_expenses is not None else "Complete all living expense categories in Part 3"
        debt_note = "Explicit monthly debt-payment field used" if legacy_debt_payments_used else "Complete Part 3 debt payments or confirm no debts" if existing_payments is not None else "Debt payments and frequency, or an explicit no-debt confirmation, required"
        _render_capacity_value_grid((
            ("Gross monthly income", _format_amount(gross_income) if gross_income is not None else "Not available", gross_note),
            ("Net monthly income", _format_amount(net_income) if net_income is not None else "Not available", net_note),
            ("Total monthly living expenses", _format_amount(living_expenses) if living_expenses is not None else "Not available", expense_note),
            ("Existing monthly debt payments", _format_amount(existing_payments) if existing_payments is not None else "Not available", debt_note),
            ("Proposed monthly loan installment", _format_amount(proposed_monthly) if proposed_monthly is not None else "Not available", "Calculator output in confirmed currency"),
            ("Debt-to-Income Ratio (DTI)", f"{metrics['dti_percent']:.2f}%" if metrics["dti_percent"] is not None else "Not available", "Existing monthly debt payments ÷ gross monthly income"),
            ("Debt Service-to-Income Ratio (DSTI)", f"{metrics['dsti_percent']:.2f}%" if metrics["dsti_percent"] is not None else "Not available", "(Existing debt payments + proposed installment) ÷ gross income"),
            ("Disposable income", _format_amount(metrics["disposable_income"]) if metrics["disposable_income"] is not None else "Not available", "Net income − living expenses − existing debt payments"),
            ("Remaining income after proposed loan", _format_amount(metrics["remaining_income"]) if metrics["remaining_income"] is not None else "Not available", "Disposable income − proposed installment"),
        ), columns_count=3)
        if gross_income is None:
            missing.append("Complete gross income and frequency")
        if net_income is None:
            missing.append("Complete net income and frequency")
        if living_expenses is None:
            missing.extend(obligation_summary["missing_expense_categories"])
        if existing_payments is None:
            missing.append("Complete existing debt payments or confirm no existing debts")
        if calculator is None:
            missing.append("Complete proposed loan amount, rate, and term")
        if not currency_matches:
            missing.append("Matching confirmed calculator and financial-data currency")
        result = {
            "gross_monthly_income": gross_income,
            "net_monthly_income": net_income,
            "monthly_living_expenses": living_expenses,
            "existing_monthly_debt_payments": existing_payments,
            "proposed_monthly_installment": proposed_monthly,
            **metrics,
        }
    else:
        revenue, other_income, operating_income_complete = business_monthly_operating_income(record)
        business_source_rows = part_two.get("income_sources", [])
        application_currency_matches = bool(
            record.get("currency") and str(record.get("currency")).strip().casefold() == currency.casefold()
        )
        if not business_source_rows and not application_currency_matches:
            revenue, other_income, operating_income_complete = None, None, False
        active_expenses = obligation_summary["active_expenses"]
        normalized_operating_expenses = [
            normalize_monthly_amount(active_expenses[category].get("amount"), str(active_expenses[category].get("frequency", "")))
            if category in active_expenses else None
            for category in expense_categories
        ]
        expenses_complete = obligation_summary["expense_complete"] and operating_income_complete
        other_income_reviewed = bool(part_two.get("other_operating_income_reviewed"))
        cfads = calculate_business_cfads(
            revenue,
            other_income,
            normalized_operating_expenses,
            expense_categories_complete=expenses_complete,
            other_income_reviewed=other_income_reviewed,
            currency_confirmed=currency_matches,
        )
        existing_service = obligation_summary["total_monthly_debt_payments"]
        legacy_debt_service_used = False
        if existing_service is None and not debt_entries and not no_debts and currency_matches and application_currency_matches:
            existing_service = _amount(record.get("existing_business_debt_service"))
            legacy_debt_service_used = existing_service is not None
        metrics = calculate_business_capacity(cfads, existing_service, proposed_monthly)
        _render_capacity_value_grid((
            ("Cash flow available for debt service", _format_amount(cfads) if cfads is not None else "Not available", "Part 2 operating income − complete Part 3 operating costs"),
            ("Existing monthly business debt service", _format_amount(existing_service) if existing_service is not None else "Not available", "Explicit monthly source field used" if legacy_debt_service_used else "Part 3 business debt records; personal debts excluded"),
            ("Proposed monthly loan installment", _format_amount(proposed_monthly) if proposed_monthly is not None else "Not available", "Calculator output in confirmed currency"),
            ("Total monthly debt service", _format_amount(metrics["total_monthly_debt_service"]) if metrics["total_monthly_debt_service"] is not None else "Not available", "Existing + proposed debt service"),
            ("Debt Service Coverage Ratio (DSCR)", f"{metrics['dscr']:.2f}×" if metrics["dscr"] is not None else "Not available", "Monthly CFADS ÷ total monthly debt service"),
            ("Remaining cash flow after debt service", _format_amount(metrics["remaining_cash_flow"]) if metrics["remaining_cash_flow"] is not None else "Not available", "Monthly CFADS − total monthly debt service"),
        ), columns_count=3)
        if revenue is None:
            missing.append("Complete business revenue sources and reporting frequency")
        if not other_income_reviewed or other_income is None:
            missing.append("Review other operating income (including confirming zero if none)")
        if not obligation_summary["expense_complete"]:
            missing.extend(obligation_summary["missing_expense_categories"])
            missing.extend(f"{category} reporting frequency" for category in obligation_summary["invalid_expense_categories"])
        if not expenses_complete:
            missing.append("Complete operating expense records and periods")
        if existing_service is None:
            missing.append("Complete business debt service or confirm no existing business debts")
        if calculator is None:
            missing.append("Complete proposed loan amount, rate, and term")
        if not currency_matches:
            missing.append("Matching confirmed calculator and financial-data currency")
        result = {
            "monthly_business_revenue": revenue,
            "monthly_other_operating_income": other_income,
            "cfads": cfads,
            **metrics,
        }

    st.markdown("#### Calculation notes")
    if borrower_type == "Personal":
        st.caption("DTI uses gross income. DSTI adds the proposed installment to existing debt payments. Disposable and remaining income use net income, and debt payments are not added into living expenses.")
    else:
        st.caption("DSCR uses monthly CFADS before debt service divided by existing plus proposed monthly debt service. Personal obligations are not included.")

    interpretation_options = (
        "Not assessed — bank policy not configured",
        "Within Defined Policy",
        "Requires Further Review",
        "Potential Affordability Concern",
        "Insufficient Information",
    )
    current_interpretation = saved.get(f"{borrower_type.casefold()}_interpretation", interpretation_options[0])
    if current_interpretation not in interpretation_options:
        current_interpretation = interpretation_options[0]
    interpretation = st.selectbox(
        "Optional analyst interpretation",
        interpretation_options,
        index=interpretation_options.index(current_interpretation),
        key=f"capacity-interpretation-{application_id}-{borrower_type.casefold()}",
        help="No bank policy thresholds are configured. This optional label is a human analyst entry, not an automated decision.",
    )
    st.caption("These categories are not assigned from universal ratio thresholds. Apply the relevant bank policy and human review; this analysis is not a lending decision.")

    saved["calculator"] = {
        "loan_amount": float(loan_amount) if loan_amount is not None else None,
        "annual_interest_rate": float(annual_rate) if annual_rate is not None else None,
        "loan_term_months": int(term_months) if term_months is not None else None,
        "repayment_frequency": frequency,
        "currency": currency,
        "monthly_installment": calculator.get("monthly_installment") if calculator else None,
        "total_repayment": calculator.get("total_repayment") if calculator else None,
        "total_interest": calculator.get("total_interest") if calculator else None,
    }
    saved[borrower_type.casefold()] = {**result, "interpretation": interpretation, "updated_at": datetime.now().astimezone().isoformat(timespec="minutes")}
    if missing:
        st.markdown("#### Missing information")
        st.write(" · ".join(dict.fromkeys(missing)))
    else:
        st.success("All inputs needed for the displayed repayment metrics are available.")
    st.caption(f"Inputs and calculated outputs are stored separately from the original application request. Last updated: {_format_updated(saved[borrower_type.casefold()]['updated_at'])}.")


def _scenario_preset_callback(application_id: str, preset: str) -> None:
    """Set scenario widget state before its widgets are rendered on the next rerun."""
    for suffix in ("income-cut", "expense-rise", "debt-rise", "revenue-cut", "rate-rise"):
        st.session_state[f"scenario-{suffix}-{application_id}"] = 0.0
    if preset == "Income reduction":
        st.session_state[f"scenario-income-cut-{application_id}"] = 20.0
        st.session_state[f"scenario-revenue-cut-{application_id}"] = 20.0
    elif preset == "Higher expenses":
        st.session_state[f"scenario-expense-rise-{application_id}"] = 20.0
    elif preset == "Higher existing debt service":
        st.session_state[f"scenario-debt-rise-{application_id}"] = 20.0
    elif preset == "Higher interest rate":
        st.session_state[f"scenario-rate-rise-{application_id}"] = 2.0
    records = st.session_state.get(APPLICATIONS_KEY, [])
    record = next((item for item in records if isinstance(item, Mapping) and str(item.get("application_id", "")) == application_id), {})
    analysis = record.get("financial_analysis", {}) if isinstance(record, Mapping) else {}
    capacity = analysis.get("repayment_capacity", {}) if isinstance(analysis, Mapping) else {}
    base = capacity.get("calculator", {}) if isinstance(capacity, Mapping) else {}
    if not isinstance(base, Mapping):
        base = {}
    base_amount = record.get("loan_amount") if record.get("loan_amount") is not None else base.get("loan_amount")
    base_rate = record.get("annual_interest_rate") if record.get("annual_interest_rate") is not None else base.get("annual_interest_rate")
    base_term = record.get("loan_term_months") if record.get("loan_term_months") is not None else base.get("loan_term_months")
    amount_key, rate_key, term_key = (f"scenario-amount-{application_id}", f"scenario-rate-{application_id}", f"scenario-term-{application_id}")
    current_amount = st.session_state.get(amount_key, base_amount)
    current_term = st.session_state.get(term_key, base_term)
    if preset == "Original application terms":
        if _amount(base_amount) is not None:
            st.session_state[amount_key] = float(base_amount)
        if _amount(base_rate) is not None:
            st.session_state[rate_key] = float(base_rate)
        if _amount(base_term) is not None and int(float(base_term)) > 0:
            st.session_state[term_key] = min(1200, int(float(base_term)))
        original_frequency = record.get("repayment_frequency", base.get("repayment_frequency", "Monthly"))
        original_frequency = {"Bi-weekly": "Biweekly", "Bi-weekly (every two weeks)": "Biweekly"}.get(original_frequency, original_frequency)
        if original_frequency in {"Monthly", "Biweekly", "Weekly"}:
            st.session_state[f"scenario-frequency-{application_id}"] = original_frequency
    elif preset == "Reduced loan amount" and _amount(current_amount) is not None:
        st.session_state[amount_key] = float(current_amount) * 0.8
    elif preset == "Extended loan term" and _amount(current_term) is not None:
        st.session_state[term_key] = min(1200, int(float(current_term)) + 12)


def _render_scenario_comparison(baseline: Mapping[str, Any], simulated: Mapping[str, Any], borrower_type: str, currency: str) -> None:
    if borrower_type == "Personal":
        rows = (
            ("Gross monthly income", "gross_monthly_income", "amount"),
            ("Net monthly income", "net_monthly_income", "amount"),
            ("Living expenses", "monthly_living_expenses", "amount"),
            ("Existing monthly debt payments", "existing_monthly_debt_payments", "amount"),
            ("Estimated monthly installment", "monthly_installment", "amount"),
            ("DTI", "dti_percent", "percent"),
            ("DSTI", "dsti_percent", "percent"),
            ("Disposable income", "disposable_income", "amount"),
            ("Remaining income", "remaining_income", "amount"),
        )
    else:
        rows = (
            ("Business revenue", "monthly_revenue", "amount"),
            ("Operating expenses", "monthly_operating_expenses", "amount"),
            ("Cash flow available for debt service (CFADS)", "cfads", "amount"),
            ("Existing monthly business debt service", "existing_monthly_debt_service", "amount"),
            ("Proposed monthly installment", "proposed_monthly_installment", "amount"),
            ("Total monthly debt service", "total_monthly_debt_service", "amount"),
            ("DSCR", "dscr", "ratio"),
            ("Remaining cash flow", "remaining_cash_flow", "amount"),
        )
    table = []
    for label, key, kind in rows:
        base_value = baseline.get(key)
        scenario_value = simulated.get(key)
        if key == "monthly_installment":
            base_loan = baseline.get("loan_calculation")
            base_value = base_loan.get("monthly_installment") if isinstance(base_loan, Mapping) else None
        if key == "proposed_monthly_installment":
            scenario_loan = simulated.get("loan_calculation")
            scenario_value = scenario_loan.get("monthly_installment") if isinstance(scenario_loan, Mapping) else None
        delta = scenario_value - base_value if isinstance(base_value, (int, float)) and isinstance(scenario_value, (int, float)) else None
        formatter = (lambda v: f"{v:.2f}%") if kind == "percent" else ((lambda v: f"{v:.2f}×") if kind == "ratio" else (lambda v: f"{currency} {v:,.2f}" if currency else f"{v:,.2f}"))
        table.append({
            "Metric": label,
            "Original / Part 4 baseline": formatter(base_value) if isinstance(base_value, (int, float)) else "Not available",
            "Simulated scenario": formatter(scenario_value) if isinstance(scenario_value, (int, float)) else "Not available",
            "Difference": formatter(delta) if delta is not None else "Not available",
        })
    st.dataframe(table, width="stretch", hide_index=True)


def _render_scenario_analysis(record: dict[str, Any], application_id: str) -> None:
    st.markdown("### Scenario Analysis & Stress Testing")
    st.caption("Interactive hypothetical scenarios based on this application's Part 1–4 analysis. Simulations are not predictions, forecasts, or changes to the original loan request.")
    borrower_type = _effective_borrower_type(record, application_id)
    if borrower_type is None:
        return
    analysis = record.get("financial_analysis", {})
    analysis = analysis if isinstance(analysis, Mapping) else {}
    capacity = analysis.get("repayment_capacity", {})
    capacity = capacity if isinstance(capacity, Mapping) else {}
    baseline = capacity.get(borrower_type.casefold(), {})
    baseline = dict(baseline) if isinstance(baseline, Mapping) else {}
    calculator = capacity.get("calculator", {})
    calculator = dict(calculator) if isinstance(calculator, Mapping) else {}
    baseline["loan_calculation"] = calculate_amortizing_loan(
        calculator.get("loan_amount"), calculator.get("annual_interest_rate"),
        calculator.get("loan_term_months"), calculator.get("repayment_frequency", "Monthly"),
    )
    part_two = _financial_analysis_data(record)
    currency = str(calculator.get("currency") or part_two.get("currency") or "").strip()
    confirmed_currency = bool(part_two.get("currency_confirmed") and currency and str(part_two.get("currency", "")).strip().casefold() == currency.casefold())

    st.markdown("#### Starting terms")
    request = {"Loan amount": record.get("loan_amount"), "Term (months)": record.get("loan_term_months"), "Annual rate (%)": record.get("annual_interest_rate")}
    analysis_terms = {"Loan amount": calculator.get("loan_amount"), "Term (months)": calculator.get("loan_term_months"), "Annual rate (%)": calculator.get("annual_interest_rate")}
    st.caption("Original application request: " + " · ".join(f"{label}: {_format_amount(value) if value is not None else 'Not specified'}" for label, value in request.items()))
    st.caption("Scenario baseline uses the current Part 4 analysis inputs: " + " · ".join(f"{label}: {_format_amount(value) if value is not None else 'Not available'}" for label, value in analysis_terms.items()) + (f" · Frequency: {calculator.get('repayment_frequency', 'Not specified')}"))
    if not confirmed_currency:
        st.warning("Confirm a matching Part 2 and Part 4 currency before interpreting scenario amounts alongside the financial analysis.")

    preset_col, _, _ = st.columns([1.3, 1, 1])
    with preset_col:
        st.selectbox(
            "Apply a stress preset",
            ("Custom scenario", "Original application terms", "Reduced loan amount", "Extended loan term", "Higher interest rate", "Income reduction", "Higher expenses", "Higher existing debt service"),
            key=f"scenario-preset-{application_id}",
            on_change=lambda: _scenario_preset_callback(application_id, st.session_state.get(f"scenario-preset-{application_id}", "Custom scenario")),
        )

    defaults = {
        "loan_amount": calculator.get("loan_amount", record.get("loan_amount")),
        "annual_rate": calculator.get("annual_interest_rate", record.get("annual_interest_rate")),
        "term": calculator.get("loan_term_months", record.get("loan_term_months")),
    }
    loan_col, rate_col, term_col, freq_col = st.columns([1.2, 1, 1, 1.15])
    with loan_col:
        loan_amount = st.number_input(f"Simulated loan amount ({currency or 'currency not specified'})", min_value=0.0, max_value=1_000_000_000_000.0, value=float(defaults["loan_amount"]) if _amount(defaults["loan_amount"]) is not None else None, step=500.0, key=f"scenario-amount-{application_id}")
    with rate_col:
        annual_rate = st.number_input("Simulated annual rate (%)", min_value=0.0, max_value=1000.0, value=float(defaults["annual_rate"]) if _amount(defaults["annual_rate"]) is not None else None, step=0.25, key=f"scenario-rate-{application_id}")
    with term_col:
        term = st.number_input("Simulated loan term (months)", min_value=1, max_value=1200, value=int(float(defaults["term"])) if _amount(defaults["term"]) is not None and int(float(defaults["term"])) > 0 else None, key=f"scenario-term-{application_id}")
    frequencies = ("Monthly", "Biweekly", "Weekly")
    frequency_default = calculator.get("repayment_frequency", record.get("repayment_frequency", "Monthly"))
    frequency_default = {"Bi-weekly": "Biweekly", "Bi-weekly (every two weeks)": "Biweekly"}.get(frequency_default, frequency_default)
    if frequency_default not in frequencies:
        frequency_default = "Monthly"
    with freq_col:
        frequency = st.selectbox("Repayment frequency", frequencies, index=frequencies.index(frequency_default), key=f"scenario-frequency-{application_id}")

    if borrower_type == "Personal":
        st.markdown("#### Personal loan stress inputs")
        a, b, c, d = st.columns(4)
        income_cut = a.number_input("Income reduction (%)", min_value=0.0, max_value=100.0, value=0.0, step=5.0, key=f"scenario-income-cut-{application_id}")
        expense_rise = b.number_input("Living expense increase (%)", min_value=0.0, max_value=1000.0, value=0.0, step=5.0, key=f"scenario-expense-rise-{application_id}")
        debt_rise = c.number_input("Existing debt payment increase (%)", min_value=0.0, max_value=1000.0, value=0.0, step=5.0, key=f"scenario-debt-rise-{application_id}")
        rate_rise = d.number_input("Interest rate increase (percentage points)", min_value=0.0, max_value=1000.0, value=0.0, step=0.5, key=f"scenario-rate-rise-{application_id}")
        simulated = simulate_personal_scenario(
            gross_monthly_income=baseline.get("gross_monthly_income"), net_monthly_income=baseline.get("net_monthly_income"),
            monthly_living_expenses=baseline.get("monthly_living_expenses"), existing_monthly_debt_payments=baseline.get("existing_monthly_debt_payments"),
            loan_amount=loan_amount, annual_interest_rate=annual_rate, loan_term_months=term, repayment_frequency=frequency,
            income_reduction_percent=income_cut, living_expense_increase_percent=expense_rise,
            existing_debt_increase_percent=debt_rise, interest_rate_increase_points=rate_rise,
        )
        simulated.update({"loan_amount": loan_amount, "loan_term_months": term, "repayment_frequency": frequency})
    else:
        st.markdown("#### Business loan stress inputs")
        a, b, c, d = st.columns(4)
        revenue_cut = a.number_input("Business revenue reduction (%)", min_value=0.0, max_value=100.0, value=0.0, step=5.0, key=f"scenario-revenue-cut-{application_id}")
        expense_rise = b.number_input("Operating expense increase (%)", min_value=0.0, max_value=1000.0, value=0.0, step=5.0, key=f"scenario-expense-rise-{application_id}")
        debt_rise = c.number_input("Existing business debt service increase (%)", min_value=0.0, max_value=1000.0, value=0.0, step=5.0, key=f"scenario-debt-rise-{application_id}")
        rate_rise = d.number_input("Interest rate increase (percentage points)", min_value=0.0, max_value=1000.0, value=0.0, step=0.5, key=f"scenario-rate-rise-{application_id}")
        existing_obligations = _obligations_data(record)
        expense_key, debt_key, expense_categories, _ = OBLIGATION_COLLECTIONS["Business"]
        obligation_summary = calculate_obligations_summary(
            existing_obligations[expense_key], existing_obligations[debt_key], expense_categories,
            currency_confirmed=confirmed_currency,
            no_debts_reported=bool(existing_obligations.get("business_no_debts_reported")),
            part_two_business_expenses=part_two.get("business_expenses", []),
        )
        revenue = baseline.get("monthly_business_revenue")
        other_income = baseline.get("monthly_other_operating_income")
        operating_expenses = obligation_summary.get("total_expenses")
        if operating_expenses is None and baseline.get("cfads") is not None and revenue is not None and other_income is not None:
            operating_expenses = revenue + other_income - baseline["cfads"]
        baseline["monthly_operating_expenses"] = operating_expenses
        simulated = simulate_business_scenario(
            monthly_revenue=revenue, monthly_other_operating_income=other_income, monthly_operating_expenses=operating_expenses,
            existing_monthly_debt_service=baseline.get("existing_monthly_debt_service"),
            loan_amount=loan_amount, annual_interest_rate=annual_rate, loan_term_months=term, repayment_frequency=frequency,
            revenue_reduction_percent=revenue_cut, operating_expense_increase_percent=expense_rise,
            existing_debt_service_increase_percent=debt_rise, interest_rate_increase_points=rate_rise,
        )
        simulated.update({"loan_amount": loan_amount, "loan_term_months": term, "repayment_frequency": frequency})

    simulated["loan_calculation"] = simulated.get("loan_calculation") or calculate_amortizing_loan(loan_amount, annual_rate, term, frequency)
    st.markdown("#### Original position vs simulated scenario")
    _render_scenario_comparison(baseline, simulated, borrower_type, currency if confirmed_currency else "")
    if simulated.get("loan_calculation"):
        loan_result = simulated["loan_calculation"]
        _render_capacity_value_grid((
            ("Simulated installment", f"{_format_amount(loan_result['installment'])} / {frequency}", currency or "Currency not specified"),
            ("Total simulated repayment", loan_result["total_repayment"], f"{loan_result['periods']} payments; fees excluded"),
            ("Total simulated interest", loan_result["total_interest"], "Fixed-rate amortization"),
        ), columns_count=3)
    st.caption("The baseline is the current Part 4 analysis position. For business scenarios, CFADS remains revenue plus other operating income less operating expenses; revenue is not treated as profit.")

    snapshots = analysis.setdefault("scenario_analysis", {})
    if not isinstance(snapshots, dict):
        snapshots = {}
        analysis["scenario_analysis"] = snapshots
    by_application = snapshots.setdefault(application_id, [])
    if not isinstance(by_application, list):
        by_application = []
        snapshots[application_id] = by_application
    scenario_name = st.text_input("Scenario name to save", value="Custom stress scenario", key=f"scenario-name-{application_id}")
    if st.button("Save scenario snapshot", key=f"scenario-save-{application_id}"):
        snapshot = {
            "id": str(uuid4()), "name": scenario_name.strip() or "Custom stress scenario", "borrower_type": borrower_type,
            "loan_amount": loan_amount, "annual_interest_rate": annual_rate, "loan_term_months": int(term) if term is not None else None, "repayment_frequency": frequency,
            "stress": ({"income_reduction_percent": income_cut, "living_expense_increase_percent": expense_rise, "existing_debt_increase_percent": debt_rise, "interest_rate_increase_points": rate_rise} if borrower_type == "Personal" else {"revenue_reduction_percent": revenue_cut, "operating_expense_increase_percent": expense_rise, "existing_debt_service_increase_percent": debt_rise, "interest_rate_increase_points": rate_rise}),
            "results": {key: value for key, value in simulated.items() if key != "loan_calculation"},
            "loan_calculation": dict(simulated["loan_calculation"]) if simulated.get("loan_calculation") else None,
            "currency": currency, "created_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        }
        by_application.append(snapshot)
        st.success("Scenario snapshot saved separately from the application request.")
    matching_snapshots = [item for item in by_application if isinstance(item, Mapping) and item.get("borrower_type") == borrower_type]
    if matching_snapshots:
        st.markdown("#### Saved scenario comparisons")
        rows = []
        for item in matching_snapshots:
            result = item.get("results", {})
            main_metric = "remaining_income" if borrower_type == "Personal" else "remaining_cash_flow"
            ratio_metric = "dsti_percent" if borrower_type == "Personal" else "dscr"
            rows.append({
                "Scenario": item.get("name", "Saved scenario"),
                "Loan amount": _format_amount(item.get("loan_amount")),
                "Rate (%)": _format_amount(item.get("annual_interest_rate")),
                "Term (months)": item.get("loan_term_months", "Not available"),
                "Installment / month": _format_amount((item.get("loan_calculation") or {}).get("monthly_installment")) if item.get("loan_calculation") else "Not available",
                "DSTI / DSCR": f"{result[ratio_metric]:.2f}{'%' if borrower_type == 'Personal' else '×'}" if result.get(ratio_metric) is not None else "Not available",
                "Remaining": _format_amount(result.get(main_metric)),
            })
        st.dataframe(rows, width="stretch", hide_index=True)
        remove_id = st.selectbox("Remove saved scenario", [item.get("id") for item in matching_snapshots], format_func=lambda sid: next((item.get("name", "Saved scenario") for item in matching_snapshots if item.get("id") == sid), "Saved scenario"), key=f"scenario-remove-select-{application_id}")
        if st.button("Remove selected scenario", key=f"scenario-remove-{application_id}"):
            snapshots[application_id] = [item for item in by_application if item.get("id") != remove_id]
            st.rerun()


def _render_income_cash_flow(record: dict[str, Any], application_id: str) -> None:
    analysis = _financial_analysis_data(record)
    application_type = _borrower_type(record)
    saved_type = analysis.get("borrower_type")
    borrower_type = application_type if application_type in {"Personal", "Business"} else saved_type

    st.markdown("### Income & Cash Flow")
    st.caption("Review recorded sources, reporting frequency, normalized monthly values, and verification status.")
    if application_type == "Not specified":
        chosen_type = st.selectbox(
            "Analysis view (borrower type is not specified in the application)",
            ("Select borrower type", "Personal", "Business"),
            index=("Select borrower type", "Personal", "Business").index(saved_type or "Select borrower type")
            if (saved_type or "Select borrower type") in ("Select borrower type", "Personal", "Business") else 0,
            key=f"debt-analysis-type-{application_id}",
        )
        if chosen_type in {"Personal", "Business"}:
            if chosen_type != saved_type:
                analysis["borrower_type"] = chosen_type
                analysis["borrower_type_source"] = "Analyst working classification; application record unchanged"
                analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
            borrower_type = chosen_type
        else:
            st.info("Choose a working analysis view to enter personal income or business revenue. This does not change the original application classification.")
            return

    currency_col, confirmation_col = st.columns([1, 2], vertical_alignment="bottom")
    with currency_col:
        currency = st.text_input(
            "Currency code or label",
            value=str(analysis.get("currency", "")),
            placeholder="Required before totals (for example, USD)",
            key=f"debt-analysis-currency-{application_id}",
        ).strip()
    currency_changed = currency != str(analysis.get("currency", ""))
    if currency_changed:
        analysis["currency"] = currency
        analysis["currency_confirmed"] = False
        analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
    with confirmation_col:
        same_currency = st.checkbox(
            "Confirm all amounts entered here use this currency",
            value=False if currency_changed else bool(analysis.get("currency_confirmed", False)),
            key=f"debt-analysis-currency-confirm-{application_id}-{currency or 'unset'}",
            disabled=not currency,
        )
    if (currency, same_currency) != (analysis.get("currency", ""), bool(analysis.get("currency_confirmed", False))):
        analysis["currency"] = currency
        analysis["currency_confirmed"] = same_currency
        analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
    currency_ready = bool(currency and same_currency)
    if not currency_ready:
        st.warning("Enter a currency and confirm it is consistent before viewing aggregate totals or business cash flow.")

    sources: list[dict[str, Any]] = analysis["income_sources"]
    if borrower_type == "Personal":
        st.markdown("#### Personal income sources")
        st.caption("Employment, self-employment/business, and other income are recorded separately. Gross and net amounts are distinct.")
        with st.form(f"personal-income-form-{application_id}", clear_on_submit=True):
            name_col, type_col, gross_col, net_col = st.columns([1.35, 1.1, 1, 1])
            with name_col:
                source_name = st.text_input("Source name", placeholder="Employer or income source")
            with type_col:
                source_type = st.selectbox("Income type", ("Employment", "Self-employment / business", "Other"))
            with gross_col:
                gross_amount = st.number_input("Gross amount", min_value=0.0, step=100.0, format="%.2f")
            with net_col:
                net_amount = st.number_input("Net amount (optional)", min_value=0.0, step=100.0, format="%.2f")
            frequency_col, period_col, add_col = st.columns([1, 1, 1])
            with frequency_col:
                frequency = st.selectbox("Income frequency", INCOME_FREQUENCIES)
            with period_col:
                period = st.date_input("Reporting month (optional)", value=None, key=f"personal-income-period-{application_id}")
            with add_col:
                submitted = st.form_submit_button("Add income source", type="primary", use_container_width=True)
            if submitted:
                if not source_name.strip():
                    st.error("Enter an income source name.")
                elif gross_amount <= 0 and net_amount <= 0:
                    st.error("Enter a gross or net amount greater than zero.")
                else:
                    sources.append({
                        "name": source_name.strip(), "type": source_type, "gross_amount": float(gross_amount),
                        "net_amount": float(net_amount) if net_amount > 0 else None, "frequency": frequency,
                        "period": period.isoformat() if period else None, "verification_status": "Unverified",
                        "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
                    })
                    analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")

        if sources:
            for index, source in enumerate(sources):
                row_col, status_col, remove_col = st.columns([5, 1.3, 0.8], vertical_alignment="center")
                gross_monthly = normalize_monthly_amount(source.get("gross_amount"), source.get("frequency", ""))
                net_monthly = normalize_monthly_amount(source.get("net_amount"), source.get("frequency", "")) if source.get("net_amount") is not None else None
                period_label = f" · {source['period']}" if source.get("period") else ""
                with row_col:
                    st.markdown(
                        f"**{html.escape(str(source.get('name', 'Income source')))}** · {html.escape(str(source.get('type', 'Other')))}{period_label}  \n"
                        f"Gross: {_format_amount(source.get('gross_amount'))} / {source.get('frequency', 'Unknown')} → monthly {_format_amount(gross_monthly)} · "
                        f"Net: {_format_amount(source.get('net_amount')) if source.get('net_amount') is not None else 'Not supplied'}"
                        + (f" → monthly {_format_amount(net_monthly)}" if net_monthly is not None else ""),
                        help="Applicant or staff entered; amounts remain unverified until explicitly reviewed.",
                    )
                with status_col:
                    current_status = source.get("verification_status", "Unverified")
                    if current_status not in VERIFICATION_STATES:
                        current_status = "Needs Review"
                    new_status = st.selectbox(
                        "Verification", VERIFICATION_STATES, index=VERIFICATION_STATES.index(current_status),
                        key=f"income-verification-{application_id}-{index}", label_visibility="collapsed",
                    )
                    if new_status != source.get("verification_status"):
                        source["verification_status"] = new_status
                        source["verified_at"] = datetime.now().astimezone().isoformat(timespec="minutes") if new_status == "Verified" else None
                        analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
                with remove_col:
                    if st.button("Remove", key=f"income-remove-{application_id}-{index}"):
                        sources.pop(index)
                        st.rerun()
        else:
            st.info("No detailed income sources have been recorded. Original application values remain unchanged.")

        if _has_value(record.get("monthly_income")):
            st.caption(f"Existing application field: monthly income {_format_amount(record.get('monthly_income'))}. Its gross/net classification and source frequency are not specified, so it is displayed separately and excluded from normalized totals.")

        gross_sources = _monthly_sources(sources, "gross_amount")
        net_sources = _monthly_sources([item for item in sources if item.get("net_amount") is not None], "net_amount")
        all_gross_normalized = bool(sources) and len(gross_sources) == len(sources)
        gross_total = sum(value for _, value in gross_sources) if all_gross_normalized and currency_ready else None
        net_total = sum(value for _, value in net_sources) if net_sources and currency_ready else None
        _render_value_grid((
            ("Normalized monthly gross income", _format_amount(gross_total) if gross_total is not None else "Not available", currency if currency_ready else "Currency confirmation required"),
            ("Normalized monthly net income", _format_amount(net_total) if net_total is not None else "Not available", "Only sources with a net amount are included"),
            ("Income sources", len(sources), "Stored in this shared application record"),
        ), columns_count=3)
        if gross_sources:
            chart_data = {str(source.get("name", f"Source {i + 1}")): amount for i, (source, amount) in enumerate(gross_sources)}
            st.markdown("#### Monthly gross income by source")
            st.bar_chart(chart_data, y_label=f"Monthly amount ({currency or 'currency not specified'})")

        st.markdown("#### Legacy application income")
        st.caption("Existing `monthly_income` is retained as entered. It is not combined with the source breakdown because its income basis and frequency are unknown.")
        st.caption(f"Analysis last updated: {_format_updated(analysis.get('updated_at'))}")
        return

    # Business borrower branch
    st.markdown("#### Business revenue sources")
    st.caption("Revenue is turnover, not profit. Record each revenue stream with its known reporting frequency.")
    with st.form(f"business-revenue-form-{application_id}", clear_on_submit=True):
        source_col, kind_col, amount_col, frequency_col = st.columns([1.4, 1.2, 1, 1])
        with source_col:
            revenue_name = st.text_input("Revenue source", placeholder="Product line, service, or other operating income")
        with kind_col:
            revenue_type = st.selectbox("Revenue type", ("Business revenue", "Other operating income"))
        with amount_col:
            revenue_amount = st.number_input("Revenue amount", min_value=0.0, step=100.0, format="%.2f")
        with frequency_col:
            revenue_frequency = st.selectbox("Revenue frequency", INCOME_FREQUENCIES, key=f"business-revenue-frequency-{application_id}")
        period_col, revenue_add_col = st.columns([1, 1])
        with period_col:
            revenue_period = st.date_input("Reporting month (optional)", value=None, key=f"business-revenue-period-{application_id}")
        with revenue_add_col:
            revenue_submitted = st.form_submit_button("Add revenue source", type="primary", use_container_width=True)
        if revenue_submitted:
            if not revenue_name.strip():
                st.error("Enter a revenue source name.")
            elif revenue_amount <= 0:
                st.error("Enter a revenue amount greater than zero.")
            else:
                sources.append({
                    "name": revenue_name.strip(), "type": revenue_type, "gross_amount": float(revenue_amount),
                    "frequency": revenue_frequency, "period": revenue_period.isoformat() if revenue_period else None,
                    "verification_status": "Unverified", "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
                })
                analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")

    business_sources = _monthly_sources(sources, "gross_amount")
    all_revenue_normalized = bool(sources) and len(business_sources) == len(sources)
    if sources:
        for index, source in enumerate(sources):
            source_monthly = normalize_monthly_amount(source.get("gross_amount"), source.get("frequency", ""))
            col, status_col, remove_col = st.columns([5, 1.3, 0.8], vertical_alignment="center")
            with col:
                st.markdown(
                    f"**{html.escape(str(source.get('name', 'Revenue source')))}** · {html.escape(str(source.get('type', 'Business revenue')))}  \n"
                    f"{_format_amount(source.get('gross_amount'))} / {source.get('frequency', 'Unknown')} → monthly {_format_amount(source_monthly)}"
                    + (f" · Period {source['period']}" if source.get("period") else ""),
                )
            with status_col:
                current_status = source.get("verification_status", "Unverified")
                if current_status not in VERIFICATION_STATES:
                    current_status = "Needs Review"
                new_status = st.selectbox("Verification", VERIFICATION_STATES, index=VERIFICATION_STATES.index(current_status), key=f"revenue-verification-{application_id}-{index}", label_visibility="collapsed")
                if new_status != source.get("verification_status"):
                    source["verification_status"] = new_status
                    source["verified_at"] = datetime.now().astimezone().isoformat(timespec="minutes") if new_status == "Verified" else None
                    analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
            with remove_col:
                if st.button("Remove", key=f"revenue-remove-{application_id}-{index}"):
                    sources.pop(index)
                    st.rerun()
    else:
        st.info("No business revenue sources have been recorded. Personal income fields are not substituted for business revenue.")

    revenue_sources = [(source, value) for source, value in business_sources if source.get("type") == "Business revenue"]
    other_income_sources = [(source, value) for source, value in business_sources if source.get("type") == "Other operating income"]
    monthly_revenue = sum(value for _, value in revenue_sources) if revenue_sources and all_revenue_normalized and currency_ready else None
    monthly_other_income = sum(value for _, value in other_income_sources) if other_income_sources and all_revenue_normalized and currency_ready else None
    annual_revenue = monthly_revenue * 12 if monthly_revenue is not None else None
    _render_value_grid((
        ("Normalized monthly revenue", _format_amount(monthly_revenue) if monthly_revenue is not None else "Not available", currency if currency_ready else "Currency confirmation required"),
        ("Normalized annual revenue", _format_amount(annual_revenue) if annual_revenue is not None else "Not available", "Monthly normalized revenue × 12"),
        ("Other monthly operating income", _format_amount(monthly_other_income) if monthly_other_income is not None else ("0.00" if analysis.get("other_operating_income_reviewed") and currency_ready else "Not available"), "Reported separately from business revenue"),
        ("Income sources", str(len(sources)), "Revenue is not profit"),
    ), columns_count=4)
    if business_sources:
        st.markdown("#### Monthly operating income by source")
        st.bar_chart({str(source.get("name", f"Source {i + 1}")): amount for i, (source, amount) in enumerate(business_sources)}, y_label=f"Monthly amount ({currency or 'currency not specified'})")

    trend_periods: dict[str, float] = defaultdict(float)
    for source, amount in business_sources:
        period = source.get("period")
        if period:
            trend_periods[str(period)[:7]] += amount
    if len(trend_periods) > 1:
        st.markdown("#### Recorded monthly revenue trend")
        st.line_chart(dict(sorted(trend_periods.items())), y_label=f"Monthly revenue ({currency or 'currency not specified'})")
    else:
        st.caption("No historical revenue trend is shown; at least two explicitly dated reporting periods are required.")

    other_income_reviewed = st.checkbox(
        "Other operating income has been reviewed and all applicable sources are included (zero if none)",
        value=bool(analysis.get("other_operating_income_reviewed", False)),
        key=f"business-other-income-reviewed-{application_id}",
    )
    if other_income_reviewed != bool(analysis.get("other_operating_income_reviewed", False)):
        analysis["other_operating_income_reviewed"] = other_income_reviewed
        analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
    monthly_operating_income = (
        (monthly_revenue or 0.0) + (monthly_other_income or 0.0)
        if all_revenue_normalized and (monthly_revenue is not None or other_income_reviewed) and currency_ready else None
    )

    st.markdown("#### Business operating costs and cash flow")
    st.caption("Monthly cash flow available for debt service (CFADS) is defined here as normalized business revenue plus other operating income minus normalized operating cash costs, including taxes, before existing and proposed debt service. All listed categories must be entered (zero is valid) before CFADS is calculated.")
    expenses: list[dict[str, Any]] = analysis["business_expenses"]
    recorded_categories = {str(item.get("category")) for item in expenses}
    missing_categories = [category for category in BUSINESS_EXPENSE_CATEGORIES if category not in recorded_categories]
    if missing_categories:
        st.warning("Missing operating expense categories: " + ", ".join(missing_categories))
    with st.form(f"business-expense-form-{application_id}", clear_on_submit=True):
        category_col, expense_amount_col, expense_frequency_col = st.columns([1.8, 1, 1])
        available_categories = [item for item in BUSINESS_EXPENSE_CATEGORIES if item not in recorded_categories]
        with category_col:
            expense_category = st.selectbox("Expense category", available_categories or BUSINESS_EXPENSE_CATEGORIES)
        with expense_amount_col:
            expense_amount = st.number_input("Amount (zero if none)", min_value=0.0, step=100.0, format="%.2f", key=f"business-expense-amount-{application_id}")
        with expense_frequency_col:
            expense_frequency = st.selectbox("Expense frequency", INCOME_FREQUENCIES, key=f"business-expense-frequency-{application_id}")
        expense_submitted = st.form_submit_button("Add / update expense", type="primary")
        if expense_submitted:
            existing = next((item for item in expenses if item.get("category") == expense_category), None)
            entry = {"category": expense_category, "amount": float(expense_amount), "frequency": expense_frequency, "verification_status": "Unverified", "updated_at": datetime.now().astimezone().isoformat(timespec="minutes")}
            if existing:
                existing.update(entry)
            else:
                expenses.append(entry)
            analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
    for index, expense in enumerate(list(expenses)):
        amount_monthly = normalize_monthly_amount(expense.get("amount"), expense.get("frequency", ""))
        exp_col, exp_status_col, exp_remove_col = st.columns([5, 1.3, 0.8], vertical_alignment="center")
        with exp_col:
            st.markdown(f"**{html.escape(str(expense.get('category', 'Operating expense')))}** · {_format_amount(expense.get('amount'))} / {expense.get('frequency', 'Unknown')} → monthly {_format_amount(amount_monthly)}")
        with exp_status_col:
            current_status = expense.get("verification_status", "Unverified")
            if current_status not in VERIFICATION_STATES:
                current_status = "Needs Review"
            new_status = st.selectbox("Verification", VERIFICATION_STATES, index=VERIFICATION_STATES.index(current_status), key=f"expense-verification-{application_id}-{index}", label_visibility="collapsed")
            if new_status != expense.get("verification_status"):
                expense["verification_status"] = new_status
                expense["verified_at"] = datetime.now().astimezone().isoformat(timespec="minutes") if new_status == "Verified" else None
                analysis["updated_at"] = datetime.now().astimezone().isoformat(timespec="minutes")
        with exp_remove_col:
            if st.button("Remove", key=f"expense-remove-{application_id}-{index}"):
                expenses.pop(index)
                st.rerun()

    normalized_expenses = [normalize_monthly_amount(item.get("amount"), item.get("frequency", "")) for item in expenses]
    all_expenses_normalized = len(expenses) == len(BUSINESS_EXPENSE_CATEGORIES) and all(value is not None for value in normalized_expenses) and not missing_categories
    cfads = calculate_business_cfads(
        monthly_revenue,
        monthly_other_income,
        normalized_expenses,
        expense_categories_complete=all_expenses_normalized,
        other_income_reviewed=other_income_reviewed,
        currency_confirmed=currency_ready and monthly_operating_income is not None,
    )
    if cfads is not None:
        _render_value_grid((("Monthly CFADS", cfads, "Revenue + other operating income − operating cash costs; before debt service"),), columns_count=1)
    else:
        st.info("CFADS is unavailable until normalized revenue, consistent currency, other operating income is reviewed, and all eight operating cost categories are recorded. Revenue alone or revenue minus one expense category is not treated as cash flow.")
    st.caption(f"Analysis last updated: {_format_updated(analysis.get('updated_at'))}. Values entered here are analysis inputs, not changes to original application fields.")


def _return_to_credit_assessment() -> None:
    st.session_state["active_page"] = "Credit Assessment"
    st.rerun()


def render() -> None:
    """Render the approved Debt & Affordability workspace parts."""
    dark = bool(st.session_state.get("dark_mode", False))
    st.markdown(_page_styles(dark), unsafe_allow_html=True)
    with st.container(key="debt-analysis-page"):
        st.markdown(
            '<div class="financial-workspace-heading"><h1>Financial Analysis</h1>'
            '<p>Evaluate financial capacity, debt obligations, and loan repayment affordability.</p></div>',
            unsafe_allow_html=True,
        )
        records = _records()
        eligible = eligible_applications(records)
        if not eligible:
            st.info("No applications are currently eligible for Financial Analysis. Only records submitted to the assessment workflow are shown.")
            pending = [record for record in records if record not in eligible]
            if pending:
                st.caption(
                    "Applications outside the assessment stage are excluded. Current application statuses: "
                    + ", ".join(sorted({str(record.get('status', 'Not specified')) for record in pending}))
                )
            if st.button("Return to Credit Assessment", key="debt-analysis-return", icon=":material/arrow_back:"):
                _return_to_credit_assessment()
            return

        purpose_values = sorted({str(record.get("loan_purpose") or "Not specified") for record in eligible})
        application_status_values = sorted({str(record.get("status") or "Not specified") for record in eligible})
        assessment_status_values = sorted({_assessment_status(record) for record in eligible} | set(ASSESSMENT_STATUSES))
        borrower_filter_options = BORROWER_TYPES
        search_col, borrower_col, purpose_col, app_status_col, assessment_col = st.columns(
            [2, 1.05, 1.05, 1.15, 1.2], gap="small", vertical_alignment="bottom"
        )
        with search_col:
            search = st.text_input("Search applications", placeholder="Application ID, applicant, or business", key="debt-analysis-search")
        with borrower_col:
            borrower_filter = st.selectbox("Borrower type", borrower_filter_options, key="debt-analysis-borrower-filter")
        with purpose_col:
            purpose_filter = st.selectbox("Loan purpose", ("All",) + tuple(purpose_values), key="debt-analysis-purpose-filter")
        with app_status_col:
            app_status_filter = st.selectbox("Application status", ("All",) + tuple(application_status_values), key="debt-analysis-application-status-filter")
        with assessment_col:
            assessment_filter = st.selectbox("Assessment status", ("All",) + tuple(assessment_status_values), key="debt-analysis-assessment-status-filter")

        filtered = _assessment_filter_records(
            eligible,
            search,
            borrower_filter,
            purpose_filter,
            app_status_filter,
            assessment_filter,
        )
        if not filtered:
            st.info("No eligible applications match the selected search and filters.")
            return

        records_by_id = {str(record.get("application_id")): record for record in filtered}
        options = list(records_by_id)
        preferred_id = st.session_state.get("debt_analysis_application_id") or st.session_state.get("credit_assessment_application_id")
        if preferred_id not in records_by_id:
            preferred_id = options[0]
        selector_key = "debt-analysis-application-selector"
        if st.session_state.get(selector_key) not in records_by_id:
            st.session_state[selector_key] = preferred_id
        selected_id = st.selectbox(
            "Select eligible application",
            options,
            format_func=lambda app_id: f"{_application_name(records_by_id[app_id])} · {app_id}",
            key=selector_key,
        )
        record = records_by_id[selected_id]
        borrower_type = _borrower_type(record)
        assessment_status = _assessment_status(record)

        summary = (
            ("Application ID", selected_id),
            ("Applicant or business", _application_name(record)),
            ("Borrower type", borrower_type),
            ("Requested loan amount", record.get("loan_amount")),
            ("Loan purpose", record.get("loan_purpose", "Not specified")),
            ("Application status", record.get("status", "Not specified")),
            ("Assessment status", assessment_status),
        )
        st.markdown(
            '<div class="da-summary-grid">'
            + "".join(_summary_card(label, value) for label, value in summary)
            + '</div>',
            unsafe_allow_html=True,
        )

        overview_tab, income_tab, expenses_tab, capacity_tab, scenario_tab, report_tab = st.tabs(
            [
                "Financial Overview",
                "Income & Cash Flow",
                "Expenses & Debts",
                "Repayment Capacity",
                "Scenario Analysis",
                "Financial Report",
            ]
        )
        with overview_tab:
            _render_financial_overview(record)
        with income_tab:
            _render_income_cash_flow(record, selected_id)
        with expenses_tab:
            _render_expenses_debts(record, selected_id)
        with capacity_tab:
            _render_repayment_capacity(record, selected_id)
        with scenario_tab:
            _render_scenario_analysis(record, selected_id)
        with report_tab:
            _render_financial_report(record, selected_id)
