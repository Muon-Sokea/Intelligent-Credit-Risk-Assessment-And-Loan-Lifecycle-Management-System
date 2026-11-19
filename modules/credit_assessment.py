"""Shared-record credit underwriting workspace (prototype)."""

from __future__ import annotations

import html
import re
from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

import streamlit as st

from data.loan_applications_demo import create_loan_application_demo_data
from utils.calculations import debt_to_income_ratio, monthly_loan_payment


APPLICATIONS_KEY = "loan_application_records"
APPLICATION_SELECTOR_KEY = "credit_assessment_application_id"
ASSESSMENT_STATUSES = ("Not Started", "In Progress", "Awaiting Information", "Completed")
VERIFICATION_STATUSES = ("Verified", "Needs Review", "Missing", "Needs Resubmission")
DOCUMENT_STATUSES = ("Not Submitted", "Pending Review", "Verified", "Needs Resubmission")
RECOMMENDATIONS = (
    "Recommend Approval",
    "Recommend Rejection",
    "Request Additional Information",
    "Refer for Further Review",
)
ASSESSMENT_ELIGIBLE_APPLICATION_STATUSES = {
    "Under Assessment",
    "Assessment Completed",
    "Pending Decision",
}
DOCUMENT_TYPES = (
    "Identification document",
    "Employment certificate",
    "Salary slip",
    "Bank statement",
    "Existing loan statement",
    "Other supporting document",
)
MODEL_NAMES = (
    "Logistic Regression",
    "Decision Tree",
    "Random Forest",
    "XGBoost / Gradient Boosting",
)
REVIEW_GROUPS = (
    (
        "Personal profile",
        (
            ("Applicant name", "applicant_name"),
            ("Identification number", "identification_number"),
            ("Date of birth", "date_of_birth"),
            ("Gender", "gender"),
            ("Phone", "phone"),
            ("Email", "email"),
            ("Residential address", "address"),
        ),
    ),
    (
        "Employment information",
        (
            ("Employment type", "employment_status"),
            ("Occupation", "occupation"),
            ("Employer", "employer_name"),
            ("Employment duration", "work_experience_years"),
            ("Monthly income", "monthly_income"),
            ("Income source", "income_source"),
            ("Income frequency", "income_frequency"),
        ),
    ),
    (
        "Financial information",
        (
            ("Monthly expenses", "monthly_expenses"),
            ("Existing debt balance", "existing_debt"),
            ("Other financial obligations", "other_obligations"),
            ("Monthly debt payments", "monthly_debt_payments"),
        ),
    ),
    (
        "Loan request information",
        (
            ("Requested amount", "loan_amount"),
            ("Loan purpose", "loan_purpose"),
            ("Repayment term (months)", "loan_term_months"),
            ("Interest rate", "annual_interest_rate_percent"),
            ("Loan product", "loan_product"),
        ),
    ),
)

_REQUIRED_FIELDS = (
    ("Applicant name", "applicant_name"),
    ("Date of birth", "date_of_birth"),
    ("Phone", "phone"),
    ("Email", "email"),
    ("Residential address", "address"),
    ("Employment type", "employment_status"),
    ("Occupation", "occupation"),
    ("Employer", "employer_name"),
    ("Monthly income", "monthly_income"),
    ("Loan amount", "loan_amount"),
    ("Loan purpose", "loan_purpose"),
    ("Repayment term", "loan_term_months"),
)
_FINANCIAL_FIELDS = (
    ("Monthly income", "monthly_income"),
    ("Monthly expenses", "monthly_expenses"),
    ("Existing debt", "existing_debt"),
    ("Other obligations", "other_obligations"),
    ("Loan amount", "loan_amount"),
    ("Repayment term", "loan_term_months"),
)


