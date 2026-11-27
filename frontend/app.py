"""FinGuard AI — Intelligent Credit Risk Assessment & Loan Lifecycle Management."""

from __future__ import annotations

import streamlit as st

from utils.assistive_network import render_assistive_touch
from utils.branding import render_page_banner, render_sidebar_brand, render_sidebar_footer
from utils.handoff import render_role_inbox
from utils.state import STAFF_ROLES, init_session_state

st.set_page_config(
    page_title="FinGuard AI",
    page_icon=":material/account_balance:",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()

# Sidebar branding and staff-role selector (prototype role-oriented navigation)
with st.sidebar:
    render_sidebar_brand()

    role_names = list(STAFF_ROLES.keys())
    selected_role = st.selectbox(
        "Staff role view",
        options=role_names,
        key="staff_role",
        help="Switch banking roles to preview role-oriented navigation (prototype only).",
    )
    role_meta = STAFF_ROLES[selected_role]
    st.caption(role_meta["description"])

    render_role_inbox(selected_role)
    st.badge("Demo data · Session only", icon=":material/science:", color="blue")
    render_sidebar_footer()

# Define all 7 FinGuard AI modules as native st.Page entries
ALL_PAGES = {
    "dashboard": st.Page(
        "app_pages/dashboard.py",
        title="Dashboard",
        url_path="dashboard",
        icon=":material/space_dashboard:",
        default=True,
        help="Portfolio snapshot, key lending KPIs, risk distribution, and priority alerts.",
    ),
    "loan-applications": st.Page(
        "app_pages/loan_applications.py",
        title="Loan applications",
        url_path="loan-applications",
        icon=":material/description:",
        help="Review, filter, create, and inspect customer loan applications.",
    ),
    "credit-assessment": st.Page(
        "app_pages/credit_assessment.py",
        title="Credit assessment",
        url_path="credit-assessment",
        icon=":material/verified_user:",
        help="Evaluate borrower risk indicators, financial inclusion signals, and analyst recommendations.",
    ),
    "debt-analysis": st.Page(
        "app_pages/debt_analysis.py",
        title="Debt analysis",
        url_path="debt-analysis",
        icon=":material/account_balance_wallet:",
        help="Analyze existing obligations, DTI/DSCR capacity, and borrower stress-test scenarios.",
    ),
    "loan-management": st.Page(
        "app_pages/loan_management.py",
        title="Loan management",
        url_path="loan-management",
        icon=":material/payments:",
        help="Manage disbursed loan accounts, amortization schedules, and repayment logging.",
    ),
    "risk-monitoring": st.Page(
        "app_pages/risk_monitoring.py",
        title="Risk monitoring",
        url_path="risk-monitoring",
        icon=":material/monitoring:",
        help="Track days past due (DPD), aging buckets, early-warning signals, and collection follow-ups.",
    ),
    "banking-analytics": st.Page(
        "app_pages/banking_analytics.py",
        title="Banking analytics",
        url_path="banking-analytics",
        icon=":material/analytics:",
        help="Portfolio composition, risk & inclusion breakdowns, and macro stress simulations.",
    ),
}

allowed = set(role_meta["pages"])
nav_sections: dict[str, list[st.Page]] = {}

overview = [ALL_PAGES[p] for p in ("dashboard",) if p in allowed]
origination = [
    ALL_PAGES[p]
    for p in ("loan-applications", "credit-assessment", "debt-analysis")
    if p in allowed
]
lifecycle = [
    ALL_PAGES[p]
    for p in ("loan-management", "risk-monitoring", "banking-analytics")
    if p in allowed
]

if overview:
    nav_sections["Overview"] = overview
if origination:
    nav_sections["Origination & assessment"] = origination
if lifecycle:
    nav_sections["Lifecycle & risk"] = lifecycle

current_page = st.navigation(nav_sections, position="sidebar")

# Shared executive page banner with subtle Cambodian banking accents
render_page_banner(
    title=current_page.title,
    role_short=role_meta["short"],
    subtitle="FinGuard AI · Intelligent Credit Risk Assessment & Loan Lifecycle Management",
)

current_page.run()

# Floating AssistiveTouch button pinned to bottom-right across every page
render_assistive_touch(selected_role)
