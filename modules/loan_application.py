"""Loan application management using clearly identified demonstration records."""

from __future__ import annotations

import csv
import html
import io
import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

import streamlit as st
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from data.loan_applications_demo import create_loan_application_demo_data


APPLICATIONS_KEY = "loan_application_records"
VIEW_KEY = "loan_application_view"
SELECTED_ID_KEY = "loan_application_selected_id"
FORM_ID_KEY = "loan_application_form_id"
FORM_STEP_KEY = "loan_application_form_step"
PAGE_SIZE = 8
EXPORT_COLUMNS = (
    ("Application ID", "application_id"),
    ("Applicant", "applicant_name"),
    ("Application Date", "application_date"),
    ("Loan Amount", "loan_amount"),
    ("Loan Purpose", "loan_purpose"),
    ("Risk Level", "risk_level"),
    ("Status", "status"),
)

STATUSES = ("Pending", "Under Review", "Under Assessment", "Approved", "Rejected")
PURPOSES = ("Personal", "Business", "Education", "Home", "Other")
GENDERS = ("Female", "Male", "Non-binary", "Prefer not to say")
EMPLOYMENT_STATUSES = (
    "Full-time",
    "Part-time",
    "Contract",
    "Self-employed",
    "Unemployed",
    "Retired",
    "Student",
)
REPAYMENT_FREQUENCIES = ("Weekly", "Bi-weekly", "Monthly")

_FILTER_STATUS_KEY = "loan_applications_status_filter"
_FILTER_PURPOSE_KEY = "loan_applications_purpose_filter"
_FILTER_DATE_KEY = "loan_applications_date_filter"
_FILTER_SEARCH_KEY = "loan_applications_search"
_FILTER_PAGE_KEY = "loan_applications_page"

_FORM_DEFAULTS: dict[str, Any] = {
    "full_name": "",
    "date_of_birth": None,
    "gender": None,
    "phone": "",
    "email": "",
    "address": "",
    "employment_status": None,
    "occupation": "",
    "employer": "",
    "work_experience_years": 0.0,
    "monthly_income": 0.0,
    "monthly_expenses": 0.0,
    "existing_debt": 0.0,
    "other_obligations": 0.0,
    "loan_amount": 0.0,
    "loan_purpose": None,
    "loan_term_months": 1,
    "repayment_frequency": None,
}

_FORM_STEP_FIELDS = {
    1: ("full_name", "date_of_birth", "gender", "phone", "email", "address"),
    2: (
        "employment_status",
        "occupation",
        "employer",
        "work_experience_years",
        "monthly_income",
    ),
    3: ("monthly_expenses", "existing_debt", "other_obligations"),
    4: ("loan_amount", "loan_purpose", "loan_term_months", "repayment_frequency"),
}

_REQUIRED_FIELDS = {
    "full_name": "Full name",
    "date_of_birth": "Date of birth",
    "gender": "Gender",
    "phone": "Phone number",
    "email": "Email address",
    "address": "Residential address",
    "employment_status": "Employment status",
    "occupation": "Occupation",
    "employer": "Employer name",
    "loan_purpose": "Loan purpose",
    "repayment_frequency": "Repayment frequency",
}

_FORM_TO_RECORD = {
    "full_name": "applicant_name",
    "date_of_birth": "date_of_birth",
    "gender": "gender",
    "phone": "phone",
    "email": "email",
    "address": "address",
    "employment_status": "employment_status",
    "occupation": "occupation",
    "employer": "employer_name",
    "work_experience_years": "work_experience_years",
    "monthly_income": "monthly_income",
    "monthly_expenses": "monthly_expenses",
    "existing_debt": "existing_debt",
    "other_obligations": "other_obligations",
    "loan_amount": "loan_amount",
    "loan_purpose": "loan_purpose",
    "loan_term_months": "loan_term_months",
    "repayment_frequency": "repayment_frequency",
}


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def _assessment_summary(value: Any) -> str | None:
    """Extract a stored assessment summary without deriving a new risk value."""
    if isinstance(value, Mapping):
        for field in (
            "summary",
            "risk_summary",
            "predicted_risk_level",
            "risk_level",
            "risk_grade",
        ):
            summary = value.get(field)
            if summary not in (None, ""):
                return str(summary).strip()
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _assessment_timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
    else:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def latest_risk_summary(record: Mapping[str, Any]) -> str:
    """Return the newest stored risk summary, or the legacy label / fallback."""
    latest = _assessment_summary(record.get("latest_risk_assessment"))
    if latest:
        return latest

    assessments = record.get("risk_assessments", ())
    if isinstance(assessments, Mapping):
        assessments = [assessments]
    if isinstance(assessments, Sequence) and not isinstance(assessments, (str, bytes)):
        candidates = []
        for index, assessment in enumerate(assessments):
            summary = _assessment_summary(assessment)
            if not summary:
                continue
            timestamp = 0.0
            if isinstance(assessment, Mapping):
                timestamp = _assessment_timestamp(
                    assessment.get("assessed_at")
                    or assessment.get("created_at")
                    or assessment.get("timestamp")
                )
            candidates.append((timestamp, index, summary))
        if candidates:
            return max(candidates)[2]

    legacy_summary = _assessment_summary(record.get("risk_level"))
    return legacy_summary or "Not Assessed"


def filter_applications(
    records: Iterable[Mapping[str, Any]],
    query: str = "",
    status: str = "All",
    purpose: str = "All",
    date_range: Sequence[date] | None = None,
) -> list[Mapping[str, Any]]:
    """Return records matching the list toolbar without mutating the source."""
    normalized_query = query.strip().casefold()
    numeric_query = re.sub(r"\D", "", normalized_query)
    start_date = _as_date(date_range[0]) if date_range else None
    end_date = _as_date(date_range[-1]) if date_range else None
    matches: list[Mapping[str, Any]] = []

    for record in records:
        if status != "All" and record.get("status") != status:
            continue
        if purpose != "All" and record.get("loan_purpose") != purpose:
            continue

        application_date = _as_date(record.get("application_date"))
        if start_date and application_date and application_date < start_date:
            continue
        if end_date and application_date and application_date > end_date:
            continue
        if (start_date or end_date) and application_date is None:
            continue

        if normalized_query:
            searchable = " ".join(
                str(record.get(field, ""))
                for field in ("applicant_name", "application_id", "phone")
            ).casefold()
            normalized_phone = re.sub(r"\D", "", str(record.get("phone", "")))
            if normalized_query not in searchable and not (
                numeric_query and numeric_query in normalized_phone
            ):
                continue
        matches.append(record)

    return sorted(
        matches,
        key=lambda item: _as_date(item.get("application_date")) or date.min,
        reverse=True,
    )


