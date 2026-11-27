"""New loan application dialog: no Enter-to-submit, hint placeholders, validated required fields."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

import streamlit as st

from utils.calculations import illustrative_risk_assessment
from utils.state import LOAN_PURPOSES, get_records, next_application_id

_P = "na_"  # session-state key prefix for this form
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-]{6,17}[0-9]$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NAME_RE = re.compile(r"^[A-Za-z\u1780-\u17FF][A-Za-z\u1780-\u17FF .'\-]{1,59}$")

EMPLOYMENT = ["Full-time", "Business owner", "Self-employed", "Contract", "Part-time"]
FIELD_KEYS = [
    "name", "type", "province", "phone", "email", "employment", "years", "occupation",
    "income", "expenses", "debt_bal", "debt_pmt", "amount", "purpose", "term", "rate",
    "thin", "alt",
]


def _req(text: str) -> str:
    """Required label with a small red star."""
    return f"{text} :red[*]"


def _err(field: str) -> None:
    msg = st.session_state.get(_P + "errors", {}).get(field)
    if msg:
        st.caption(f":red[{msg}]")


def _val(key: str):
    return st.session_state.get(_P + key)


def _validate() -> dict[str, str]:
    e: dict[str, str] = {}
    name = (_val("name") or "").strip()
    if not name:
        e["name"] = "Full name is required."
    elif not _NAME_RE.match(name):
        e["name"] = "Use letters only (2-60 characters)."
    if not _val("type"):
        e["type"] = "Select a borrower type."
    if not _val("employment"):
        e["employment"] = "Select an employment status."
    phone = (_val("phone") or "").strip()
    if phone and not _PHONE_RE.match(phone):
        e["phone"] = "Enter digits only, e.g. +855 12 345 678."
    email = (_val("email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        e["email"] = "Enter a valid email, e.g. name@example.com."
    years = _val("years")
    if years is not None and not (0 <= years <= 60):
        e["years"] = "Enter 0 to 60 years."
    if _val("income") is None or _val("income") <= 0:
        e["income"] = "Monthly income is required and must be above 0."
    if _val("expenses") is None or _val("expenses") < 0:
        e["expenses"] = "Monthly expenses are required (0 or more)."
    if _val("amount") is None or _val("amount") < 500:
        e["amount"] = "Requested loan is required (minimum 500)."
    if not _val("purpose"):
        e["purpose"] = "Select a loan purpose."
    if _val("term") is None or not (6 <= _val("term") <= 240):
        e["term"] = "Term is required (6 to 240 months)."
    if _val("rate") is None or not (0 <= _val("rate") <= 36):
        e["rate"] = "Rate is required (0 to 36 %)."
    return e


def _submit() -> None:
    errors = _validate()
    st.session_state[_P + "errors"] = errors
    if errors:
        return

    new_id = next_application_id()
    name = _val("name").strip()
    record = {
        "application_id": new_id,
        "applicant_name": name,
        "borrower_type": _val("type"),
        "phone": (_val("phone") or "").strip() or "Not provided",
        "email": (_val("email") or "").strip() or "Not provided",
        "province": (_val("province") or "").strip() or "Not provided",
        "employment_status": _val("employment"),
        "occupation": (_val("occupation") or "").strip() or "Not provided",
        "work_experience_years": float(_val("years") or 0.0),
        "monthly_income": float(_val("income")),
        "monthly_expenses": float(_val("expenses")),
        "existing_debt_balance": float(_val("debt_bal") or 0.0),
        "monthly_debt_payment": float(_val("debt_pmt") or 0.0),
        "loan_amount": float(_val("amount")),
        "loan_purpose": _val("purpose"),
        "loan_term_months": int(_val("term")),
        "interest_rate": float(_val("rate")),
        "application_date": date.today(),
        "status": "Pending",
        "thin_file": bool(_val("thin")),
        "alt_data_verified": bool(_val("alt")),
        "docs_verified": {"ID / KYC": False, "Income Proof": False, "Bank Statements": False, "Collateral": False},
        "analyst_notes": "",
        "recommendation": "Pending initial review",
        "loan_account_id": None,
        "disbursed_date": None,
        "repayment_schedule": [],
        "payments": [],
        "collection_logs": [],
        "activity_log": [
            {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "actor": st.session_state.get("staff_role", "Loan officer"),
                "event": f"Application {new_id} submitted (borrower-declared data, unverified)",
            }
        ],
    }
    a = illustrative_risk_assessment(record)
    record.update(
        risk_tier=a["tier"], risk_pd_pct=a["pd_pct"], projected_dti=a["projected_dti"],
        estimated_installment=a["estimated_installment"],
    )
    get_records().insert(0, record)
    st.session_state.selected_app_id = new_id
    st.session_state[_P + "created"] = new_id
    for k in FIELD_KEYS:  # reset form for next time
        st.session_state.pop(_P + k, None)


@st.dialog("New loan application", width="large")
def open_new_application_dialog() -> None:
    """Plain widgets (not st.form) so pressing Enter never submits the application."""
    created = st.session_state.pop(_P + "created", None)
    if created:
        st.session_state.pop(_P + "errors", None)
        st.toast(f"Created application {created}", icon=":material/check_circle:")
        st.rerun()

    st.caption(":red[*] Required. Other fields are optional. Press Enter freely: nothing is submitted until you click Submit.")
    if st.session_state.get(_P + "errors"):
        st.error("Please fix the highlighted fields below.", icon=":material/error:")

    st.markdown("#### Borrower information")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input(_req("Full name"), key=_P + "name", placeholder="e.g. Sophea Mean")
        _err("name")
    with c2:
        st.selectbox(_req("Borrower type"), ["Personal", "Business"], index=None,
                     placeholder="Choose type", key=_P + "type")
        _err("type")
    with c3:
        st.text_input("Province / city", key=_P + "province", placeholder="e.g. Phnom Penh")

    c4, c5, c6 = st.columns(3)
    with c4:
        st.text_input("Phone number", key=_P + "phone", placeholder="e.g. +855 12 345 678")
        _err("phone")
    with c5:
        st.text_input("Email", key=_P + "email", placeholder="e.g. name@example.com")
        _err("email")
    with c6:
        st.selectbox(_req("Employment status"), EMPLOYMENT, index=None,
                     placeholder="Choose status", key=_P + "employment")
        _err("employment")

    c7, c8 = st.columns(2)
    with c7:
        st.text_input("Occupation / business activity", key=_P + "occupation",
                      placeholder="e.g. Retail shop owner")
    with c8:
        st.number_input("Years of experience", min_value=0.0, max_value=60.0, value=None,
                        step=0.5, key=_P + "years", placeholder="e.g. 3")
        _err("years")

    st.markdown("#### Financial profile")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        st.number_input(_req("Monthly income ($)"), min_value=0.0, value=None, step=100.0,
                        key=_P + "income", placeholder="e.g. 2500")
        _err("income")
    with f2:
        st.number_input(_req("Monthly expenses ($)"), min_value=0.0, value=None, step=50.0,
                        key=_P + "expenses", placeholder="e.g. 1100")
        _err("expenses")
    with f3:
        st.number_input("Existing debt balance ($)", min_value=0.0, value=None, step=100.0,
                        key=_P + "debt_bal", placeholder="e.g. 2000")
    with f4:
        st.number_input("Monthly debt payments ($)", min_value=0.0, value=None, step=25.0,
                        key=_P + "debt_pmt", placeholder="e.g. 150")

    st.markdown("#### Loan request")
    l1, l2, l3, l4 = st.columns(4)
    with l1:
        st.number_input(_req("Requested loan ($)"), min_value=0.0, value=None, step=500.0,
                        key=_P + "amount", placeholder="e.g. 15000")
        _err("amount")
    with l2:
        st.selectbox(_req("Loan purpose"), list(LOAN_PURPOSES), index=None,
                     placeholder="Choose purpose", key=_P + "purpose")
        _err("purpose")
    with l3:
        st.number_input(_req("Term (months)"), min_value=0, max_value=240, value=None, step=6,
                        key=_P + "term", placeholder="e.g. 36")
        _err("term")
    with l4:
        st.number_input(_req("Indicative rate (%)"), min_value=0.0, max_value=36.0, value=None,
                        step=0.25, key=_P + "rate", placeholder="e.g. 11.5")
        _err("rate")

    i1, i2 = st.columns(2)
    i1.checkbox("Thin traditional credit file (limited bureau history)", key=_P + "thin")
    i2.checkbox("Alternative records available (utility / mobile money)", key=_P + "alt")

    b1, b2 = st.columns([1, 3])
    if b1.button("Cancel", width="stretch"):
        st.session_state.pop(_P + "errors", None)
        st.rerun()
    b2.button("Submit application", type="primary", width="stretch", on_click=_submit)
