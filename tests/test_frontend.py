"""Automated tests for the FinGuard AI Streamlit frontend and financial helpers."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from utils.calculations import (
    build_amortization_schedule,
    calculate_dpd_and_bucket,
    debt_service_coverage_ratio,
    debt_to_income_ratio,
    illustrative_risk_assessment,
    monthly_loan_payment,
)

APP_PATH = Path(__file__).resolve().parents[1] / "frontend" / "app.py"

ALL_PAGE_PATHS = [
    "app_pages/dashboard.py",
    "app_pages/loan_applications.py",
    "app_pages/credit_assessment.py",
    "app_pages/debt_analysis.py",
    "app_pages/loan_management.py",
    "app_pages/risk_monitoring.py",
    "app_pages/banking_analytics.py",
]


# --- Pure calculation tests --------------------------------------------------
def test_monthly_loan_payment_zero_and_nonzero_rate():
    assert monthly_loan_payment(12000, 0.0, 12) == 1000.0
    pmt = monthly_loan_payment(12000, 12.0, 12)
    assert 1060.0 < pmt < 1070.0


def test_dti_and_dscr_calculations():
    assert debt_to_income_ratio(1000, 4000) == 25.0
    assert debt_to_income_ratio(500, 0) == 0.0
    assert debt_service_coverage_ratio(3000, 1500) == 2.0
    assert debt_service_coverage_ratio(3000, 0) is None


def test_amortization_and_dpd_buckets():
    today = date.today()
    schedule = build_amortization_schedule(
        principal=6000,
        annual_rate_pct=12.0,
        months=6,
        first_due_date=today - timedelta(days=45),
        paid_installments=0,
    )
    assert len(schedule) == 6
    assert schedule[-1]["closing_balance"] == 0.0
    dpd, bucket, overdue = calculate_dpd_and_bucket(schedule, as_of=today)
    assert dpd == 45
    assert bucket == "31-60 DPD"
    assert overdue > 0


def test_thin_file_with_alt_data_not_auto_penalized():
    base = {
        "monthly_income": 4000.0,
        "monthly_expenses": 1400.0,
        "monthly_debt_payment": 200.0,
        "loan_amount": 10000.0,
        "loan_term_months": 24,
        "interest_rate": 10.0,
        "work_experience_years": 5,
        "thin_file": True,
        "alt_data_verified": True,
    }
    res = illustrative_risk_assessment(base)
    assert res["tier"] == "Low Risk"


# --- Streamlit AppTest UI verification ---------------------------------------
def test_dashboard_loads_cleanly():
    at = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert not at.exception
    assert at.session_state["staff_role"] == "All roles (full preview)"
    assert len(at.session_state["loan_records"]) >= 10


@pytest.mark.parametrize("page_path", ALL_PAGE_PATHS)
def test_every_page_renders_without_error(page_path: str):
    at = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert not at.exception
    at.switch_page(page_path).run()
    assert not at.exception


def test_role_selector_updates_navigation():
    at = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    at.sidebar.selectbox(key="staff_role").select("Loan officer").run()
    assert not at.exception
    assert at.session_state["staff_role"] == "Loan officer"

def _dialog_script():
    import sys

    sys.path.insert(0, r"FRONTEND_DIR")
    from utils.new_application import open_new_application_dialog
    from utils.state import init_session_state

    init_session_state()
    open_new_application_dialog()


def _submit_btn(at):
    return next(b for b in at.button if b.label == "Submit application")


def test_new_application_requires_fields_then_submits():
    script = _dialog_script
    import inspect
    import textwrap

    src = textwrap.dedent(inspect.getsource(script)).replace(
        "FRONTEND_DIR", str(APP_PATH.parent)
    ) + "\n_dialog_script()\n"
    at = AppTest.from_string(src, default_timeout=15).run()
    assert not at.exception
    before = len(at.session_state["loan_records"])

    # Required fields empty -> no record, errors shown
    _submit_btn(at).click().run()
    assert len(at.session_state["loan_records"]) == before
    assert {"name", "type", "income", "amount"} <= set(at.session_state["na_errors"])

    at.text_input(key="na_name").set_value("Sophea Mean")
    at.selectbox(key="na_type").select("Personal")
    at.selectbox(key="na_employment").select("Full-time")
    at.number_input(key="na_income").set_value(2500.0)
    at.number_input(key="na_expenses").set_value(1100.0)
    at.number_input(key="na_amount").set_value(15000.0)
    at.selectbox(key="na_purpose").select("Personal")
    at.number_input(key="na_term").set_value(36)
    at.number_input(key="na_rate").set_value(11.5)
    at.text_input(key="na_phone").set_value("abc")
    _submit_btn(at).click().run()
    assert len(at.session_state["loan_records"]) == before
    assert "phone" in at.session_state["na_errors"]

    # Optional fields blank -> submits
    at.text_input(key="na_phone").set_value("")
    _submit_btn(at).click().run()
    assert len(at.session_state["loan_records"]) == before + 1
    assert at.session_state["loan_records"][0]["applicant_name"] == "Sophea Mean"


def test_loan_applications_role_permissions():
    at = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    # Credit analyst: read-only, no New application button, sees Open credit assessment
    at.sidebar.selectbox(key="staff_role").select("Credit analyst").run()
    at.switch_page("app_pages/loan_applications.py").run()
    assert not at.exception
    labels = [b.label for b in at.button]
    assert "New application" not in labels
    assert "Open credit assessment" in labels
    assert all(cb.disabled for cb in at.checkbox)

    # Loan officer: sees New application, editable document checkboxes, no Open credit assessment
    at.sidebar.selectbox(key="staff_role").select("Loan officer").run()
    assert not at.exception
    labels = [b.label for b in at.button]
    assert "New application" in labels
    assert "Open credit assessment" not in labels
    assert not any(cb.disabled for cb in at.checkbox)


def test_role_handoff_workflow():
    at = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert len(at.session_state["handoff_messages"]) >= 3

    # Switch to Credit analyst -> should see incoming handoff for Credit analyst
    at.sidebar.selectbox(key="staff_role").select("Credit analyst").run()
    assert not at.exception
    ca_inbox = [m for m in at.session_state["handoff_messages"] if m["to_role"] == "Credit analyst"]
    assert len(ca_inbox) >= 1

    # Switch to Loan officer -> send a Pending application to assessment -> notifies Credit analyst
    before_ca = len(ca_inbox)
    at.sidebar.selectbox(key="staff_role").select("Loan officer").run()
    at.switch_page("app_pages/loan_applications.py").run()
    pending = next(r for r in at.session_state["loan_records"] if r["status"] == "Pending")
    at.session_state["selected_app_id"] = pending["application_id"]
    at.run()
    at.button(key=f"advance_{pending['application_id']}").click().run()
    assert not at.exception
    after_ca = [m for m in at.session_state["handoff_messages"] if m["to_role"] == "Credit analyst"]
    assert len(after_ca) == before_ca + 1
    assert after_ca[0]["application_id"] == pending["application_id"]


def test_maker_checker_approver_flow():
    at = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    # Credit analyst recommends Approve -> status becomes Pending Approval (NOT Approved)
    at.sidebar.selectbox(key="staff_role").select("Credit analyst").run()
    at.switch_page("app_pages/credit_assessment.py").run()
    case = next(r for r in at.session_state["loan_records"] if r["status"] == "Under Assessment")
    at.selectbox(key="assess_selected_app").select(case["application_id"]).run()
    # Select Recommend Approve inside analyst review form and submit
    rec_sb = next(sb for sb in at.selectbox if sb.label == "Analyst recommendation")
    rec_sb.select("Recommend Approve")
    next(b for b in at.button if b.label == "Submit recommendation").click().run()
    assert not at.exception
    updated = next(r for r in at.session_state["loan_records"] if r["application_id"] == case["application_id"])
    assert updated["status"] == "Pending Approval"

    # Loan manager approves it from the Approval queue -> status becomes Approved
    at.sidebar.selectbox(key="staff_role").select("Loan manager").run()
    at.switch_page("app_pages/loan_management.py").run()
    assert not at.exception
    at.button(key=f"mgr_approve_{case['application_id']}").click().run()
    assert not at.exception
    final = next(r for r in at.session_state["loan_records"] if r["application_id"] == case["application_id"])
    assert final["status"] == "Approved"


def test_role_network_live_simulation():
    at = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert not at.exception
    # AssistiveTouch floating button should be rendered on Dashboard
    fab = at.button(key="assistive_touch_btn")
    assert "Role Hub" in fab.label

    # Unified walkthrough uses existing case data without mutating records
    case = at.session_state["loan_records"][0]
    before_statuses = [r["status"] for r in at.session_state["loan_records"]]
    at.session_state["selected_app_id"] = case["application_id"]
    fab.click().run()
    assert not at.exception

    at.button(key="at_sim_step_btn").click().run()
    assert not at.exception
    assert at.session_state["at_sim_count"] == 1
    assert case["applicant_name"] in at.session_state["at_sim_current"]["text"]
    assert [r["status"] for r in at.session_state["loan_records"]] == before_statuses

    # AppTest reruns the whole script (closing the dialog), so reopen it before resetting
    at.button(key="assistive_touch_btn").click().run()
    at.button(key="at_sim_reset_btn").click().run()
    assert at.session_state["at_sim_count"] == 0
    assert at.session_state["at_sim_current"] is None
