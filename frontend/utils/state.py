"""Shared session-state store and illustrative FinGuard AI banking records."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from utils.calculations import (
    build_amortization_schedule,
    calculate_dpd_and_bucket,
    illustrative_risk_assessment,
)

STAFF_ROLES: dict[str, dict[str, Any]] = {
    "All roles (full preview)": {
        "short": "All roles",
        "description": "Full access to all seven FinGuard AI prototype modules.",
        "pages": [
            "dashboard",
            "loan-applications",
            "credit-assessment",
            "debt-analysis",
            "loan-management",
            "risk-monitoring",
            "banking-analytics",
        ],
    },
    "Loan officer": {
        "short": "Loan officer",
        "description": "Applicant intake, document verification, and affordability checks.",
        "pages": ["dashboard", "loan-applications", "debt-analysis"],
    },
    "Credit analyst": {
        "short": "Credit analyst",
        "description": "Default risk review, financial inclusion assessment, and debt analysis.",
        "pages": ["dashboard", "loan-applications", "credit-assessment", "debt-analysis"],
    },
    "Loan manager": {
        "short": "Loan manager",
        "description": "Approved loan servicing, repayment schedules, and overdue follow-up.",
        "pages": ["dashboard", "loan-management", "risk-monitoring", "banking-analytics"],
    },
    "Risk management officer": {
        "short": "Risk officer",
        "description": "Early-warning alerts, portfolio quality, and macro stress testing.",
        "pages": ["dashboard", "credit-assessment", "risk-monitoring", "banking-analytics"],
    },
    "Customer service officer": {
        "short": "Customer service",
        "description": "Loan terms, balances, and repayment schedules for borrower inquiries.",
        "pages": ["dashboard", "loan-management"],
    },
}

LOAN_PURPOSES = ("Business", "Personal", "Home", "Education", "Agriculture", "Vehicle")
APPLICATION_STATUSES = (
    "Pending",
    "Under Review",
    "Under Assessment",
    "Pending Approval",
    "Approved",
    "Disbursed",
    "Fully Repaid",
    "Rejected",
)


def _make_initial_records(reference_date: date | None = None) -> list[dict[str, Any]]:
    """Build cohesive, clearly labelled illustrative banking records."""
    today = reference_date or date.today()

    raw_templates: list[dict[str, Any]] = [
        {
            "application_id": "FG-2026-0101",
            "applicant_name": "Sokha Dara",
            "borrower_type": "Business",
            "phone": "+855 12 401 101",
            "email": "sokha.dara@demo.invalid",
            "province": "Phnom Penh",
            "employment_status": "Business owner",
            "occupation": "Wholesale grocery distributor",
            "work_experience_years": 7,
            "monthly_income": 6800.0,
            "monthly_expenses": 3100.0,
            "existing_debt_balance": 9500.0,
            "monthly_debt_payment": 480.0,
            "loan_amount": 35000.0,
            "loan_purpose": "Business",
            "loan_term_months": 36,
            "interest_rate": 11.0,
            "days_ago": 195,
            "status": "Disbursed",
            "thin_file": False,
            "alt_data_verified": True,
            "docs_verified": {"ID / KYC": True, "Income Proof": True, "Bank Statements": True, "Collateral": True},
            "disbursed_days_ago": 185,
            "paid_installments": 6,
            "partial_payment": 0.0,
            "analyst_notes": "Strong wholesale cash flow and consistent bank turnover.",
            "recommendation": "Approve with standard quarterly check-in",
        },
        {
            "application_id": "FG-2026-0102",
            "applicant_name": "Vannak Chan",
            "borrower_type": "Personal",
            "phone": "+855 17 502 204",
            "email": "vannak.chan@demo.invalid",
            "province": "Siem Reap",
            "employment_status": "Full-time",
            "occupation": "Hospitality operations lead",
            "work_experience_years": 5,
            "monthly_income": 2400.0,
            "monthly_expenses": 1150.0,
            "existing_debt_balance": 4200.0,
            "monthly_debt_payment": 240.0,
            "loan_amount": 12000.0,
            "loan_purpose": "Personal",
            "loan_term_months": 24,
            "interest_rate": 12.5,
            "days_ago": 160,
            "status": "Disbursed",
            "thin_file": True,
            "alt_data_verified": True,
            "docs_verified": {"ID / KYC": True, "Income Proof": True, "Bank Statements": True, "Collateral": False},
            "disbursed_days_ago": 152,
            "paid_installments": 4,
            "partial_payment": 200.0,
            "analyst_notes": "Thin bureau history supplemented with 12-month payroll & utility records.",
            "recommendation": "Approve (financial inclusion review)",
        },
        {
            "application_id": "FG-2026-0103",
            "applicant_name": "Channary Kim",
            "borrower_type": "Business",
            "phone": "+855 89 310 882",
            "email": "channary.kim@demo.invalid",
            "province": "Battambang",
            "employment_status": "Self-employed",
            "occupation": "Rice milling & logistics",
            "work_experience_years": 9,
            "monthly_income": 5400.0,
            "monthly_expenses": 2950.0,
            "existing_debt_balance": 18500.0,
            "monthly_debt_payment": 920.0,
            "loan_amount": 42000.0,
            "loan_purpose": "Agriculture",
            "loan_term_months": 36,
            "interest_rate": 10.5,
            "days_ago": 240,
            "status": "Disbursed",
            "thin_file": False,
            "alt_data_verified": False,
            "docs_verified": {"ID / KYC": True, "Income Proof": True, "Bank Statements": True, "Collateral": True},
            "disbursed_days_ago": 230,
            "paid_installments": 5,
            "partial_payment": 0.0,
            "analyst_notes": "Seasonal harvest revenue; monitor debt burden closely.",
            "recommendation": "Approve with seasonal monitoring",
        },
        {
            "application_id": "FG-2026-0104",
            "applicant_name": "Rithy Meas",
            "borrower_type": "Personal",
            "phone": "+855 77 884 119",
            "email": "rithy.meas@demo.invalid",
            "province": "Phnom Penh",
            "employment_status": "Full-time",
            "occupation": "Senior civil engineer",
            "work_experience_years": 11,
            "monthly_income": 4900.0,
            "monthly_expenses": 1900.0,
            "existing_debt_balance": 6000.0,
            "monthly_debt_payment": 310.0,
            "loan_amount": 65000.0,
            "loan_purpose": "Home",
            "loan_term_months": 120,
            "interest_rate": 8.9,
            "days_ago": 130,
            "status": "Disbursed",
            "thin_file": False,
            "alt_data_verified": True,
            "docs_verified": {"ID / KYC": True, "Income Proof": True, "Bank Statements": True, "Collateral": True},
            "disbursed_days_ago": 120,
            "paid_installments": 4,
            "partial_payment": 0.0,
            "analyst_notes": "Low leverage and verified property collateral.",
            "recommendation": "Approve",
        },
        {
            "application_id": "FG-2026-0105",
            "applicant_name": "Bopha Lim",
            "borrower_type": "Business",
            "phone": "+855 96 441 720",
            "email": "bopha.lim@demo.invalid",
            "province": "Kandal",
            "employment_status": "Business owner",
            "occupation": "Garment subcontractor",
            "work_experience_years": 4,
            "monthly_income": 4100.0,
            "monthly_expenses": 2650.0,
            "existing_debt_balance": 21000.0,
            "monthly_debt_payment": 1150.0,
            "loan_amount": 28000.0,
            "loan_purpose": "Business",
            "loan_term_months": 24,
            "interest_rate": 13.0,
            "days_ago": 14,
            "status": "Under Assessment",
            "thin_file": False,
            "alt_data_verified": False,
            "docs_verified": {"ID / KYC": True, "Income Proof": True, "Bank Statements": False, "Collateral": True},
            "analyst_notes": "Elevated existing debt service; verifying second MFI facility.",
            "recommendation": "Pending analyst review",
        },
        {
            "application_id": "FG-2026-0106",
            "applicant_name": "Piseth Nhem",
            "borrower_type": "Personal",
            "phone": "+855 15 229 603",
            "email": "piseth.nhem@demo.invalid",
            "province": "Phnom Penh",
            "employment_status": "Full-time",
            "occupation": "Software developer",
            "work_experience_years": 3,
            "monthly_income": 2800.0,
            "monthly_expenses": 1050.0,
            "existing_debt_balance": 1200.0,
            "monthly_debt_payment": 95.0,
            "loan_amount": 9500.0,
            "loan_purpose": "Education",
            "loan_term_months": 24,
            "interest_rate": 9.5,
            "days_ago": 7,
            "status": "Under Assessment",
            "thin_file": True,
            "alt_data_verified": True,
            "docs_verified": {"ID / KYC": True, "Income Proof": True, "Bank Statements": True, "Collateral": False},
            "analyst_notes": "No prior bank loans; strong salary deposits and zero missed utility bills.",
            "recommendation": "Pending analyst review",
        },
        {
            "application_id": "FG-2026-0107",
            "applicant_name": "Sreypov Heng",
            "borrower_type": "Personal",
            "phone": "+855 92 773 418",
            "email": "sreypov.heng@demo.invalid",
            "province": "Kampong Cham",
            "employment_status": "Self-employed",
            "occupation": "Pharmacy owner",
            "work_experience_years": 6,
            "monthly_income": 3500.0,
            "monthly_expenses": 1600.0,
            "existing_debt_balance": 3500.0,
            "monthly_debt_payment": 180.0,
            "loan_amount": 18000.0,
            "loan_purpose": "Business",
            "loan_term_months": 36,
            "interest_rate": 11.2,
            "days_ago": 4,
            "status": "Approved",
            "thin_file": False,
            "alt_data_verified": True,
            "docs_verified": {"ID / KYC": True, "Income Proof": True, "Bank Statements": True, "Collateral": True},
            "analyst_notes": "Credit committee approved; awaiting disbursement setup.",
            "recommendation": "Approve",
        },
        {
            "application_id": "FG-2026-0108",
            "applicant_name": "Daro Keo",
            "borrower_type": "Personal",
            "phone": "+855 10 618 905",
            "email": "daro.keo@demo.invalid",
            "province": "Phnom Penh",
            "employment_status": "Contract",
            "occupation": "Independent logistics driver",
            "work_experience_years": 2,
            "monthly_income": 1650.0,
            "monthly_expenses": 980.0,
            "existing_debt_balance": 5800.0,
            "monthly_debt_payment": 340.0,
            "loan_amount": 14000.0,
            "loan_purpose": "Vehicle",
            "loan_term_months": 36,
            "interest_rate": 13.5,
            "days_ago": 2,
            "status": "Pending",
            "thin_file": True,
            "alt_data_verified": False,
            "docs_verified": {"ID / KYC": True, "Income Proof": False, "Bank Statements": False, "Collateral": False},
            "analyst_notes": "Awaiting mobile-money statements and vehicle valuation.",
            "recommendation": "Pending initial review",
        },
        {
            "application_id": "FG-2026-0109",
            "applicant_name": "Kosal Prak",
            "borrower_type": "Personal",
            "phone": "+855 88 904 312",
            "email": "kosal.prak@demo.invalid",
            "province": "Preah Sihanouk",
            "employment_status": "Full-time",
            "occupation": "Port supervisor",
            "work_experience_years": 8,
            "monthly_income": 3200.0,
            "monthly_expenses": 1350.0,
            "existing_debt_balance": 0.0,
            "monthly_debt_payment": 0.0,
            "loan_amount": 10000.0,
            "loan_purpose": "Personal",
            "loan_term_months": 12,
            "interest_rate": 10.0,
            "days_ago": 390,
            "status": "Fully Repaid",
            "thin_file": False,
            "alt_data_verified": True,
            "docs_verified": {"ID / KYC": True, "Income Proof": True, "Bank Statements": True, "Collateral": False},
            "disbursed_days_ago": 385,
            "paid_installments": 12,
            "partial_payment": 0.0,
            "analyst_notes": "All 12 installments paid on time.",
            "recommendation": "Approve",
        },
        {
            "application_id": "FG-2026-0110",
            "applicant_name": "Sovannarith Tep",
            "borrower_type": "Business",
            "phone": "+855 11 337 540",
            "email": "sovannarith.tep@demo.invalid",
            "province": "Phnom Penh",
            "employment_status": "Self-employed",
            "occupation": "Electronics reseller",
            "work_experience_years": 1,
            "monthly_income": 2100.0,
            "monthly_expenses": 1450.0,
            "existing_debt_balance": 19000.0,
            "monthly_debt_payment": 890.0,
            "loan_amount": 25000.0,
            "loan_purpose": "Business",
            "loan_term_months": 24,
            "interest_rate": 14.0,
            "days_ago": 28,
            "status": "Rejected",
            "thin_file": False,
            "alt_data_verified": False,
            "docs_verified": {"ID / KYC": True, "Income Proof": True, "Bank Statements": True, "Collateral": False},
            "analyst_notes": "Declined due to severe over-indebtedness (projected DTI > 90%).",
            "recommendation": "Decline — excessive debt burden",
        },
    ]

    records: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_templates, start=1):
        app_date = today - timedelta(days=item["days_ago"])
        assessment = illustrative_risk_assessment(item)

        record: dict[str, Any] = {
            **{k: v for k, v in item.items() if k not in {"days_ago", "disbursed_days_ago", "paid_installments", "partial_payment"}},
            "application_date": app_date,
            "risk_tier": assessment["tier"],
            "risk_pd_pct": assessment["pd_pct"],
            "projected_dti": assessment["projected_dti"],
            "estimated_installment": assessment["estimated_installment"],
            "loan_account_id": None,
            "disbursed_date": None,
            "repayment_schedule": [],
            "payments": [],
            "collection_logs": [],
            "activity_log": [
                {
                    "timestamp": datetime.combine(app_date, datetime.min.time(), tzinfo=timezone.utc)
                    .strftime("%Y-%m-%d %H:%M UTC"),
                    "actor": "Loan officer",
                    "event": f"Application {item['application_id']} created (demo data)",
                }
            ],
        }

        if item["status"] in {"Disbursed", "Fully Repaid"}:
            disb_date = today - timedelta(days=item["disbursed_days_ago"])
            first_due = disb_date + timedelta(days=30)
            schedule = build_amortization_schedule(
                principal=item["loan_amount"],
                annual_rate_pct=item["interest_rate"],
                months=item["loan_term_months"],
                first_due_date=first_due,
                paid_installments=item["paid_installments"],
                partial_payment=item["partial_payment"],
            )
            record["loan_account_id"] = f"LN-2026-{idx:04d}"
            record["disbursed_date"] = disb_date
            record["repayment_schedule"] = schedule
            record["payments"] = [
                {
                    "payment_id": f"PAY-{idx:02d}-{row['installment_no']:02d}",
                    "payment_date": row["due_date"] - timedelta(days=1),
                    "amount": row["amount_paid"],
                    "method": "Bank transfer",
                    "notes": f"Installment #{row['installment_no']}",
                }
                for row in schedule
                if row["amount_paid"] > 0
            ]
            dpd, _, _ = calculate_dpd_and_bucket(schedule, as_of=today)
            if dpd > 0:
                record["collection_logs"].append(
                    {
                        "date": (today - timedelta(days=min(dpd, 3))).isoformat(),
                        "officer": "Loan manager",
                        "channel": "Phone call",
                        "outcome": "Borrower contacted — requested short grace window",
                        "promise_date": (today + timedelta(days=5)).isoformat(),
                    }
                )

        records.append(record)

    return records


def _make_initial_handoffs() -> list[dict[str, Any]]:
    """Seed illustrative inter-role handoff messages so the Role Inbox is live on launch."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return [
        {
            "id": "HO-0001",
            "timestamp": now_str,
            "from_role": "Loan officer",
            "to_role": "Credit analyst",
            "application_id": "FG-2026-0105",
            "subject": "Submitted for credit assessment",
            "message": "Bopha Lim application ready for review. Please check existing MFI debt service.",
            "target_page": "app_pages/credit_assessment.py",
            "target_slug": "credit-assessment",
            "read": False,
        },
        {
            "id": "HO-0002",
            "timestamp": now_str,
            "from_role": "Credit analyst",
            "to_role": "Loan manager",
            "application_id": "FG-2026-0107",
            "subject": "Approved — ready for disbursement",
            "message": "Sreypov Heng ($18,000) approved by credit review. Ready for disbursement and schedule setup.",
            "target_page": "app_pages/loan_management.py",
            "target_slug": "loan-management",
            "read": False,
        },
        {
            "id": "HO-0003",
            "timestamp": now_str,
            "from_role": "Risk management officer",
            "to_role": "Loan manager",
            "application_id": "FG-2026-0103",
            "subject": "Early-warning DPD alert",
            "message": "Channary Kim (LN-2026-0003) has overdue installments. Please follow up on seasonal repayment.",
            "target_page": "app_pages/risk_monitoring.py",
            "target_slug": "risk-monitoring",
            "read": False,
        },
    ]