def _safe_text(value: Any, fallback: str = "Not available") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, (date, datetime)):
        return value.strftime("%b %d, %Y")
    return str(value)


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _display_amount(value: Any, suffix: str = "demo units") -> str:
    amount = _number(value)
    return f"{amount:,.2f} {suffix}" if amount is not None else "Not available"


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def eligible_applications(records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Only expose applications explicitly submitted into the assessment stage."""
    return [
        record
        for record in records
        if record.get("status") in ASSESSMENT_ELIGIBLE_APPLICATION_STATUSES
        or record.get("submitted_for_assessment") is True
    ]


def _assessment_for(record: dict[str, Any]) -> dict[str, Any]:
    assessment = record.get("credit_assessment")
    if not isinstance(assessment, dict):
        assessment = {}
        record["credit_assessment"] = assessment
    current_status = (
        record.get("assessment_status")
        or assessment.get("status")
        or "Not Started"
    )
    if current_status not in ASSESSMENT_STATUSES:
        current_status = "Not Started"
    assessment.setdefault("status", current_status)
    if not isinstance(assessment.get("verification_statuses"), dict):
        assessment["verification_statuses"] = {}
    if not isinstance(assessment.get("documents"), dict):
        assessment["documents"] = {}
    if not isinstance(assessment.get("activity_history"), list):
        assessment["activity_history"] = []
    assessment.setdefault("credit_analysis_status", "Not Started")
    assessment.setdefault("risk_assessment_status", "Not Started")
    for document_type in DOCUMENT_TYPES:
        document = assessment["documents"].get(document_type)
        if isinstance(document, str):
            assessment["documents"][document_type] = {"status": document}
        elif not isinstance(document, dict):
            assessment["documents"][document_type] = {"status": "Not Submitted"}
        else:
            document.setdefault("status", "Not Submitted")
    record["assessment_status"] = current_status
    return assessment


def _log_activity(assessment: dict[str, Any], event: str, detail: str = "") -> None:
    assessment.setdefault("activity_history", []).append(
        {
            "event": event,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    assessment["last_updated"] = datetime.now(timezone.utc).isoformat()


def _set_assessment_status(
    record: dict[str, Any], assessment: dict[str, Any], status: str, event: str
) -> None:
    if assessment.get("status") == status:
        return
    assessment["status"] = status
    record["assessment_status"] = status
    _log_activity(assessment, event, f"Assessment status set to {status}.")


def _record_change(
    record: dict[str, Any],
    assessment: dict[str, Any],
    event: str,
    detail: str,
) -> None:
    _log_activity(assessment, event, detail)
    if assessment.get("status") in ("Not Started", "Awaiting Information"):
        assessment["status"] = "In Progress"
        record["assessment_status"] = "In Progress"
        _log_activity(assessment, "Assessment resumed", "A review item was updated.")


def _completeness(record: Mapping[str, Any]) -> tuple[int, int, list[str]]:
    missing = [label for label, field in _REQUIRED_FIELDS if not _has_value(record.get(field))]
    return len(_REQUIRED_FIELDS) - len(missing), len(_REQUIRED_FIELDS), missing


def _financial_completeness(record: Mapping[str, Any]) -> tuple[int, int]:
    complete = sum(_has_value(record.get(field)) for _, field in _FINANCIAL_FIELDS)
    return complete, len(_FINANCIAL_FIELDS)


def _latest_activity(assessment: Mapping[str, Any]) -> str:
    history = assessment.get("activity_history", [])
    if not history:
        return "No analyst activity recorded"
    event = history[-1]
    value = event.get("timestamp")
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        rendered = timestamp.astimezone().strftime("%b %d, %Y %H:%M")
    except (TypeError, ValueError):
        rendered = "Time unavailable"
    return f'{event.get("event", "Activity recorded")} · {rendered}'


def _activity_time(value: Any) -> tuple[float, str]:
    try:
        if isinstance(value, datetime):
            timestamp = value
        else:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.timestamp(), timestamp.astimezone().strftime("%b %d, %Y %H:%M")
    except (TypeError, ValueError):
        return 0.0, "Time unavailable"


def _page_styles(dark: bool) -> str:
    if dark:
        surface, text, muted, border, soft = "#172338", "#F1F5F9", "#A7B4C5", "#33445C", "#1A2940"
    else:
        surface, text, muted, border, soft = "#FFFFFF", "#1E293B", "#64748B", "#E2E8F0", "#F5F7FA"
    return f"""
    <style>
    .st-key-credit-assessment-page {{ color:{text}; }}
    .st-key-credit-assessment-page .ca-header {{ display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:10px 20px; margin:0 0 18px; }}
    .st-key-credit-assessment-page .ca-title {{ color:{text}; font-size:1.62rem; font-weight:750; letter-spacing:-0.02em; line-height:1.2; margin:0; }}
    .st-key-credit-assessment-page .ca-subtitle {{ color:{muted}; font-size:0.9rem; margin:5px 0 0; }}
    .st-key-credit-assessment-page .ca-panel {{ background:{surface}; border:1px solid {border}; border-radius:13px; padding:15px 17px; margin:0 0 12px; }}
    .st-key-ca-overview-panel {{ background:{surface}; border:1px solid {border}; border-radius:13px; padding:15px 17px; margin-bottom:12px; }}
    .st-key-credit-assessment-page .ca-panel-title {{ color:{text}; font-size:0.98rem; font-weight:700; margin:0 0 4px; }}
    .st-key-credit-assessment-page .ca-panel-copy {{ color:{muted}; font-size:0.78rem; margin:0 0 10px; }}
    .st-key-credit-assessment-page .ca-summary-grid {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:9px; margin:4px 0 17px; }}
    .st-key-credit-assessment-page .ca-summary-card {{ min-width:0; min-height:76px; box-sizing:border-box; border:1px solid {border}; border-radius:11px; background:{surface}; padding:12px 13px; }}
    .st-key-credit-assessment-page .ca-summary-label {{ color:{muted}; font-size:0.69rem; font-weight:650; margin-bottom:6px; }}
    .st-key-credit-assessment-page .ca-summary-value {{ color:{text}; font-size:0.88rem; font-weight:700; line-height:1.25; overflow-wrap:anywhere; }}
    .st-key-credit-assessment-page .ca-metric-card {{ height:100%; min-height:94px; box-sizing:border-box; border:1px solid {border}; border-radius:11px; background:{surface}; padding:13px 14px; }}
    .st-key-credit-assessment-page .ca-metric-label {{ color:{muted}; font-size:0.72rem; font-weight:650; }}
    .st-key-credit-assessment-page .ca-metric-value {{ color:{text}; font-size:1.22rem; font-weight:750; margin-top:6px; line-height:1.15; }}
    .st-key-credit-assessment-page .ca-metric-help {{ color:{muted}; font-size:0.7rem; margin-top:5px; }}
    .st-key-credit-assessment-page .ca-callout {{ border-left:3px solid #2563EB; border-radius:0 8px 8px 0; background:{soft}; padding:10px 13px; color:{text}; font-size:0.81rem; line-height:1.5; margin:7px 0 13px; }}
    .st-key-credit-assessment-page .ca-info-row {{ display:grid; grid-template-columns:minmax(130px,0.8fr) minmax(130px,1.2fr) minmax(150px,1fr); gap:9px; align-items:center; padding:9px 0; border-bottom:1px solid {border}; }}
    .st-key-credit-assessment-page .ca-info-row:last-child {{ border-bottom:0; }}
    .st-key-credit-assessment-page .ca-info-label {{ color:{muted}; font-size:0.76rem; font-weight:650; }}
    .st-key-credit-assessment-page .ca-info-value {{ color:{text}; font-size:0.8rem; overflow-wrap:anywhere; }}
    .st-key-credit-assessment-page .ca-info-source {{ color:{muted}; font-size:0.7rem; }}
    .st-key-credit-assessment-page .ca-signal {{ border:1px solid {border}; border-radius:9px; background:{surface}; padding:10px 12px; margin:0 0 8px; }}
    .st-key-credit-assessment-page .ca-signal-title {{ color:{text}; font-size:0.8rem; font-weight:700; }}
    .st-key-credit-assessment-page .ca-signal-copy {{ color:{muted}; font-size:0.73rem; margin-top:3px; line-height:1.45; }}
    .st-key-credit-assessment-page .ca-status-pill {{ display:inline-flex; border:1px solid {border}; border-radius:999px; background:{soft}; color:{text}; padding:4px 9px; font-size:0.72rem; font-weight:700; }}
    .st-key-credit-assessment-page .ca-empty {{ border:1px dashed {border}; border-radius:11px; background:{soft}; padding:22px; color:{muted}; text-align:center; }}
    .st-key-credit-assessment-page .stTabs [data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid {border}; }}
    .st-key-credit-assessment-page .stTabs [data-baseweb="tab"] {{ color:{muted}; font-weight:650; }}
    .st-key-credit-assessment-page .stTabs [aria-selected="true"] {{ color:#2563EB; }}
    @media (max-width: 1050px) {{ .st-key-credit-assessment-page .ca-summary-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} }}
    @media (max-width: 700px) {{ .st-key-credit-assessment-page .ca-summary-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .st-key-credit-assessment-page .ca-info-row {{ grid-template-columns:1fr; gap:3px; }} }}
    </style>
    """


def _metric_card(label: str, value: Any, detail: str = "") -> str:
    return (
        '<div class="ca-metric-card">'
        f'<div class="ca-metric-label">{html.escape(label)}</div>'
        f'<div class="ca-metric-value">{html.escape(_safe_text(value))}</div>'
        f'<div class="ca-metric-help">{html.escape(detail)}</div></div>'
    )


def _render_metric_row(items: Sequence[tuple[str, Any, str]]) -> None:
    columns = st.columns(len(items), gap="small")
    for column, item in zip(columns, items):
        with column:
            st.markdown(_metric_card(*item), unsafe_allow_html=True)


def _render_heading(title: str, detail: str = "") -> None:
    st.markdown(
        f'<div class="ca-panel-title">{html.escape(title)}</div>'
        + (f'<div class="ca-panel-copy">{html.escape(detail)}</div>' if detail else ""),
        unsafe_allow_html=True,
    )


def _records() -> list[dict[str, Any]]:
    if APPLICATIONS_KEY not in st.session_state:
        st.session_state[APPLICATIONS_KEY] = create_loan_application_demo_data()
    return [
        record
        for record in st.session_state.get(APPLICATIONS_KEY, [])
        if isinstance(record, dict)
    ]


def _application_search_filter(
    records: Sequence[Mapping[str, Any]], query: str, status: str, purpose: str
) -> list[Mapping[str, Any]]:
    normalized = query.strip().casefold()
    result = []
    for record in eligible_applications(records):
        application_id = str(record.get("application_id", ""))
        applicant_name = str(record.get("applicant_name", ""))
        assessment = record.get("credit_assessment", {})
        assessment_status = (
            record.get("assessment_status")
            or (assessment.get("status") if isinstance(assessment, Mapping) else None)
            or "Not Started"
        )
        if status != "All" and assessment_status != status:
            continue
        if purpose != "All" and record.get("loan_purpose") != purpose:
            continue
        if normalized and normalized not in application_id.casefold() and normalized not in applicant_name.casefold():
            continue
        result.append(record)
    return result


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _sync_widget(key: str, value: Any) -> None:
    if key not in st.session_state:
        st.session_state[key] = value


def _render_application_summary(record: Mapping[str, Any], assessment: Mapping[str, Any]) -> None:
    summary = (
        ("Application ID", record.get("application_id", "Not available")),
        ("Applicant", record.get("applicant_name", "Not available")),
        ("Requested amount", _display_amount(record.get("loan_amount"))),
        ("Loan purpose", record.get("loan_purpose", "Not available")),
        ("Application status", record.get("status", "Not available")),
        ("Assessment status", assessment.get("status", "Not Started")),
    )
    st.markdown(
        '<div class="ca-summary-grid">'
        + "".join(
            '<div class="ca-summary-card">'
            f'<div class="ca-summary-label">{html.escape(str(label))}</div>'
            f'<div class="ca-summary-value">{html.escape(_safe_text(value))}</div></div>'
            for label, value in summary
        )
        + '</div>',
        unsafe_allow_html=True,
    )


def _render_overview(record: dict[str, Any], assessment: dict[str, Any]) -> None:
    verified_documents = sum(
        item.get("status") == "Verified"
        for item in assessment.get("documents", {}).values()
        if isinstance(item, Mapping)
    )
    document_total = len(DOCUMENT_TYPES)
    info_done, info_total, missing_fields = _completeness(record)
    financial_done, financial_total = _financial_completeness(record)
    document_progress = verified_documents / document_total if document_total else 0
    info_progress = info_done / info_total if info_total else 0
    progress = (document_progress + info_progress) / 2

    with st.container(key="ca-overview-panel"):
        _render_heading("Assessment overview", "Progress is based on record completeness and explicit document verification statuses.")
        left, right = st.columns([1.2, 1], gap="medium")
        with left:
            _render_metric_row(
                (
                    ("Assessment status", assessment.get("status", "Not Started"), "Analyst workflow status"),
                    ("Documents verified", f"{verified_documents} / {document_total}", "Only explicitly marked Verified"),
                    ("Financial information", f"{financial_done} / {financial_total}", "Income, expenses, debt, and loan fields present"),
                )
            )
            st.progress(progress, text=f"Overall review progress · {progress:.0%}")
        with right:
            _render_metric_row(
                (
                    ("Credit analysis", assessment.get("credit_analysis_status", "Not Started"), "Manual review status"),
                    ("Risk assessment", assessment.get("risk_assessment_status", "Not Started"), "Model not connected"),
                    ("Last assessment activity", _latest_activity(assessment), "Current session record"),
                )
            )

    if missing_fields:
        st.warning("Information requiring review: " + ", ".join(missing_fields))
    not_verified = [
        document_type
        for document_type, item in assessment.get("documents", {}).items()
        if isinstance(item, Mapping) and item.get("status") != "Verified"
    ]
    if not_verified:
        st.info(f"{len(not_verified)} document type(s) are not verified. No document is treated as verified unless a staff member marks it so.")

    start_label = "Resume assessment" if assessment.get("status") == "Awaiting Information" else "Start assessment"
    if assessment.get("status") == "Not Started" or assessment.get("status") == "Awaiting Information":
        if st.button(start_label, key=f"ca-start-{record.get('application_id')}", type="primary", icon=":material/play_arrow:"):
            _set_assessment_status(record, assessment, "In Progress", "Assessment started")
            st.rerun()


def _field_status_default(record: Mapping[str, Any], field: str) -> str:
    return "Needs Review" if _has_value(record.get(field)) else "Missing"


def _render_review_field(
    record: dict[str, Any], assessment: dict[str, Any], label: str, field: str
) -> None:
    statuses = assessment.setdefault("verification_statuses", {})
    default = statuses.get(field, _field_status_default(record, field))
    key = f"ca-verify-{record.get('application_id')}-{field}"
    _sync_widget(key, default)
    value = _safe_text(record.get(field), "Missing from application")
    if isinstance(record.get(field), (float, int)):
        value = f"{record[field]:,.2f} demo units"
    row = st.columns([1.15, 1.5, 1.25], gap="small", vertical_alignment="center")
    with row[0]:
        st.markdown(f'<div class="ca-info-label">{html.escape(label)}</div>', unsafe_allow_html=True)
    with row[1]:
        st.markdown(
            f'<div class="ca-info-value">{html.escape(value)}</div><div class="ca-info-source">Source: applicant-declared application record</div>',
            unsafe_allow_html=True,
        )
    with row[2]:
        new_status = st.selectbox(
            f"{label} verification",
            VERIFICATION_STATUSES,
            key=key,
            label_visibility="collapsed",
        )
    old_status = statuses.get(field, default)
    if new_status != old_status:
        statuses[field] = new_status
        _record_change(
            record,
            assessment,
            "Verification status changed",
            f"{label}: {old_status} → {new_status}.",
        )
        st.session_state["assessment_status"] = assessment["status"]


def _render_documents(record: dict[str, Any], assessment: dict[str, Any]) -> None:
    documents = assessment.setdefault("documents", {})
    _render_heading(
        "Supporting documents",
        "The source application has no document upload field. These are review placeholders; no file is marked verified by default.",
    )
    for document_type in DOCUMENT_TYPES:
        document = documents.setdefault(document_type, {"status": "Not Submitted"})
        if isinstance(document, str):
            document = {"status": document}
            documents[document_type] = document
        status = document.get("status", "Not Submitted")
        key = f"ca-document-{record.get('application_id')}-{_slug(document_type)}"
        _sync_widget(key, status if status in DOCUMENT_STATUSES else "Not Submitted")
        attachment = document.get("file_name") or "No attachment recorded"
        label_col, file_col, status_col = st.columns([1.35, 1.4, 1], gap="small", vertical_alignment="center")
        with label_col:
            st.markdown(f'<div class="ca-info-label">{html.escape(document_type)}</div>', unsafe_allow_html=True)
        with file_col:
            st.markdown(f'<div class="ca-info-value">{html.escape(str(attachment))}</div>', unsafe_allow_html=True)
        with status_col:
            new_status = st.selectbox(
                f"{document_type} status",
                DOCUMENT_STATUSES,
                key=key,
                label_visibility="collapsed",
            )
        old_status = document.get("status", "Not Submitted")
        if new_status != old_status:
            document["status"] = new_status
            _record_change(record, assessment, "Document status changed", f"{document_type}: {old_status} → {new_status}.")
            st.session_state["assessment_status"] = assessment["status"]
            if new_status == "Verified" and not document.get("file_name"):
                st.warning(f"{document_type} has no recorded attachment. The status reflects the staff selection only.")


def _render_applicant_review(record: dict[str, Any], assessment: dict[str, Any]) -> None:
    st.caption("Information is displayed from the selected Loan Applications record. Verification status is stored with that same record.")
    for group_name, fields in REVIEW_GROUPS:
        with st.expander(group_name, expanded=group_name in ("Personal profile", "Employment information")):
            for label, field in fields:
                _render_review_field(record, assessment, label, field)
    with st.expander("Supporting documents", expanded=True):
        _render_documents(record, assessment)


def _financial_data(record: Mapping[str, Any]) -> dict[str, Any]:
    income = _number(record.get("monthly_income"))
    debt_payments = _number(record.get("monthly_debt_payments"))
    dti = None
    if income is not None and income > 0 and debt_payments is not None and debt_payments >= 0:
        dti = debt_to_income_ratio(debt_payments, income) * 100

    annual_rate = _number(record.get("annual_interest_rate_percent"))
    term = _number(record.get("loan_term_months"))
    amount = _number(record.get("loan_amount"))
    installment = _number(record.get("estimated_monthly_installment"))
    if (
        installment is None
        and amount is not None
        and amount >= 0
        and annual_rate is not None
        and annual_rate >= 0
        and term
        and term > 0
    ):
        installment = monthly_loan_payment(amount, annual_rate / 100, int(term))
    return {
        "income": income,
        "debt_payments": debt_payments,
        "dti": dti,
        "annual_rate": annual_rate,
        "term": term,
        "amount": amount,
        "installment": installment,
    }


def _render_financial_analysis(
    record: dict[str, Any], assessment: dict[str, Any]
) -> None:
    st.markdown(
        '<div class="ca-callout"><strong>Source and verification:</strong> Financial amounts come from the application record and remain applicant-declared until staff update verification. Currency is not specified in the source data; amounts are shown in demo units.</div>',
        unsafe_allow_html=True,
    )
    financial = _financial_data(record)
    income_status = assessment.get("verification_statuses", {}).get("monthly_income", "Needs Review")
    st.markdown("#### Income and employment")
    _render_metric_row(
        (
            ("Monthly income", _display_amount(financial["income"], "demo units / month"), f"Verification: {income_status}"),
            ("Income frequency", record.get("income_frequency", "Not available"), "Not specified in source record"),
            ("Employment type", record.get("employment_status", "Not available"), "Applicant-declared"),
            ("Employment duration", f"{_safe_text(record.get('work_experience_years'))} years" if _has_value(record.get("work_experience_years")) else "Not available", "Applicant-declared"),
        )
    )

    st.markdown("#### Existing debt and credit history")
    _render_metric_row(
        (
            ("Existing debt balance", _display_amount(record.get("existing_debt")), "Balance field; not a monthly payment"),
            ("Monthly debt payments", _display_amount(financial["debt_payments"], "demo units / month"), "Not separately collected in current records"),
            ("Debt-to-Income Ratio", f"{financial['dti']:.1f}%" if financial["dti"] is not None else "Not available", "Needs monthly debt payments and monthly income"),
            ("Credit score", "Not available", "No bureau or score source connected"),
        )
    )
    st.caption(f"Other financial obligations: {_display_amount(record.get('other_obligations'), 'demo units / month')} · applicant-declared.")
    st.markdown("#### Proposed loan")
    annual_rate_text = f"{financial['annual_rate']:.2f}%" if financial["annual_rate"] is not None else "Not available"
    installment_text = _display_amount(financial["installment"], "demo units / month")
    _render_metric_row(
        (
            ("Requested amount", _display_amount(financial["amount"]), "Loan Applications record"),
            ("Purpose", record.get("loan_purpose", "Not available"), "Loan Applications record"),
            ("Interest rate", annual_rate_text, "No demo rate substituted"),
            ("Term", f"{financial['term']:g} months" if financial["term"] is not None else "Not available", "Requested term"),
            ("Estimated installment", installment_text, "Shown only when source rate or installment is available"),
        )
    )
    st.caption("Credit history, prior borrowing, repayment history, and delinquency information: Not available in the current application dataset.")
    st.markdown("#### Analyst review controls")
    analysis_col, risk_col = st.columns(2, gap="small")
    for column, key, label in (
        (analysis_col, "credit_analysis_status", "Financial and credit analysis status"),
        (risk_col, "risk_assessment_status", "Human risk assessment status"),
    ):
        with column:
            current = assessment.get(key, "Not Started")
            control_key = f"ca-{record.get('application_id')}-{key}"
            _sync_widget(control_key, current if current in ASSESSMENT_STATUSES else "Not Started")
            selected = st.selectbox(label, ASSESSMENT_STATUSES, key=control_key)
            if selected != current:
                assessment[key] = selected
                _record_change(record, assessment, f"{label} updated", f"Status set to {selected}.")
                st.session_state["assessment_status"] = assessment["status"]

    if st.button("Open Debt & Affordability analysis", key="ca-open-debt-analysis", icon=":material/open_in_new:"):
        st.session_state["debt_analysis_application_id"] = record.get("application_id")
        st.session_state["active_page"] = "Debt & Affordability"
        st.rerun()


def _render_risk_assessment(record: dict[str, Any], assessment: dict[str, Any]) -> None:
    _render_metric_row(
        (
            ("Default probability", "Not available", "No trained model connected"),
            ("Predicted risk category", "Not available", "No model prediction recorded"),
            ("Model name and version", "Not connected", "Future supervised-model output"),
        )
    )
    st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
    _render_metric_row(
        (
            ("Important risk factors", "Not available", "No model explanation generated"),
            ("Model explanation", "Not available", "No model output to explain"),
        )
    )
    st.markdown("#### Planned supervised models")
    model_rows = [
        {"Model": model, "Output status": "Not connected", "Version": "Not available", "Default probability": "Not available"}
        for model in MODEL_NAMES
    ]
    st.dataframe(model_rows, hide_index=True, width="stretch")
    source_label = record.get("risk_level")
    if source_label and source_label != "Not Assessed":
        st.info(f"Stored source-record risk label: **{source_label}**. This is demo record data, not an ML prediction or current analyst conclusion.")

    st.markdown("#### K-Means borrower segmentation")
    _render_metric_row(
        (
            ("Assigned cluster", "Not assigned", "Clustering model not connected"),
            ("Cluster description", "Not available", "No borrower segments configured"),
            ("Borrower characteristics", "Not available", "No cluster output recorded"),
        )
    )
    st.caption("K-Means is an unsupervised segmentation method. It will not produce a default probability.")

    st.markdown("#### Information available to an analyst")
    factual_items = (
        ("Applicant data", f"Income: {_display_amount(record.get('monthly_income'), 'demo units / month')}; employment: {_safe_text(record.get('employment_status'))}. Applicant-declared fields."),
        ("Calculated metrics", "DTI is unavailable until monthly debt payments are recorded. No affordability estimate is substituted here."),
        ("ML predictions", "None. Planned models are not connected."),
        ("Human observations", assessment.get("analyst_comments") or "No analyst observations recorded yet."),
    )
    for label, text in factual_items:
        st.markdown(
            f'<div class="ca-signal"><div class="ca-signal-title">{html.escape(label)}</div><div class="ca-signal-copy">{html.escape(text)}</div></div>',
            unsafe_allow_html=True,
        )


def _findings_form_key(application_id: str) -> str:
    return f"ca-findings-form-{_slug(application_id)}"


def _render_findings(record: dict[str, Any], assessment: dict[str, Any]) -> None:
    application_id = str(record.get("application_id", "application"))
    fields = (
        ("positive_findings", "Positive findings", "Record only findings supported by available application data or reviewed documents."),
        ("negative_findings", "Negative findings", "List concerns and include the field or document that supports them."),
        ("risk_mitigation", "Risk mitigation", "Possible follow-up or mitigation steps for consideration."),
        ("analyst_comments", "Analyst comments", "Professional observations for this assessment record."),
        ("recommendation_justification", "Recommendation justification", "Required before submitting a recommendation."),
    )
    for key, _, _ in fields:
        widget_key = f"ca-{_slug(application_id)}-{key}"
        _sync_widget(widget_key, assessment.get(key, ""))
    recommendation_key = f"ca-{_slug(application_id)}-recommendation"
    _sync_widget(recommendation_key, assessment.get("recommendation") or "Select recommendation")

    st.markdown("Record human findings and a recommendation. The recommendation is not the final lending decision.")
    with st.form(key=_findings_form_key(application_id)):
        columns = st.columns(2, gap="medium")
        with columns[0]:
            st.text_area(fields[0][1], key=f"ca-{_slug(application_id)}-positive_findings", help=fields[0][2], height=110)
            st.text_area(fields[1][1], key=f"ca-{_slug(application_id)}-negative_findings", help=fields[1][2], height=110)
            st.text_area(fields[2][1], key=f"ca-{_slug(application_id)}-risk_mitigation", help=fields[2][2], height=100)
        with columns[1]:
            st.text_area(fields[3][1], key=f"ca-{_slug(application_id)}-analyst_comments", help=fields[3][2], height=180)
            st.selectbox("Recommendation", ("Select recommendation",) + RECOMMENDATIONS, key=recommendation_key)
            st.text_area(fields[4][1], key=f"ca-{_slug(application_id)}-recommendation_justification", help=fields[4][2], height=110)
        save_clicked, submit_clicked = st.columns(2, gap="small")
        with save_clicked:
            save_findings = st.form_submit_button("Save findings", width="stretch")
        with submit_clicked:
            submit_recommendation = st.form_submit_button("Submit recommendation", type="primary", width="stretch")

    values = {
        key: st.session_state[f"ca-{_slug(application_id)}-{key}"]
        for key, _, _ in fields
    }
    recommendation = st.session_state[recommendation_key]
    if save_findings or submit_recommendation:
        assessment.update(values)
    if save_findings:
        _record_change(record, assessment, "Findings recorded", "Analyst findings and comments saved.")
        st.session_state["assessment_status"] = assessment["status"]
        st.success("Assessment findings saved in the shared application record.")
    if submit_recommendation:
        justification = values["recommendation_justification"].strip()
        if recommendation == "Select recommendation":
            st.error("Select a recommendation before submitting.")
        elif not justification:
            st.error("A written justification is required before submitting a recommendation.")
        else:
            assessment["recommendation"] = recommendation
            next_status = "Awaiting Information" if recommendation == "Request Additional Information" else "Completed"
            status_event = "Assessment completed" if next_status == "Completed" else "Information requested"
            _set_assessment_status(record, assessment, next_status, status_event)
            _log_activity(assessment, "Recommendation submitted", f"{recommendation}. Final lending decision remains separate.")
            updated_at = datetime.now(timezone.utc).isoformat()
            record["latest_assessment_summary"] = {
                "assessment_status": next_status,
                "recommendation": recommendation,
                "justification": justification,
                "updated_at": updated_at,
                "source": "human analyst recommendation; not final lending decision",
            }
            st.session_state["assessment_status"] = next_status
            st.success("Recommendation recorded. This is not the final lending decision.")


def _render_timeline(record: Mapping[str, Any], assessment: Mapping[str, Any]) -> None:
    application_history = record.get("history", [])
    assessment_history = assessment.get("activity_history", [])
    if not application_history and not assessment_history:
        st.markdown('<div class="ca-empty">No application or assessment activity has been recorded.</div>', unsafe_allow_html=True)
        return

    rows: list[dict[str, Any]] = []
    for event in application_history:
        order, rendered_time = _activity_time(event.get("timestamp"))
        rows.append(
            {
                "Source": "Application record · demo data",
                "Activity": _safe_text(event.get("event"), "Application activity"),
                "Detail": _safe_text(event.get("detail"), "—"),
                "Time": rendered_time,
                "_order": order,
            }
        )
    for event in assessment_history:
        order, rendered_time = _activity_time(event.get("timestamp"))
        rows.append(
            {
                "Source": "Assessment workspace · session record",
                "Activity": _safe_text(event.get("event"), "Assessment activity"),
                "Detail": _safe_text(event.get("detail"), "—"),
                "Time": rendered_time,
                "_order": order,
            }
        )
    rows.sort(key=lambda row: row["_order"])
    for row in rows:
        row.pop("_order", None)
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption("Activity is stored in this Streamlit session. It is not a production audit log and does not identify individual users.")


def _go_to_loan_applications() -> None:
    st.session_state["active_page"] = "Loan Applications"
    st.session_state["loan_application_view"] = "list"
    st.rerun()


def render() -> None:
    """Render a human-led assessment workspace over shared application records."""
    dark = bool(st.session_state.get("dark_mode", False))
    st.markdown(_page_styles(dark), unsafe_allow_html=True)
    with st.container(key="credit-assessment-page"):
        st.markdown(
            '<div class="ca-header"><div><h1 class="ca-title">Assessment Workspace</h1>'
            '<p class="ca-subtitle">Review applicant information, evaluate credit risk, and prepare assessment recommendations.</p></div></div>',
            unsafe_allow_html=True,
        )
        records = _records()
        eligible = eligible_applications(records)
        if not eligible:
            st.info("No applications have been submitted for Credit Assessment. Only applications in the assessment workflow appear here.")
            if st.button("Open Loan Applications", key="ca-open-applications", icon=":material/arrow_forward:"):
                _go_to_loan_applications()
            return

        search_col, status_col, purpose_col = st.columns([2, 1.15, 1.1], gap="small", vertical_alignment="bottom")
        with search_col:
            query = st.text_input("Search applications", placeholder="Application ID or applicant name", key="ca-application-search")
        with status_col:
            assessment_status_filter = st.selectbox("Assessment status", ("All",) + ASSESSMENT_STATUSES, key="ca-assessment-status-filter")
        purposes = sorted({str(record.get("loan_purpose")) for record in eligible if record.get("loan_purpose")})
        with purpose_col:
            purpose_filter = st.selectbox("Loan purpose", ("All",) + tuple(purposes), key="ca-purpose-filter")

        filtered = _application_search_filter(eligible, query, assessment_status_filter, purpose_filter)
        if not filtered:
            st.info("No submitted applications match these assessment filters.")
            return
        records_by_id = {str(record.get("application_id")): record for record in filtered}
        application_ids = list(records_by_id)
        selected_id = st.selectbox(
            "Select submitted application",
            application_ids,
            format_func=lambda application_id: f"{records_by_id[application_id].get('applicant_name', 'Applicant')} · {application_id}",
            key=APPLICATION_SELECTOR_KEY,
        )
        record = records_by_id[selected_id]
        assessment = _assessment_for(record)
        _render_application_summary(record, assessment)

        overview_tab, review_tab, finance_tab, risk_tab, findings_tab, history_tab = st.tabs(
            [
                "Assessment Overview",
                "Applicant & Documents",
                "Financial & Credit Analysis",
                "Credit Risk Assessment",
                "Findings & Recommendation",
                "Assessment History",
            ]
        )
        with overview_tab:
            _render_overview(record, assessment)
        with review_tab:
            _render_applicant_review(record, assessment)
        with finance_tab:
            _render_financial_analysis(record, assessment)
        with risk_tab:
            _render_risk_assessment(record, assessment)
        with findings_tab:
            _render_findings(record, assessment)
        with history_tab:
            _render_timeline(record, assessment)