def summarize_applications(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    records = list(records)
    return {
        "total": len(records),
        "pending_review": sum(
            record.get("status") in ("Pending", "Under Review") for record in records
        ),
        "under_assessment": sum(
            record.get("status") == "Under Assessment" for record in records
        ),
        "completed": sum(
            record.get("status") in ("Approved", "Rejected") for record in records
        ),
    }


def generate_application_id(records: Iterable[Mapping[str, Any]], today: date | None = None) -> str:
    """Create the next unique, year-prefixed demonstration application reference."""
    year = (today or date.today()).year
    prefix = f"APP-{year}-"
    highest = 0
    for record in records:
        application_id = str(record.get("application_id", ""))
        if application_id.startswith(prefix):
            suffix = application_id[len(prefix) :]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:04d}"


def validate_application_form(values: Mapping[str, Any]) -> list[str]:
    errors = [
        f"{label} is required."
        for field, label in _REQUIRED_FIELDS.items()
        if not str(values.get(field, "") or "").strip()
    ]

    email = str(values.get("email", "") or "").strip()
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append("Enter a valid email address.")

    phone = re.sub(r"\D", "", str(values.get("phone", "")))
    if values.get("phone") and len(phone) < 7:
        errors.append("Enter a valid phone number.")

    numeric_fields = (
        ("work_experience_years", "Work experience"),
        ("monthly_income", "Monthly income"),
        ("monthly_expenses", "Monthly expenses"),
        ("existing_debt", "Existing debt"),
        ("other_obligations", "Other financial obligations"),
        ("loan_amount", "Requested loan amount"),
    )
    for field, label in numeric_fields:
        try:
            value = float(values.get(field, 0) or 0)
        except (TypeError, ValueError):
            errors.append(f"{label} must be a number.")
            continue
        if not math.isfinite(value):
            errors.append(f"{label} must be a finite number.")
        elif value < 0:
            errors.append(f"{label} cannot be negative.")
        elif field in ("monthly_income", "loan_amount") and value <= 0:
            errors.append(f"{label} must be greater than zero.")

    try:
        loan_term = float(values.get("loan_term_months", 0) or 0)
        if not math.isfinite(loan_term) or not loan_term.is_integer():
            errors.append("Loan term must be a whole number.")
        elif loan_term <= 0:
            errors.append("Loan term must be greater than zero.")
    except (TypeError, ValueError):
        errors.append("Loan term must be a whole number.")

    birth_date = _as_date(values.get("date_of_birth"))
    if values.get("date_of_birth") and birth_date is None:
        errors.append("Date of birth is invalid.")
    elif birth_date and birth_date > date.today():
        errors.append("Date of birth cannot be in the future.")

    return errors


def _ensure_state() -> None:
    state = st.session_state
    if APPLICATIONS_KEY not in state:
        state[APPLICATIONS_KEY] = create_loan_application_demo_data()
    state.setdefault(VIEW_KEY, "list")
    state.setdefault(SELECTED_ID_KEY, None)
    state.setdefault(FORM_ID_KEY, None)
    state.setdefault(FORM_STEP_KEY, 1)
    state.setdefault(_FILTER_SEARCH_KEY, "")
    state.setdefault(_FILTER_STATUS_KEY, "All")
    state.setdefault(_FILTER_PURPOSE_KEY, "All")
    state.setdefault(_FILTER_PAGE_KEY, 1)
    records = state[APPLICATIONS_KEY]
    dates = [
        application_date
        for record in records
        if (application_date := _as_date(record.get("application_date")))
    ]
    default_start = min(dates) if dates else date.today() - timedelta(days=90)
    default_end = max(dates) if dates else date.today()
    state.setdefault(_FILTER_DATE_KEY, (default_start, default_end))


def open_new_application() -> None:
    """Callback used by both the page action and the existing navbar CTA."""
    st.session_state["active_page"] = "Loan Applications"
    st.session_state[VIEW_KEY] = "new"
    st.session_state[FORM_ID_KEY] = None
    st.session_state[FORM_STEP_KEY] = 1


def _return_to_list() -> None:
    st.session_state[VIEW_KEY] = "list"
    st.session_state[SELECTED_ID_KEY] = None


def _open_details(application_id: str) -> None:
    st.session_state[SELECTED_ID_KEY] = application_id
    st.session_state[VIEW_KEY] = "details"


