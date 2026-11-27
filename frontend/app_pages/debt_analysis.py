"""FinGuard AI — Debt, over-indebtedness & stress-testing workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.calculations import (
    debt_service_coverage_ratio,
    debt_to_income_ratio,
    monthly_loan_payment,
)
from utils.state import get_record_by_id, get_records, refresh_record_metrics

st.caption(
    "Analyze borrower obligations, calculate DTI/DSCR repayment capacity, and simulate income or rate shocks "
    "to identify over-indebtedness early."
)

records = get_records()
if not records:
    st.info("No applications available.", icon=":material/info:")
    st.stop()

app_ids = [r["application_id"] for r in records]
default_idx = app_ids.index(st.session_state.selected_app_id) if st.session_state.selected_app_id in app_ids else 0

selected_id = st.selectbox(
    "Select borrower",
    options=app_ids,
    index=default_idx,
    format_func=lambda aid: next(
        f"{r['application_id']} · {r['applicant_name']} ({r['borrower_type']} · ${r['loan_amount']:,.0f})"
        for r in records
        if r["application_id"] == aid
    ),
    key="debt_selected_app",
)
st.session_state.selected_app_id = selected_id
record = get_record_by_id(selected_id)
if record is None:
    st.stop()

# Baseline metrics
income = float(record["monthly_income"])
expenses = float(record["monthly_expenses"])
existing_debt_pmt = float(record["monthly_debt_payment"])
loan_amount = float(record["loan_amount"])
term_months = int(record["loan_term_months"])
rate_pct = float(record["interest_rate"])

base_installment = monthly_loan_payment(loan_amount, rate_pct, term_months)
total_debt_service = existing_debt_pmt + base_installment
base_dti = debt_to_income_ratio(total_debt_service, income)
net_cash_flow = round(income - expenses - total_debt_service, 2)
dscr = debt_service_coverage_ratio(income - expenses, total_debt_service)

with st.grid(4, gap="medium"):
    st.metric("Monthly income", f"${income:,.0f}", f"Expenses ${expenses:,.0f}", delta_color="off", border=True, height="stretch")
    st.metric("Total debt service", f"${total_debt_service:,.0f}/mo", f"Existing ${existing_debt_pmt:,.0f} + New ${base_installment:,.0f}", delta_color="off", border=True, height="stretch")
    st.metric(
        "Projected DTI",
        f"{base_dti:.1f}%",
        "Over-indebtedness watch" if base_dti > 45 else "Within standard range",
        delta_color="inverse" if base_dti > 45 else "normal",
        border=True,
        height="stretch",
    )
    st.metric(
        "DSCR / Net surplus",
        f"{dscr:.2f}x" if dscr is not None else "N/A",
        f"Surplus ${net_cash_flow:,.0f}/mo",
        delta_color="normal" if net_cash_flow >= 0 else "inverse",
        border=True,
        height="stretch",
    )

tab_profile, tab_calc, tab_stress = st.tabs(
    [
        ":material/account_balance_wallet: Income & obligations",
        ":material/calculate: Loan calculator",
        ":material/bolt: Stress testing",
    ],
    on_change="rerun",
)

with tab_profile:
    if tab_profile.open:
        col_form, col_chart = st.columns([2, 3], gap="medium")
        with col_form:
            with st.container(border=True):
                st.subheader("Update financial inputs")
                with st.form(f"debt_inputs_form_{record['application_id']}"):
                    new_income = st.number_input("Monthly income / revenue ($)", min_value=100.0, value=income, step=100.0)
                    new_expenses = st.number_input("Monthly living / operating expenses ($)", min_value=0.0, value=expenses, step=50.0)
                    new_debt_bal = st.number_input("Existing debt balance ($)", min_value=0.0, value=float(record["existing_debt_balance"]), step=250.0)
                    new_debt_pmt = st.number_input("Existing monthly debt payments ($)", min_value=0.0, value=existing_debt_pmt, step=25.0)
                    save_fin = st.form_submit_button("Recalculate & save", type="primary", width="stretch")

                if save_fin:
                    record["monthly_income"] = float(new_income)
                    record["monthly_expenses"] = float(new_expenses)
                    record["existing_debt_balance"] = float(new_debt_bal)
                    record["monthly_debt_payment"] = float(new_debt_pmt)
                    refresh_record_metrics(record)
                    st.toast("Financial profile updated.", icon=":material/check_circle:")
                    st.rerun()

        with col_chart:
            with st.container(border=True):
                st.subheader("Monthly cash-flow allocation")
                alloc_df = pd.DataFrame(
                    {
                        "Category": [
                            "Living / operating expenses",
                            "Existing debt payments",
                            "Proposed loan installment",
                            "Remaining surplus",
                        ],
                        "Amount": [
                            round(expenses, 2),
                            round(existing_debt_pmt, 2),
                            round(base_installment, 2),
                            round(max(net_cash_flow, 0.0), 2),
                        ],
                    }
                )
                st.echarts_chart(
                    {
                        "tooltip": {"trigger": "axis", "valueFormatter": "dollar"},
                        "grid": {"left": 180, "right": 24, "top": 16, "bottom": 28},
                        "dataset": {"source": alloc_df},
                        "xAxis": {"type": "value"},
                        "yAxis": {"type": "category"},
                        "series": [
                            {
                                "type": "bar",
                                "barMaxWidth": 28,
                                "encode": {"x": "Amount", "y": "Category"},
                                "itemStyle": {"borderRadius": [0, 6, 6, 0]},
                            }
                        ],
                    },
                    height=280,
                    alt="Monthly cash-flow breakdown across expenses, debt service, and surplus",
                )

with tab_calc:
    if tab_calc.open:
        with st.container(border=True):
            st.subheader("Interactive fixed-rate loan calculator")
            c1, c2, c3 = st.columns(3)
            sim_amount = c1.number_input("Loan principal ($)", min_value=500.0, value=loan_amount, step=500.0, key="calc_amt")
            sim_rate = c2.number_input("Annual interest rate (%)", min_value=0.0, max_value=36.0, value=rate_pct, step=0.25, key="calc_rate")
            sim_term = c3.number_input("Term (months)", min_value=6, max_value=240, value=term_months, step=6, key="calc_term")

            sim_pmt = monthly_loan_payment(sim_amount, sim_rate, int(sim_term))
            total_repaid = round(sim_pmt * int(sim_term), 2)
            total_interest = round(max(total_repaid - sim_amount, 0.0), 2)
            sim_dti = debt_to_income_ratio(existing_debt_pmt + sim_pmt, income)

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Monthly payment", f"${sim_pmt:,.2f}")
            r2.metric("Total interest", f"${total_interest:,.2f}")
            r3.metric("Total repayment", f"${total_repaid:,.2f}")
            r4.metric("Resulting DTI", f"{sim_dti:.1f}%")

with tab_stress:
    if tab_stress.open:
        with st.container(border=True):
            st.subheader("Borrower stress-test simulator")
            st.caption(
                "Test how income drops, interest-rate increases, or higher living costs impact repayment capacity. "
                "Scenarios are illustrative and do not alter the original application."
            )
            s1, s2, s3 = st.columns(3)
            income_shock = s1.slider("Income / revenue change (%)", min_value=-40, max_value=20, value=-15, step=5)
            rate_shock = s2.slider("Interest rate shock (pp)", min_value=-2.0, max_value=6.0, value=2.0, step=0.5)
            expense_shock = s3.slider("Expense increase (%)", min_value=0, max_value=40, value=10, step=5)

            stressed_income = max(income * (1 + income_shock / 100.0), 1.0)
            stressed_expenses = expenses * (1 + expense_shock / 100.0)
            stressed_rate = max(rate_pct + rate_shock, 0.0)
            stressed_pmt = monthly_loan_payment(loan_amount, stressed_rate, term_months)
            stressed_total_debt = existing_debt_pmt + stressed_pmt
            stressed_dti = debt_to_income_ratio(stressed_total_debt, stressed_income)
            stressed_surplus = round(stressed_income - stressed_expenses - stressed_total_debt, 2)

            compare_df = pd.DataFrame(
                {
                    "Metric": ["Monthly income ($)", "Loan installment ($)", "Projected DTI (%)", "Monthly surplus ($)"],
                    "Baseline": [round(income, 2), round(base_installment, 2), round(base_dti, 1), round(net_cash_flow, 2)],
                    "Stressed": [round(stressed_income, 2), round(stressed_pmt, 2), round(stressed_dti, 1), round(stressed_surplus, 2)],
                }
            )
            st.dataframe(compare_df, hide_index=True, alt="Baseline versus stressed borrower financial metrics")

            if stressed_surplus < 0 or stressed_dti > 55:
                st.warning(
                    f"Under this stress scenario, DTI rises to {stressed_dti:.1f}% with a monthly surplus of ${stressed_surplus:,.0f}. "
                    "Consider smaller principal, longer tenure, or additional collateral.",
                    icon=":material/warning:",
                )
            else:
                st.success(
                    f"Borrower remains resilient under this scenario (DTI {stressed_dti:.1f}%, surplus ${stressed_surplus:,.0f}/mo).",
                    icon=":material/check_circle:",
                )
