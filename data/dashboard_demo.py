from datetime import date, timedelta

import pandas as pd
import streamlit as st


_APPLICATIONS = (
    ("APP-2108", "Maya Chen", 2, 28_500, "Low Risk", "Under review"),
    ("APP-2107", "Ethan Foster", 5, 42_000, "High Risk", "Under review"),
    ("APP-2106", "Sofia Patel", 9, 18_500, "Medium Risk", "Approved"),
    ("APP-2105", "Noah Williams", 13, 72_500, "High Risk", "Pending"),
    ("APP-2104", "Amara Okafor", 18, 33_000, "Low Risk", "Approved"),
    ("APP-2103", "Luca Rossi", 24, 16_750, "Medium Risk", "Approved"),
    ("APP-2102", "Priya Shah", 32, 90_000, "High Risk", "Declined"),
    ("APP-2101", "Oliver Kim", 44, 26_500, "Low Risk", "Under review"),
    ("APP-2100", "Elena Garcia", 58, 58_000, "Medium Risk", "Approved"),
    ("APP-2099", "Daniel Reed", 77, 41_000, "Low Risk", "Approved"),
    ("APP-2098", "Fatima Noor", 105, 125_000, "High Risk", "Pending"),
    ("APP-2097", "Grace Liu", 138, 27_500, "Low Risk", "Approved"),
    ("APP-2096", "Mateo Silva", 175, 62_000, "Medium Risk", "Approved"),
    ("APP-2095", "Amina Yusuf", 211, 49_000, "Low Risk", "Under review"),
    ("APP-2094", "Jamie Park", 269, 32_000, "Medium Risk", "Approved"),
    ("APP-2093", "Samira Khan", 333, 87_000, "High Risk", "Declined"),
)

_OVERDUE_DAYS = {
    "APP-2103": 3,
    "APP-2100": 11,
    "APP-2096": 26,
}

_MONTHLY_LOAN_AMOUNTS = (
    320_000, 338_000, 361_000, 355_000, 382_000, 401_000,
    428_000, 447_000, 463_000, 489_000, 515_000, 542_000,
)

_MONTHLY_APPLICATIONS = (38, 42, 45, 43, 49, 53, 58, 61, 65, 70, 76, 82)


@st.cache_data(show_spinner=False)
def create_dashboard_demo_data(reference_date=None):
    """Build clearly illustrative dashboard data relative to the given date."""
    today = reference_date or date.today()

    applications = pd.DataFrame(
        [
            {
                "Application ID": application_id,
                "Applicant": applicant,
                "Application Date": today - timedelta(days=days_ago),
                "Loan Amount": amount,
                "Risk Level": risk_level,
                "Status": status,
            }
            for application_id, applicant, days_ago, amount, risk_level, status
            in _APPLICATIONS
        ]
    )

    approved_applications = applications.loc[
        applications["Status"].eq("Approved")
    ]
    loans = pd.DataFrame(
        [
            {
                "Loan ID": f"LN-{application_id[-4:]}",
                "Application ID": application_id,
                "Origination Date": application_date,
                "Due Date": (
                    today - timedelta(days=_OVERDUE_DAYS[application_id])
                    if application_id in _OVERDUE_DAYS
                    else today + timedelta(days=14 + index * 3)
                ),
                "Loan Status": "Active",
                "Payment Status": (
                    "Overdue" if application_id in _OVERDUE_DAYS else "Current"
                ),
            }
            for index, (application_id, application_date) in enumerate(
                zip(
                    approved_applications["Application ID"],
                    approved_applications["Application Date"],
                )
            )
        ]
    )

    month_starts = pd.date_range(
        end=pd.Timestamp(today).replace(day=1),
        periods=12,
        freq="MS",
    )
    portfolio = pd.DataFrame(
        {
            "Month": month_starts,
            "Loan Amount": _MONTHLY_LOAN_AMOUNTS,
            "Applications": _MONTHLY_APPLICATIONS,
        }
    )

    payment_offsets = (
        2, 4, 8, 12, 18, 24, 31, 37, 44, 52, 61, 70,
        82, 96, 112, 130, 150, 171, 194, 221, 248, 280, 315, 350,
    )
    payments = pd.DataFrame(
        [
            {
                "Payment Date": today - timedelta(days=days_ago),
                "Payment Status": "Late" if index % 7 == 3 else "On-time",
            }
            for index, days_ago in enumerate(payment_offsets)
        ]
    )

    alerts = (
        {
            "severity": "high",
            "icon": "warning",
            "case_id": "APP-2107",
            "title": "Application review required",
            "description": "Manual review pending",
            "label": "HIGH PRIORITY",
        },
        {
            "severity": "warning",
            "icon": "schedule",
            "case_id": "LN-2103",
            "title": "Repayment overdue",
            "description": "3 days past due",
            "label": "OVERDUE",
        },
        {
            "severity": "info",
            "icon": "monitoring",
            "case_id": "APP-2105",
            "title": "Affordability follow-up",
            "description": "Awaiting assessment",
            "label": "FOLLOW-UP",
        },
    )

    return {
        "applications": applications,
        "loans": loans,
        "portfolio": portfolio,
        "payments": payments,
        "alerts": alerts,
    }
