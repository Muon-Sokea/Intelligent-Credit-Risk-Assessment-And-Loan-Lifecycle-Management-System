import streamlit as st

from modules.app_shell import render_app_shell, synchronize_page_navigation
from utils.styles import load_css


st.set_page_config(
    page_title="FinGuard AI",
    page_icon=":material/account_balance:",
    layout="wide",
    initial_sidebar_state="expanded"
)

active_page = synchronize_page_navigation()
if "sidebar_collapsed" not in st.session_state:
    st.session_state.sidebar_collapsed = False
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

st.markdown(
    load_css(
        dark_mode=st.session_state.dark_mode,
        sidebar_collapsed=st.session_state.sidebar_collapsed
    ),
    unsafe_allow_html=True
)

render_app_shell(show_workspace=False)

if active_page == "Dashboard":
    from modules.dashboard import show_dashboard

    show_dashboard()
elif active_page == "Loan Applications":
    from modules.loan_application import show_loan_applications

    show_loan_applications()
elif active_page == "Credit Assessment":
    from modules.credit_assessment import render as show_credit_assessment

    show_credit_assessment()
elif active_page == "Debt & Affordability":
    from modules.debt_analysis import render as show_debt_analysis

    show_debt_analysis()
elif active_page == "Loan Monitoring":
    from modules.loan_monitoring import render as show_loan_monitoring

    show_loan_monitoring()
elif active_page == "Banking Analytics":
    from modules.banking_analytics import render as show_banking_analytics

    show_banking_analytics()