def init_session_state() -> None:
    """Initialize FinGuard AI shared session state once per user session."""
    if "staff_role" not in st.session_state:
        st.session_state.staff_role = "All roles (full preview)"
    if "loan_records" not in st.session_state:
        st.session_state.loan_records = _make_initial_records()
    if "selected_app_id" not in st.session_state:
        st.session_state.selected_app_id = st.session_state.loan_records[0]["application_id"]
    if "handoff_messages" not in st.session_state:
        st.session_state.handoff_messages = _make_initial_handoffs()


def add_handoff(
    from_role: str,
    to_role: str,
    application_id: str,
    subject: str,
    message: str,
    target_page: str = "app_pages/dashboard.py",
    target_slug: str = "dashboard",
) -> dict[str, Any]:
    """Create a new inter-role handoff notification in session state."""
    init_session_state()
    items = st.session_state.handoff_messages
    entry = {
        "id": f"HO-{len(items) + 1:04d}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "from_role": from_role,
        "to_role": to_role,
        "application_id": application_id,
        "subject": subject,
        "message": message,
        "target_page": target_page,
        "target_slug": target_slug,
        "read": False,
    }
    items.insert(0, entry)
    return entry


def get_handoffs_for_role(role_name: str) -> list[dict[str, Any]]:
    """Return handoff messages addressed to a role (or all messages in All roles view)."""
    init_session_state()
    items = st.session_state.handoff_messages
    if role_name == "All roles (full preview)":
        return items
    return [m for m in items if m["to_role"] == role_name]


