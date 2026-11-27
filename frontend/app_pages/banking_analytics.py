"""FinGuard AI — Banking risk analytics & macro scenario simulation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.calculations import debt_to_income_ratio, monthly_loan_payment
from utils.state import LOAN_PURPOSES, get_records, records_to_dataframe

st.caption(
    "Portfolio-level composition, financial inclusion comparisons, and macro-economic stress simulations "
    "built from shared in-session records."
)

df = records_to_dataframe()

# Global analytical filters
with st.container(border=True):
    f1, f2, f3 = st.columns(3)
    sel_purposes = f1.multiselect("Loan purpose", options=list(LOAN_PURPOSES), default=[], placeholder="All purposes")
    sel_types = f2.multiselect("Borrower type", options=["Personal", "Business"], default=[], placeholder="All types")
    sel_risks = f3.multiselect("Risk tier", options=["Low Risk", "Medium Risk", "High Risk"], default=[], placeholder="All tiers")

filtered = df.copy()
if sel_purposes:
    filtered = filtered[filtered["Purpose"].isin(sel_purposes)]
if sel_types:
    filtered = filtered[filtered["Type"].isin(sel_types)]
if sel_risks:
    filtered = filtered[filtered["Risk Tier"].isin(sel_risks)]

if filtered.empty:
    st.info("No records match the selected filters.", icon=":material/info:")
    st.stop()

with st.grid(4, gap="medium"):
    st.metric("Total exposure", f"${filtered['Loan Amount'].sum():,.0f}", f"{len(filtered)} applications", delta_color="off", border=True, height="stretch")
    st.metric("Average loan size", f"${filtered['Loan Amount'].mean():,.0f}", border=True, height="stretch")
    st.metric("Average projected DTI", f"{filtered['Projected DTI (%)'].mean():.1f}%", border=True, height="stretch")
    thin_pct = (filtered["Thin File"].mean()) * 100.0
    st.metric("Thin-file share", f"{thin_pct:.0f}%", f"{int(filtered['Thin File'].sum())} applicants", delta_color="off", border=True, height="stretch")

tab_mix, tab_inclusion, tab_macro = st.tabs(
    [
        ":material/pie_chart: Portfolio mix",
        ":material/diversity_3: Risk & financial inclusion",
        ":material/trending_down: Economic stress test",
    ],
    on_change="rerun",
)

with tab_mix:
    if tab_mix.open:
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            with st.container(border=True):
                st.subheader("Exposure by status")
                status_df = filtered.groupby("Status", as_index=False)["Loan Amount"].sum()
                st.echarts_chart(
                    {
                        "tooltip": {"trigger": "axis", "valueFormatter": "dollar"},
                        "grid": {"left": 60, "right": 16, "top": 20, "bottom": 42},
                        "dataset": {"source": status_df},
                        "xAxis": {"type": "category"},
                        "yAxis": {"type": "value"},
                        "series": [{"type": "bar", "barMaxWidth": 36, "itemStyle": {"borderRadius": [6, 6, 0, 0]}}],
                    },
                    height=300,
                    alt="Total loan exposure grouped by application and lifecycle status",
                )
        with c2:
            with st.container(border=True):
                st.subheader("Exposure by borrower type")
                type_df = filtered.groupby("Type", as_index=False)["Loan Amount"].sum()
                st.echarts_chart(
                    {
                        "tooltip": {"trigger": "item", "valueFormatter": "dollar"},
                        "legend": {"bottom": 0},
                        "dataset": {"source": type_df},
                        "series": [
                            {
                                "type": "pie",
                                "radius": ["46%", "72%"],
                                "center": ["50%", "44%"],
                                "encode": {"itemName": "Type", "value": "Loan Amount"},
                            }
                        ],
                    },
                    height=300,
                    alt="Share of loan exposure between Personal and Business borrowers",
                )

with tab_inclusion:
    if tab_inclusion.open:
        with st.container(border=True):
            st.subheader("Thin-file vs. traditional credit profile comparison")
            inc_summary = (
                filtered.assign(Segment=filtered["Thin File"].map({True: "Thin Credit File", False: "Traditional File"}))
                .groupby("Segment", as_index=False)
                .agg(
                    Applications=("Application ID", "count"),
                    Avg_Loan=("Loan Amount", "mean"),
                    Avg_DTI=("Projected DTI (%)", "mean"),
                    Avg_PD=("PD (%)", "mean"),
                )
            )
            st.dataframe(
                inc_summary,
                hide_index=True,
                column_config={
                    "Avg_Loan": st.column_config.NumberColumn("Avg. loan", format="$%,.0f"),
                    "Avg_DTI": st.column_config.NumberColumn("Avg. DTI", format="%.1f%%"),
                    "Avg_PD": st.column_config.NumberColumn("Avg. indicative PD", format="%.1f%%"),
                },
                alt="Comparison of thin-file versus traditional credit file applicants",
            )

with tab_macro:
    if tab_macro.open:
        with st.container(border=True):
            st.subheader("Macro-economic impact simulator")
            st.caption(
                "Simulate how a broad economic downturn (borrower income decline or benchmark rate hike) "
                "affects portfolio-wide DTI and high-risk concentration."
            )
            s1, s2 = st.columns(2)
            macro_income_shock = s1.slider("Portfolio borrower income shock (%)", -35, 10, -15, 5, key="macro_inc")
            macro_rate_shock = s2.slider("Benchmark interest rate shift (pp)", -1.0, 5.0, 1.5, 0.5, key="macro_rate")

            stressed_rows = []
            for rec in get_records():
                if rec["application_id"] not in set(filtered["Application ID"]):
                    continue
                base_dti = float(rec["projected_dti"])
                st_inc = max(float(rec["monthly_income"]) * (1 + macro_income_shock / 100.0), 1.0)
                st_rate = max(float(rec["interest_rate"]) + macro_rate_shock, 0.0)
                st_pmt = monthly_loan_payment(float(rec["loan_amount"]), st_rate, int(rec["loan_term_months"]))
                st_dti = debt_to_income_ratio(float(rec["monthly_debt_payment"]) + st_pmt, st_inc)
                stressed_rows.append(
                    {
                        "Application ID": rec["application_id"],
                        "Purpose": rec["loan_purpose"],
                        "Loan Amount": float(rec["loan_amount"]),
                        "Baseline DTI (%)": base_dti,
                        "Stressed DTI (%)": st_dti,
                        "DTI Shift (pp)": round(st_dti - base_dti, 1),
                        "Stressed Flag": "High Stress" if st_dti > 50 else "Watch" if st_dti > 40 else "Resilient",
                    }
                )
            stress_df = pd.DataFrame(stressed_rows)

            m1, m2, m3 = st.columns(3)
            m1.metric("Baseline avg. DTI", f"{stress_df['Baseline DTI (%)'].mean():.1f}%")
            m2.metric(
                "Stressed avg. DTI",
                f"{stress_df['Stressed DTI (%)'].mean():.1f}%",
                f"+{stress_df['DTI Shift (pp)'].mean():.1f} pp",
                delta_color="inverse",
            )
            high_stress_exp = stress_df.loc[stress_df["Stressed Flag"] == "High Stress", "Loan Amount"].sum()
            m3.metric("High-stress exposure (DTI > 50%)", f"${high_stress_exp:,.0f}")

            st.dataframe(
                stress_df,
                hide_index=True,
                column_config={
                    "Loan Amount": st.column_config.NumberColumn("Loan amount", format="$%,.0f"),
                },
                alt="Portfolio-level macro stress test results by application",
            )
            st.download_button(
                "Export stress-test CSV",
                data=stress_df.to_csv(index=False).encode("utf-8"),
                file_name="finguard_macro_stress_test.csv",
                mime="text/csv",
                icon=":material/download:",
            )