def _format_currency(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _format_date(value: Any) -> str:
    parsed = _as_date(value)
    return parsed.strftime("%b %d, %Y") if parsed else "Not provided"


def build_application_export(
    records: Sequence[Mapping[str, Any]], file_format: str
) -> bytes | None:
    """Build a table-only CSV or Excel export, or None when no rows match."""
    if not records:
        return None

    rows = [
        [
            _as_date(record.get(field)) or ""
            if field == "application_date"
            else record.get(field, "")
            for _, field in EXPORT_COLUMNS
        ]
        for record in records
    ]

    if file_format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(label for label, _ in EXPORT_COLUMNS)
        writer.writerows(rows)
        return ("\ufeff" + output.getvalue()).encode("utf-8")

    if file_format == "excel":
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Applications"
        worksheet.append([label for label, _ in EXPORT_COLUMNS])
        for row in rows:
            worksheet.append(row)

        header_fill = PatternFill(fill_type="solid", fgColor="2563EB")
        for cell in worksheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_index, (label, _) in enumerate(EXPORT_COLUMNS, start=1):
            values = (
                len(str(worksheet.cell(row=row_index, column=column_index).value or ""))
                for row_index in range(2, worksheet.max_row + 1)
            )
            max_length = max((len(label), *values))
            worksheet.column_dimensions[get_column_letter(column_index)].width = min(
                max_length + 2, 36
            )
        for cell in worksheet["C"][1:]:
            cell.number_format = "yyyy-mm-dd"
        for cell in worksheet["D"][1:]:
            cell.number_format = '$#,##0.00'

        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()

    raise ValueError(f"Unsupported application export format: {file_format}")


def _filtered_records_from_state() -> list[Mapping[str, Any]]:
    chosen_dates = st.session_state.get(_FILTER_DATE_KEY)
    date_range = chosen_dates if isinstance(chosen_dates, (tuple, list)) else None
    return filter_applications(
        st.session_state[APPLICATIONS_KEY],
        query=st.session_state.get(_FILTER_SEARCH_KEY, ""),
        status=st.session_state.get(_FILTER_STATUS_KEY, "All"),
        purpose=st.session_state.get(_FILTER_PURPOSE_KEY, "All"),
        date_range=date_range,
    )


def _render_export_menu(records: Sequence[Mapping[str, Any]]) -> None:
    with st.container(key="loan-export-control"):
        with st.popover(
            "Export",
            type="primary",
            icon=":material/download:",
            help="Export applications matching the current search and filters",
            width="content",
            wrap=False,
            key="loan-applications-export",
        ):
            with st.container(key="loan-export-menu-content"):
                if not records:
                    st.info("No matching applications to export.")
                    return

                st.download_button(
                    "Export CSV",
                    data=build_application_export(records, "csv"),
                    file_name="loan_applications.csv",
                    mime="text/csv",
                    icon=":material/table_view:",
                    width="stretch",
                    key="loan-export-csv",
                )
                st.download_button(
                    "Export Excel",
                    data=build_application_export(records, "excel"),
                    file_name="loan_applications.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    icon=":material/table_view:",
                    width="stretch",
                    key="loan-export-excel",
                )


def _render_management_header(records: Sequence[Mapping[str, Any]]) -> None:
    with st.container(key="loan-management-header"):
        title_column, export_column = st.columns(
            [5, 1.25], gap="small", vertical_alignment="center"
        )
        with title_column:
            _heading(
                "Application Management",
                "Monitor application volume, status, and processing progress.",
            )
        with export_column:
            with st.container(horizontal_alignment="right"):
                _render_export_menu(records)


def _escape(value: Any) -> str:
    return html.escape(str(value if value not in (None, "") else "Not provided"))


def _status_class(status: Any) -> str:
    return re.sub(r"[^a-z]+", "-", str(status).casefold()).strip("-")


def _risk_class(risk: Any) -> str:
    return re.sub(r"[^a-z]+", "-", str(risk).casefold()).strip("-")


def _page_styles(dark: bool) -> str:
    if dark:
        surface, text, muted, border, soft, hover, table_header, table_header_text = (
            "#151d2b",
            "#e6edf7",
            "#a2afc2",
            "rgba(226, 232, 240, 0.12)",
            "#1b2637",
            "rgba(106, 164, 255, 0.08)",
            "#1b2637",
            "#c4cfdf",
        )
    else:
        surface, text, muted, border, soft, hover, table_header, table_header_text = (
            "#ffffff",
            "#17243a",
            "#68778d",
            "#e7ebf1",
            "#f6f8fb",
            "#f7faff",
            "#f3f6fa",
            "#46556b",
        )
    styles = f"""
    <style>
    .loan-app-page {{ color: {text}; }}
    .st-key-loan-app-page {{ margin-top: -4px; }}
    .loan-app-page .loan-page-title {{ color: {text}; font-size: 1.55rem; font-weight: 700; margin: 0; }}
    .loan-app-page .loan-page-description {{ color: {muted}; font-size: 0.9rem; margin: 0.25rem 0 0; }}
    .st-key-loan-management-header {{ margin-bottom: 14px; }}
    .st-key-loan-summary-section {{ padding-bottom: 16px !important; }}
    .st-key-loan-management-header .st-key-loan-export-control {{ display: flex; justify-content: flex-end !important; align-self: stretch; width: 100%; margin-left: auto; }}
    .st-key-loan-management-header .st-key-loan-export-control > div {{ margin-left: auto !important; }}
    .st-key-loan-management-header [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{ display: flex; justify-content: flex-end; }}
    .st-key-loan-management-header [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child > div {{ display: flex; justify-content: flex-end; width: 100%; }}
    .st-key-loan-app-page .st-key-loan-management-header button[data-testid="stPopoverButton"] {{ width: 140px !important; min-width: 140px; min-height: 42px; margin-left: auto; white-space: nowrap; background: #2563eb !important; border-color: #2563eb !important; color: #ffffff !important; box-shadow: 0 2px 5px rgba(37, 99, 235, 0.2); }}
    .st-key-loan-app-page .st-key-loan-management-header button[data-testid="stPopoverButton"]:hover {{ background: #1d4ed8 !important; border-color: #1d4ed8 !important; color: #ffffff !important; }}
    [data-testid="stPopoverBody"]:has(.st-key-loan-export-menu-content) {{ border-radius: 12px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.16); }}
    .st-key-loan-export-menu-content .stDownloadButton button {{ min-height: 38px; white-space: nowrap; }}
    .loan-app-page .loan-summary-card {{ display: flex; align-items: flex-start; gap: 12px; height: 100%; min-height: 146px; box-sizing: border-box; padding: 22px 18px; border: 1px solid {border}; border-radius: 12px; background: {surface}; }}
    .loan-app-page .loan-summary-icon {{ display: inline-flex; flex: 0 0 34px; width: 34px; height: 34px; align-items: center; justify-content: center; border-radius: 9px; color: #2563eb; background: rgba(37, 99, 235, 0.09); }}
    .loan-app-page .loan-summary-content {{ min-width: 0; }}
    .loan-app-page .loan-summary-value {{ color: {text}; font-size: 1.55rem; font-weight: 750; line-height: 1.1; }}
    .loan-app-page .loan-summary-title {{ color: {text}; font-size: 0.82rem; font-weight: 650; margin-top: 3px; }}
    .loan-app-page .loan-summary-support {{ color: {muted}; font-size: 0.72rem; margin-top: 2px; }}
    .loan-app-page .loan-section-title {{ color: {text}; font-size: 1.03rem; font-weight: 700; margin: 0 0 3px; }}
    .loan-app-page .loan-section-subtitle {{ color: {muted}; font-size: 0.82rem; margin: 0; }}
    .loan-app-page .loan-filter-panel {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; padding: 10px 12px 0; }}
    .loan-app-page .st-key-loan-filter-toolbar {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; padding: 10px 12px 15px; }}
    .loan-app-page .loan-filter-heading {{ display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 10px; margin-bottom: 5px; }}
    .loan-app-page .loan-filter-heading .loan-section-title {{ margin: 0; font-size: 0.92rem; }}
    .loan-app-page .loan-filter-heading .loan-section-subtitle {{ font-size: 0.75rem; }}
    .loan-app-page .st-key-loan-table-header {{ background: {table_header}; border: 1px solid {border}; border-radius: 8px; padding: 8px 10px; }}
    .loan-app-page .loan-table-header {{ color: {table_header_text}; font-size: 0.74rem; font-weight: 750; text-transform: uppercase; letter-spacing: 0.025em; }}
    .loan-app-page .loan-table-value {{ color: {text}; font-size: 0.83rem; line-height: 1.35; }}
    .loan-app-page .loan-table-secondary {{ color: {muted}; font-size: 0.75rem; }}
    .loan-app-page .loan-applicant-name {{ color: {text}; font-size: 0.86rem; font-weight: 650; line-height: 1.25; }}
    .loan-app-page .loan-applicant-phone {{ color: {muted}; font-size: 0.72rem; margin-top: 3px; line-height: 1.2; }}
    .loan-app-page .loan-status-badge {{ display: inline-flex; align-items: center; min-height: 24px; box-sizing: border-box; max-width: 100%; border-radius: 999px; padding: 4px 8px; font-size: 0.68rem; font-weight: 700; line-height: 1.15; white-space: nowrap; }}
    .loan-app-page .status-pending {{ color: #92400e; background: #fef3c7; }}
    .loan-app-page .status-under-review {{ color: #1d4ed8; background: #dbeafe; }}
    .loan-app-page .status-under-assessment {{ color: #6d28d9; background: #ede9fe; }}
    .loan-app-page .status-approved {{ color: #166534; background: #dcfce7; }}
    .loan-app-page .status-rejected {{ color: #b91c1c; background: #fee2e2; }}
    .loan-app-page .loan-risk-badge {{ display: inline-flex; align-items: center; justify-content: center; min-width: 68px; min-height: 24px; box-sizing: border-box; border-radius: 999px; padding: 4px 8px; font-size: 0.68rem; font-weight: 700; line-height: 1.15; white-space: nowrap; }}
    .loan-app-page .risk-low {{ color: #166534; background: #dcfce7; }}
    .loan-app-page .risk-medium {{ color: #92400e; background: #fef3c7; }}
    .loan-app-page .risk-high {{ color: #b91c1c; background: #fee2e2; }}
    .loan-app-page .risk-not-assessed {{ color: {muted}; background: {soft}; border: 1px solid {border}; }}
    .loan-app-page [class*="st-key-loan-row-"] {{ border-bottom: 1px solid {border}; border-radius: 6px; transition: background-color 140ms ease; }}
    .loan-app-page [class*="st-key-loan-row-"]:hover {{ background: {hover}; }}
    .loan-app-page [class*="st-key-loan-row-"]:focus-within {{ background: {hover}; outline: 2px solid rgba(37, 99, 235, 0.28); outline-offset: -2px; }}
    .loan-app-page [class*="st-key-loan-id-"] button {{ min-height: 28px; justify-content: flex-start; padding: 0 2px; border: 0; background: transparent; color: #2563eb; font-size: 0.8rem; font-weight: 650; }}
    .loan-app-page [class*="st-key-loan-id-"] button:hover {{ border: 0; background: transparent; color: #1d4ed8; text-decoration: underline; }}
    .loan-app-page [class*="st-key-loan-id-"] button:focus-visible,
    .loan-app-page [class*="st-key-loan-view-"] button:focus-visible {{ outline: 2px solid #60a5fa; outline-offset: 2px; }}
    .loan-app-page [class*="st-key-loan-view-"] button {{ min-height: 28px; padding: 0 2px; border: 0; background: transparent; color: #2563eb; font-size: 0.76rem; font-weight: 650; }}
    .loan-app-page [class*="st-key-loan-view-"] button:hover {{ border: 0; background: transparent; color: #1d4ed8; text-decoration: underline; }}
    .loan-app-page .loan-info-card {{ box-sizing: border-box; height: 100%; padding: 18px; border: 1px solid {border}; border-radius: 12px; background: {surface}; }}
    .loan-app-page .loan-info-card h3 {{ color: {text}; font-size: 0.98rem; margin: 0 0 14px; }}
    .loan-app-page .loan-info-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 18px; }}
    .loan-app-page .loan-info-item {{ min-width: 0; }}
    .loan-app-page .loan-info-label {{ color: {muted}; font-size: 0.72rem; margin-bottom: 4px; }}
    .loan-app-page .loan-info-value {{ color: {text}; font-size: 0.85rem; font-weight: 600; overflow-wrap: anywhere; }}
    .loan-app-page .loan-detail-header {{ box-sizing: border-box; padding: 18px 20px; border: 1px solid {border}; border-radius: 12px; background: {surface}; }}
    .loan-app-page .loan-detail-id {{ color: {muted}; font-size: 0.78rem; font-weight: 600; }}
    .loan-app-page .loan-detail-name {{ color: {text}; font-size: 1.25rem; font-weight: 700; margin: 3px 0 10px; }}
    .loan-app-page .loan-timeline-item {{ display: grid; grid-template-columns: 14px 1fr; gap: 12px; padding: 0 0 18px; }}
    .loan-app-page .loan-timeline-dot {{ width: 9px; height: 9px; margin: 4px auto 0; border: 2px solid #2563eb; border-radius: 50%; background: {surface}; }}
    .loan-app-page .loan-timeline-event {{ color: {text}; font-size: 0.84rem; font-weight: 600; }}
    .loan-app-page .loan-timeline-time {{ color: {muted}; font-size: 0.75rem; margin-top: 3px; }}
    .loan-app-page .loan-form-panel,
    .loan-app-page .st-key-loan-application-form-panel {{ border: 1px solid {border}; border-radius: 12px; background: {surface}; padding: 18px 20px; }}
    .loan-app-page .loan-step-label {{ color: {muted}; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.03em; text-transform: uppercase; }}
    .loan-app-page .loan-step-title {{ color: {text}; font-size: 1.12rem; font-weight: 700; margin: 3px 0 4px; }}
    .loan-app-page .loan-step-description {{ color: {muted}; font-size: 0.82rem; margin: 0 0 16px; }}
    .loan-app-page .loan-review-block {{ border: 1px solid {border}; border-radius: 12px; background: {surface}; padding: 17px; margin-bottom: 12px; }}
    .loan-app-page .loan-review-block h4 {{ color: {text}; font-size: 0.9rem; margin: 0 0 12px; }}
    @media (max-width: 900px) {{
      .loan-app-page .loan-summary-card {{ min-height: 132px; padding: 18px 14px; }}
      .loan-app-page .loan-info-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 640px) {{
      .st-key-loan-management-header .st-key-loan-applications-export button[data-testid="stPopoverButton"] {{ min-width: 132px; }}
      .st-key-loan-management-header .loan-page-title {{ font-size: 1.35rem; }}
    }}
    </style>
    """
    return styles.replace(".loan-app-page", ".st-key-loan-app-page")


def _icon_svg(kind: str) -> str:
    paths = {
        "total": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 8h10M7 12h10M7 16h6"/>',
        "pending": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "assessment": '<path d="M4 19V5m0 14h16"/><path d="m7 15 4-4 3 2 5-6"/>',
        "completed": '<path d="m5 12 4 4L19 6"/><circle cx="12" cy="12" r="9"/>',
    }
    return (
        '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{paths[kind]}</svg>'
    )


def _summary_card(title: str, value: int, support: str, icon: str) -> str:
    return (
        '<div class="loan-summary-card">'
        f'<span class="loan-summary-icon">{_icon_svg(icon)}</span>'
        '<div class="loan-summary-content">'
        f'<div class="loan-summary-value">{value:,}</div>'
        f'<div class="loan-summary-title">{html.escape(title)}</div>'
        f'<div class="loan-summary-support">{html.escape(support)}</div>'
        '</div></div>'
    )


def _heading(title: str, description: str) -> None:
    st.markdown(
        f'<div class="loan-page-heading"><h1 class="loan-page-title">'
        f'{html.escape(title)}</h1><p class="loan-page-description">'
        f'{html.escape(description)}</p></div>',
        unsafe_allow_html=True,
    )


def _render_summary(records: Sequence[Mapping[str, Any]]) -> None:
    totals = summarize_applications(records)
    cards = (
        ("Total Applications", totals["total"], "All applications", "total"),
        ("Pending Review", totals["pending_review"], "Pending or under review", "pending"),
        ("Under Assessment", totals["under_assessment"], "In assessment", "assessment"),
        ("Completed Applications", totals["completed"], "Approved or rejected", "completed"),
    )
    with st.container(key="loan-summary-section"):
        columns = st.columns(4, gap="small")
        for column, card in zip(columns, cards):
            with column:
                st.markdown(_summary_card(*card), unsafe_allow_html=True)


def _reset_filters() -> None:
    st.session_state[_FILTER_SEARCH_KEY] = ""
    st.session_state[_FILTER_STATUS_KEY] = "All"
    st.session_state[_FILTER_PURPOSE_KEY] = "All"
    records = st.session_state.get(APPLICATIONS_KEY, [])
    dates = [
        application_date
        for record in records
        if (application_date := _as_date(record.get("application_date")))
    ]
    st.session_state[_FILTER_DATE_KEY] = (
        (min(dates), max(dates)) if dates else (date.today() - timedelta(days=90), date.today())
    )
    st.session_state[_FILTER_PAGE_KEY] = 1


def _render_filters() -> list[Mapping[str, Any]]:
    with st.container(key="loan-filter-toolbar"):
        st.markdown(
            '<div class="loan-filter-heading"><div class="loan-section-title">Search and filters</div>'
            '<div class="loan-section-subtitle">Find applications by name, ID, or phone.</div></div>',
            unsafe_allow_html=True,
        )
        search_col, status_col, purpose_col, date_col, reset_col = st.columns(
            [2.2, 1.15, 1.1, 1.65, 1.05], gap="small", vertical_alignment="bottom"
        )
        with search_col:
            st.text_input(
                "Search applications",
                placeholder="Name, application ID, or phone",
                key=_FILTER_SEARCH_KEY,
                label_visibility="visible",
                persist_state="session",
            )
        with status_col:
            st.selectbox(
                "Application status",
                ("All",) + STATUSES,
                key=_FILTER_STATUS_KEY,
                persist_state="session",
            )
        with purpose_col:
            st.selectbox(
                "Loan purpose",
                ("All",) + PURPOSES,
                key=_FILTER_PURPOSE_KEY,
                persist_state="session",
            )
        with date_col:
            st.date_input(
                "Application date",
                key=_FILTER_DATE_KEY,
                min_value=date(2000, 1, 1),
                max_value=date.today(),
                format="YYYY-MM-DD",
                persist_state="session",
            )
        with reset_col:
            st.button(
                "Reset filters",
                key="loan-applications-reset-filters",
                on_click=_reset_filters,
                type="tertiary",
                width="stretch",
            )
        st.markdown('<div style="height: 12px"></div>', unsafe_allow_html=True)

    return _filtered_records_from_state()


def _table_cell(primary: Any, secondary: Any | None = None) -> str:
    safe_primary = _escape(primary)
    if secondary is None:
        return f'<div class="loan-table-value">{safe_primary}</div>'
    return (
        f'<div class="loan-table-value">{safe_primary}</div>'
        f'<div class="loan-table-secondary">{_escape(secondary)}</div>'
    )


def _status_badge(status: Any) -> str:
    return (
        f'<span class="loan-status-badge status-{_status_class(status)}">'
        f"{_escape(status)}</span>"
    )


def _risk_indicator(risk: Any) -> str:
    return (
        f'<span class="loan-risk-badge risk-{_risk_class(risk)}">'
        f"{_escape(risk)}</span>"
    )


def _render_table(records: Sequence[Mapping[str, Any]]) -> None:
    count_label = "application" if len(records) == 1 else "applications"
    st.markdown(
        '<div><div class="loan-section-title">Applications</div>'
        f'<div class="loan-section-subtitle">Showing {len(records):,} {count_label}</div></div>',
        unsafe_allow_html=True,
    )
    if not records:
        st.info("No sample applications match the selected search and filters.")
        return

    page_count = max(1, math.ceil(len(records) / PAGE_SIZE))
    current_page = min(max(1, st.session_state.get(_FILTER_PAGE_KEY, 1)), page_count)
    st.session_state[_FILTER_PAGE_KEY] = current_page
    visible = records[(current_page - 1) * PAGE_SIZE : current_page * PAGE_SIZE]
    ratios = [1.45, 1.8, 1.05, 1.05, 0.75, 0.9, 1.15, 0.6]

    with st.container(key="loan-applications-table"):
        with st.container(key="loan-table-header"):
            header_columns = st.columns(ratios, gap="small", vertical_alignment="center")
            labels = (
                "Application ID",
                "Applicant",
                "Application date",
                "Loan amount",
                "Purpose",
                "Risk",
                "Status",
                "Action",
            )
            for column, label in zip(header_columns, labels):
                with column:
                    st.markdown(
                        f'<div class="loan-table-header">{html.escape(label)}</div>',
                        unsafe_allow_html=True,
                    )

        for record in visible:
            application_id = str(record["application_id"])
            with st.container(key=f"loan-row-{application_id}"):
                row_columns = st.columns(ratios, gap="small", vertical_alignment="center")
                cell_values = (
                    None,
                    '<div class="loan-applicant-name">'
                    f'{_escape(record.get("applicant_name"))}</div>'
                    '<div class="loan-applicant-phone">'
                    f'{_escape(record.get("phone"))}</div>',
                    _table_cell(_format_date(record.get("application_date"))),
                    _table_cell(_format_currency(record.get("loan_amount"))),
                    _table_cell(record.get("loan_purpose")),
                    _risk_indicator(latest_risk_summary(record)),
                    _status_badge(record.get("status")),
                    None,
                )
                for index, (column, cell) in enumerate(zip(row_columns, cell_values)):
                    with column:
                        if index == 0:
                            st.button(
                                application_id,
                                key=f"loan-id-{application_id}",
                                on_click=_open_details,
                                args=(application_id,),
                                type="tertiary",
                                width="content",
                            )
                        elif index == 7:
                            st.button(
                                "View",
                                key=f"loan-view-{application_id}",
                                on_click=_open_details,
                                args=(application_id,),
                                help=f"View details for {application_id}",
                                type="tertiary",
                                icon=":material/arrow_forward:",
                                width="content",
                            )
                        else:
                            st.markdown(cell, unsafe_allow_html=True)

    if page_count > 1:
        previous, page_label, next_page = st.columns([1, 2, 1], vertical_alignment="center")
        with previous:
            st.button(
                "Previous",
                key="loan-applications-previous-page",
                disabled=current_page <= 1,
                on_click=lambda: st.session_state.update(
                    {_FILTER_PAGE_KEY: max(1, st.session_state[_FILTER_PAGE_KEY] - 1)}
                ),
            )
        with page_label:
            st.caption(f"Page {current_page} of {page_count} · {len(records)} results")
        with next_page:
            st.button(
                "Next",
                key="loan-applications-next-page",
                disabled=current_page >= page_count,
                on_click=lambda: st.session_state.update(
                    {_FILTER_PAGE_KEY: min(page_count, st.session_state[_FILTER_PAGE_KEY] + 1)}
                ),
            )
    else:
        st.caption(f"{len(records)} sample application{'s' if len(records) != 1 else ''}")


def _find_application(application_id: Any) -> dict[str, Any] | None:
    return next(
        (
            record
            for record in st.session_state[APPLICATIONS_KEY]
            if record.get("application_id") == application_id
        ),
        None,
    )


def _info_card(title: str, fields: Sequence[tuple[str, Any]]) -> str:
    items = "".join(
        '<div class="loan-info-item">'
        f'<div class="loan-info-label">{html.escape(label)}</div>'
        f'<div class="loan-info-value">{_escape(value)}</div></div>'
        for label, value in fields
    )
    return (
        f'<section class="loan-info-card"><h3>{html.escape(title)}</h3>'
        f'<div class="loan-info-grid">{items}</div></section>'
    )


def _render_history(record: Mapping[str, Any]) -> None:
    st.markdown(
        '<div><div class="loan-section-title">Application history</div>'
        '<div class="loan-section-subtitle">Demonstration timeline; entries are illustrative.</div></div>',
        unsafe_allow_html=True,
    )
    history = record.get("history", [])
    if not history:
        st.caption("No sample history is available.")
        return
    for event in history:
        timestamp = event.get("timestamp")
        if isinstance(timestamp, datetime):
            displayed_time = timestamp.strftime("%b %d, %Y at %I:%M %p")
        else:
            displayed_time = _format_date(timestamp)
        st.markdown(
            '<div class="loan-timeline-item"><span class="loan-timeline-dot"></span>'
            f'<div><div class="loan-timeline-event">{_escape(event.get("event"))}</div>'
            f'<div class="loan-timeline-time">{_escape(displayed_time)}</div></div></div>',
            unsafe_allow_html=True,
        )


def _render_details() -> None:
    application_id = st.session_state.get(SELECTED_ID_KEY)
    record = _find_application(application_id)
    if record is None:
        st.warning("That sample application is no longer available.")
        st.button("Back to Applications", on_click=_return_to_list)
        return

    with st.container(key="loan-application-detail-header"):
        title_col, action_col = st.columns([4, 1], vertical_alignment="center")
        with title_col:
            st.markdown(
                f'<div class="loan-detail-header"><div class="loan-detail-id">'
                f'{_escape(record.get("application_id"))} · {_format_date(record.get("application_date"))}'
                f'</div><div class="loan-detail-name">{_escape(record.get("applicant_name"))}</div>'
                f'{_status_badge(record.get("status"))} '
                f'<span class="loan-table-secondary">Risk assessment: '
                f'{_escape(record.get("risk_level", "Not Assessed"))}</span></div>',
                unsafe_allow_html=True,
            )
        with action_col:
            st.button(
                "Back to Applications",
                key="loan-detail-back",
                on_click=_return_to_list,
                width="stretch",
            )

    st.markdown("")
    personal = (
        ("Full name", record.get("applicant_name")),
        ("Date of birth", _format_date(record.get("date_of_birth"))),
        ("Gender", record.get("gender")),
        ("Phone number", record.get("phone")),
        ("Email address", record.get("email")),
        ("Residential address", record.get("address")),
    )
    employment = (
        ("Employment status", record.get("employment_status")),
        ("Occupation", record.get("occupation")),
        ("Employer name", record.get("employer_name")),
        ("Work experience", f'{record.get("work_experience_years", 0)} years'),
        ("Monthly income", _format_currency(record.get("monthly_income"))),
    )
    monthly_income = float(record.get("monthly_income", 0) or 0)
    monthly_outgoings = sum(
        float(record.get(field, 0) or 0)
        for field in ("monthly_expenses", "other_obligations")
    )
    financial = (
        ("Monthly income", _format_currency(monthly_income)),
        ("Monthly expenses", _format_currency(record.get("monthly_expenses"))),
        ("Existing debt", _format_currency(record.get("existing_debt"))),
        ("Other obligations", _format_currency(record.get("other_obligations"))),
        ("Available monthly income", _format_currency(monthly_income - monthly_outgoings)),
    )
    loan = (
        ("Requested amount", _format_currency(record.get("loan_amount"))),
        ("Loan purpose", record.get("loan_purpose")),
        ("Loan term", f'{record.get("loan_term_months", "Not provided")} months'),
        ("Repayment frequency", record.get("repayment_frequency")),
        ("Application date", _format_date(record.get("application_date"))),
    )
    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown(_info_card("Personal information", personal), unsafe_allow_html=True)
        st.markdown("")
        st.markdown(_info_card("Financial information", financial), unsafe_allow_html=True)
    with right:
        st.markdown(_info_card("Employment information", employment), unsafe_allow_html=True)
        st.markdown("")
        st.markdown(_info_card("Loan information", loan), unsafe_allow_html=True)

    st.markdown("")
    _render_history(record)
    st.markdown("")
    st.markdown(
        '<div><div class="loan-section-title">Actions</div>'
        '<div class="loan-section-subtitle">Prototype actions update demonstration data only.</div></div>',
        unsafe_allow_html=True,
    )
    status_col, update_col, edit_col = st.columns([2, 1, 1], vertical_alignment="bottom")
    status_key = f"loan-status-{record['application_id']}"
    if status_key not in st.session_state:
        st.session_state[status_key] = record["status"]
    with status_col:
        st.selectbox("Update status", STATUSES, key=status_key)
    with update_col:
        if st.button("Update Status", key="loan-detail-update-status", type="primary"):
            new_status = st.session_state[status_key]
            if new_status != record["status"]:
                record["status"] = new_status
                record.setdefault("history", []).append(
                    {
                        "event": f"Demonstration status updated to {new_status}",
                        "timestamp": datetime.now().astimezone(),
                    }
                )
                st.session_state["loan_applications_notice"] = (
                    f"Demonstration status updated to {new_status}."
                )
            st.rerun()
    with edit_col:
        st.button(
            "Edit Application",
            key="loan-detail-edit",
            on_click=_begin_edit,
            args=(record["application_id"],),
            width="stretch",
        )


def _record_to_form(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        form_field: record.get(record_field, _FORM_DEFAULTS[form_field])
        for form_field, record_field in _FORM_TO_RECORD.items()
    }


def _prepare_form() -> None:
    view = st.session_state[VIEW_KEY]
    application_id = (
        "__new__"
        if view == "new"
        else st.session_state.get(SELECTED_ID_KEY)
    )
    if st.session_state.get(FORM_ID_KEY) == application_id:
        return

    record = _find_application(application_id) if application_id != "__new__" else None
    values = _record_to_form(record) if record else _FORM_DEFAULTS
    for field, default in _FORM_DEFAULTS.items():
        st.session_state[f"loan_form_{field}"] = values.get(field, default)
    st.session_state["loan_application_form_data"] = dict(values)
    st.session_state[FORM_ID_KEY] = application_id
    st.session_state[FORM_STEP_KEY] = 1


def _form_values(step: int | None = None) -> dict[str, Any]:
    values = dict(st.session_state.get("loan_application_form_data", _FORM_DEFAULTS))
    for field in _FORM_STEP_FIELDS.get(step, ()):
        widget_key = f"loan_form_{field}"
        if widget_key in st.session_state:
            values[field] = st.session_state[widget_key]
    return values


def _restore_form_step(step: int) -> None:
    values = st.session_state.get("loan_application_form_data", _FORM_DEFAULTS)
    for field in _FORM_STEP_FIELDS.get(step, ()):
        widget_key = f"loan_form_{field}"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = values.get(field, _FORM_DEFAULTS[field])


def _validate_step(values: Mapping[str, Any], step: int) -> list[str]:
    if step == 1:
        fields = ("full_name", "date_of_birth", "gender", "phone", "email", "address")
        errors = [
            f"{_REQUIRED_FIELDS[field]} is required."
            for field in fields
            if not str(values.get(field, "") or "").strip()
        ]
        email = str(values.get("email", "") or "").strip()
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Enter a valid email address.")
        phone = re.sub(r"\D", "", str(values.get("phone", "")))
        if values.get("phone") and len(phone) < 7:
            errors.append("Enter a valid phone number.")
        birth_date = _as_date(values.get("date_of_birth"))
        if values.get("date_of_birth") and birth_date is None:
            errors.append("Date of birth is invalid.")
        elif birth_date and birth_date > date.today():
            errors.append("Date of birth cannot be in the future.")
        return errors
    if step == 2:
        fields = ("employment_status", "occupation", "employer")
        errors = [
            f"{_REQUIRED_FIELDS[field]} is required."
            for field in fields
            if not str(values.get(field, "") or "").strip()
        ]
        for field, label in (
            ("work_experience_years", "Work experience"),
            ("monthly_income", "Monthly income"),
        ):
            try:
                number = float(values.get(field, 0) or 0)
            except (TypeError, ValueError):
                errors.append(f"{label} must be a number.")
                continue
            if not math.isfinite(number):
                errors.append(f"{label} must be a finite number.")
            elif number < 0:
                errors.append(f"{label} cannot be negative.")
            elif field == "monthly_income" and number <= 0:
                errors.append("Monthly income must be greater than zero.")
        return errors
    if step == 3:
        errors = []
        for field, label in (
            ("monthly_expenses", "Monthly expenses"),
            ("existing_debt", "Existing debt"),
            ("other_obligations", "Other financial obligations"),
        ):
            try:
                number = float(values.get(field, 0) or 0)
                if not math.isfinite(number):
                    errors.append(f"{label} must be a finite number.")
                elif number < 0:
                    errors.append(f"{label} cannot be negative.")
            except (TypeError, ValueError):
                errors.append(f"{label} must be a number.")
        return errors
    if step == 4:
        errors = []
        for field, label in (
            ("loan_purpose", "Loan purpose"),
            ("repayment_frequency", "Repayment frequency"),
        ):
            if not str(values.get(field, "") or "").strip():
                errors.append(f"{label} is required.")
        try:
            loan_amount = float(values.get("loan_amount", 0) or 0)
            if not math.isfinite(loan_amount):
                errors.append("Requested loan amount must be a finite number.")
            elif loan_amount <= 0:
                errors.append("Requested loan amount must be greater than zero.")
        except (TypeError, ValueError):
            errors.append("Requested loan amount must be a number.")
        try:
            loan_term = float(values.get("loan_term_months", 0) or 0)
            if not math.isfinite(loan_term) or not loan_term.is_integer():
                errors.append("Loan term must be a whole number.")
            elif loan_term <= 0:
                errors.append("Loan term must be greater than zero.")
        except (TypeError, ValueError):
            errors.append("Loan term must be a whole number.")
        return errors
    return validate_application_form(values)


def _render_form_fields(step: int) -> None:
    if step == 1:
        first, second = st.columns(2, gap="medium")
        with first:
            st.text_input("Full name", key="loan_form_full_name")
            st.date_input(
                "Date of birth",
                key="loan_form_date_of_birth",
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                format="YYYY-MM-DD",
            )
            st.text_input("Phone number", key="loan_form_phone", placeholder="For example, +1 202 555 0100")
        with second:
            st.selectbox("Gender", GENDERS, index=None, key="loan_form_gender")
            st.text_input("Email address", key="loan_form_email")
            st.text_area("Residential address", key="loan_form_address", height=96)
    elif step == 2:
        first, second = st.columns(2, gap="medium")
        with first:
            st.selectbox(
                "Employment status",
                EMPLOYMENT_STATUSES,
                index=None,
                key="loan_form_employment_status",
            )
            st.text_input("Occupation", key="loan_form_occupation")
            st.number_input(
                "Years of work experience",
                min_value=0.0,
                step=0.5,
                key="loan_form_work_experience_years",
            )
        with second:
            st.text_input("Employer name", key="loan_form_employer")
            st.number_input(
                "Monthly income",
                min_value=0.0,
                step=100.0,
                key="loan_form_monthly_income",
            )
    elif step == 3:
        values = _form_values()
        st.metric("Monthly income", _format_currency(values.get("monthly_income")))
        first, second = st.columns(2, gap="medium")
        with first:
            st.number_input(
                "Monthly expenses",
                min_value=0.0,
                step=100.0,
                key="loan_form_monthly_expenses",
            )
            st.number_input(
                "Existing debt",
                min_value=0.0,
                step=100.0,
                key="loan_form_existing_debt",
            )
        with second:
            st.number_input(
                "Other financial obligations",
                min_value=0.0,
                step=100.0,
                key="loan_form_other_obligations",
            )
    elif step == 4:
        first, second = st.columns(2, gap="medium")
        with first:
            st.number_input(
                "Requested loan amount",
                min_value=0.0,
                step=500.0,
                key="loan_form_loan_amount",
            )
            st.selectbox("Loan purpose", PURPOSES, index=None, key="loan_form_loan_purpose")
        with second:
            st.number_input(
                "Loan term (months)",
                min_value=1,
                step=1,
                key="loan_form_loan_term_months",
            )
            st.selectbox(
                "Preferred repayment frequency",
                REPAYMENT_FREQUENCIES,
                index=None,
                key="loan_form_repayment_frequency",
            )


def _render_review(values: Mapping[str, Any]) -> None:
    personal = (
        ("Full name", values.get("full_name")),
        ("Date of birth", _format_date(values.get("date_of_birth"))),
        ("Gender", values.get("gender")),
        ("Phone", values.get("phone")),
        ("Email", values.get("email")),
        ("Address", values.get("address")),
    )
    employment = (
        ("Employment status", values.get("employment_status")),
        ("Occupation", values.get("occupation")),
        ("Employer", values.get("employer")),
        ("Work experience", f'{values.get("work_experience_years", 0)} years'),
        ("Monthly income", _format_currency(values.get("monthly_income"))),
    )
    financial = (
        ("Monthly expenses", _format_currency(values.get("monthly_expenses"))),
        ("Existing debt", _format_currency(values.get("existing_debt"))),
        ("Other obligations", _format_currency(values.get("other_obligations"))),
    )
    loan = (
        ("Requested amount", _format_currency(values.get("loan_amount"))),
        ("Purpose", values.get("loan_purpose")),
        ("Loan term", f'{values.get("loan_term_months", 1)} months'),
        ("Repayment frequency", values.get("repayment_frequency")),
    )
    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown(_info_card("Personal information", personal), unsafe_allow_html=True)
        st.markdown("")
        st.markdown(_info_card("Financial information", financial), unsafe_allow_html=True)
    with right:
        st.markdown(_info_card("Employment information", employment), unsafe_allow_html=True)
        st.markdown("")
        st.markdown(_info_card("Loan information", loan), unsafe_allow_html=True)
    st.caption("Review the information above. Submissions are stored only for this demo session.")


def _save_application(values: Mapping[str, Any]) -> None:
    errors = validate_application_form(values)
    if errors:
        st.error("Please review the application details.")
        for error in errors:
            st.caption(f"- {error}")
        return

    records = st.session_state[APPLICATIONS_KEY]
    edit_id = st.session_state.get(FORM_ID_KEY)
    mapped_values = {
        record_field: values.get(form_field)
        for form_field, record_field in _FORM_TO_RECORD.items()
    }
    mapped_values["available_monthly_income"] = (
        float(values["monthly_income"])
        - float(values["monthly_expenses"])
        - float(values["other_obligations"])
    )
    if edit_id and edit_id != "__new__":
        record = _find_application(edit_id)
        if record is None:
            st.error("The sample application could not be found.")
            return
        record.update(mapped_values)
        record.setdefault("history", []).append(
            {"event": "Demonstration application details updated", "timestamp": datetime.now().astimezone()}
        )
        message = f"Demonstration application {edit_id} updated."
    else:
        application_id = generate_application_id(records)
        record = {
            "application_id": application_id,
            **mapped_values,
            "application_date": date.today(),
            "risk_level": "Not Assessed",
            "status": "Pending",
            "history": [
                {
                    "event": "Demonstration application submitted",
                    "timestamp": datetime.now().astimezone(),
                }
            ],
        }
        records.insert(0, record)
        st.session_state[SELECTED_ID_KEY] = application_id
        _reset_filters()
        message = f"Demonstration application {application_id} submitted."

    st.session_state["loan_applications_notice"] = message
    st.session_state[VIEW_KEY] = "list"
    st.session_state[_FILTER_PAGE_KEY] = 1
    st.rerun()


def _begin_edit(application_id: str) -> None:
    record = _find_application(application_id)
    if record is None:
        return
    values = _record_to_form(record)
    for field, value in values.items():
        st.session_state[f"loan_form_{field}"] = value
    st.session_state["loan_application_form_data"] = values
    st.session_state[FORM_ID_KEY] = application_id
    st.session_state[FORM_STEP_KEY] = 1
    st.session_state[VIEW_KEY] = "edit"


def _render_form() -> None:
    _prepare_form()
    is_edit = st.session_state[VIEW_KEY] == "edit"
    title = "Edit Application" if is_edit else "New Application"
    _heading(
        title,
        "Complete each section to review and save a demonstration application.",
    )
    st.markdown("")

    steps = (
        ("Personal information", "Applicant identity and contact details."),
        ("Employment information", "Employment status and income details."),
        ("Financial information", "Monthly expenses and existing obligations."),
        ("Loan information", "Requested amount and repayment preferences."),
        ("Review and submission", "Review the information before saving."),
    )
    step = int(st.session_state.get(FORM_STEP_KEY, 1))
    step = min(max(step, 1), len(steps))
    st.progress(step / len(steps), text=f"Step {step} of {len(steps)}")
    with st.container(key="loan-application-form-panel"):
        st.markdown(
            f'<div class="loan-step-label">Section {step} of {len(steps)}</div>'
            f'<div class="loan-step-title">{html.escape(steps[step - 1][0])}</div>'
            f'<div class="loan-step-description">{html.escape(steps[step - 1][1])}</div>',
            unsafe_allow_html=True,
        )

        if step < 5:
            _restore_form_step(step)
            with st.form(key="loan-application-step-form"):
                _render_form_fields(step)
                st.markdown("")
                back_col, next_col = st.columns([1, 1], gap="small")
                with back_col:
                    if step == 1:
                        back_clicked = st.form_submit_button("Cancel")
                    else:
                        back_clicked = st.form_submit_button("Back")
                with next_col:
                    continue_clicked = st.form_submit_button("Continue", type="primary")
            if back_clicked:
                if step == 1:
                    _return_to_list()
                else:
                    st.session_state["loan_application_form_data"] = _form_values(step)
                    st.session_state[FORM_STEP_KEY] = step - 1
                st.rerun()
            if continue_clicked:
                values = _form_values(step)
                errors = _validate_step(values, step)
                if errors:
                    st.error("Please complete the required information.")
                    for error in errors:
                        st.caption(f"- {error}")
                else:
                    st.session_state["loan_application_form_data"] = values
                    st.session_state[FORM_STEP_KEY] = step + 1
                    st.rerun()
        else:
            values = _form_values()
            _render_review(values)
            st.markdown("")
            back_col, cancel_col, submit_col = st.columns([1, 1, 1], gap="small")
            with back_col:
                back_clicked = st.button("Back / Edit", key="loan-form-back-edit")
            with cancel_col:
                cancel_clicked = st.button("Cancel", key="loan-form-cancel")
            with submit_col:
                submit_clicked = st.button(
                    "Submit Application" if not is_edit else "Save Changes",
                    key="loan-form-submit",
                    type="primary",
                )
            if back_clicked:
                st.session_state[FORM_STEP_KEY] = 1
                st.rerun()
            if cancel_clicked:
                _return_to_list()
                st.rerun()
            if submit_clicked:
                _save_application(values)


def show_loan_applications() -> None:
    """Render the Loan Applications page or its separate details/form view."""
    _ensure_state()
    dark = bool(st.session_state.get("dark_mode", False))
    st.markdown(_page_styles(dark), unsafe_allow_html=True)

    with st.container(key="loan-app-page"):
        view = st.session_state[VIEW_KEY]
        if view == "details":
            notice = st.session_state.pop("loan_applications_notice", None)
            if notice:
                st.success(notice)
            _render_details()
        elif view in ("new", "edit"):
            _render_form()
        else:
            notice = st.session_state.pop("loan_applications_notice", None)
            if notice:
                st.success(notice)
            matching_records = _filtered_records_from_state()
            _render_management_header(matching_records)
            _render_summary(st.session_state[APPLICATIONS_KEY])
            _render_filters()
            _render_table(matching_records)


def render() -> None:
    """Compatibility entry point for the existing module placeholder."""
    show_loan_applications()