def mark_handoff_read(handoff_id: str) -> None:
    """Mark a handoff message as read."""
    init_session_state()
    for item in st.session_state.handoff_messages:
        if item["id"] == handoff_id:
            item["read"] = True
            break


def get_records() -> list[dict[str, Any]]:
    """Return the shared list of loan application & lifecycle records."""
    init_session_state()
    return st.session_state.loan_records


def get_record_by_id(app_id: str) -> dict[str, Any] | None:
    """Look up a single record by application ID."""
    for rec in get_records():
        if rec["application_id"] == app_id:
            return rec
    return None


def records_to_dataframe(records: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    """Convert session records into a summary DataFrame with live monitoring metrics."""
    items = records if records is not None else get_records()
    today = date.today()
    rows: list[dict[str, Any]] = []
    for rec in items:
        schedule = rec.get("repayment_schedule") or []
        dpd, bucket, overdue_amt = calculate_dpd_and_bucket(schedule, as_of=today)
        outstanding = round(
            sum(
                max(row["scheduled_principal"] - max(row["amount_paid"] - row["scheduled_interest"], 0.0), 0.0)
                for row in schedule
            ),
            2,
        )
        rows.append(
            {
                "Application ID": rec["application_id"],
                "Loan Account": rec.get("loan_account_id") or "—",
                "Applicant": rec["applicant_name"],
                "Type": rec["borrower_type"],
                "Purpose": rec["loan_purpose"],
                "Date": rec["application_date"],
                "Loan Amount": float(rec["loan_amount"]),
                "Term (mo)": int(rec["loan_term_months"]),
                "Rate (%)": float(rec["interest_rate"]),
                "Monthly Income": float(rec["monthly_income"]),
                "Projected DTI (%)": float(rec["projected_dti"]),
                "Risk Tier": rec["risk_tier"],
                "PD (%)": float(rec["risk_pd_pct"]),
                "Thin File": bool(rec.get("thin_file", False)),
                "Status": rec["status"],
                "Outstanding": outstanding,
                "DPD": dpd,
                "Aging Bucket": bucket,
                "Overdue Amount": overdue_amt,
            }
        )
    return pd.DataFrame(rows)


def next_application_id() -> str:
    """Generate the next sequential FinGuard application ID."""
    records = get_records()
    max_num = 100
    for rec in records:
        parts = rec["application_id"].split("-")
        if parts and parts[-1].isdigit():
            max_num = max(max_num, int(parts[-1]))
    return f"FG-2026-{max_num + 1:04d}"


def refresh_record_metrics(record: dict[str, Any]) -> None:
    """Recompute illustrative risk and DTI fields after an edit."""
    assessment = illustrative_risk_assessment(record)
    record["risk_tier"] = assessment["tier"]
    record["risk_pd_pct"] = assessment["pd_pct"]
    record["projected_dti"] = assessment["projected_dti"]
    record["estimated_installment"] = assessment["estimated_installment"]
