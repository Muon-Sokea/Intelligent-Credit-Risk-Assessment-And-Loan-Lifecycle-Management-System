"""FinGuard AI — Dashboard overview page."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from utils.state import records_to_dataframe

st.caption(
    "Portfolio overview based on illustrative in-session banking records. "
    "Model indicators support human review and are not automated lending decisions."
)

df = records_to_dataframe()

# Period filter bar
top_left, top_right = st.columns([3, 2], vertical_alignment="center")
with top_left:
    period = st.segmented_control(
        "Reporting window",
        options=["30D", "90D", "12M", "All"],
        default="All",
        key="dashboard_period",
        label_visibility="collapsed",
    )
with top_right:
    st.caption(f"As of {date.today().strftime('%d %b %Y')} · {len(df)} total records in session", text_alignment="right")

today = date.today()
if period == "30D":
    filtered = df[df["Date"] >= today - timedelta(days=30)]
elif period == "90D":
    filtered = df[df["Date"] >= today - timedelta(days=90)]
elif period == "12M":
    filtered = df[df["Date"] >= today - timedelta(days=365)]
else:
    filtered = df

active_loans = filtered[filtered["Status"] == "Disbursed"]
review_queue = filtered[filtered["Status"].isin(["Pending", "Under Review", "Under Assessment", "Pending Approval"])]
overdue_accounts = active_loans[active_loans["DPD"] > 0]
high_risk_count = int((filtered["Risk Tier"] == "High Risk").sum())

# KPI grid with sparklines
with st.grid(4, gap="medium"):
    st.metric(
        "Total applications",
        f"{len(filtered)}",
        f"{len(review_queue)} in review",
        delta_color="off",
        border=True,
        height="stretch",
        chart_data=[4, 5, 6, 7, 8, 9, len(filtered)],
        chart_type="area",
    )
    st.metric(
        "Active portfolio",
        f"${active_loans['Outstanding'].sum():,.0f}",
        f"{len(active_loans)} active loans",
        delta_color="normal",
        border=True,
        height="stretch",
        chart_data=[82, 94, 105, 118, 129, 136, round(active_loans["Outstanding"].sum() / 1000, 1)],
        chart_type="line",
    )
    st.metric(
        "High-risk flagged",
        f"{high_risk_count}",
        f"{(high_risk_count / max(len(filtered), 1)) * 100:.0f}% of window",
        delta_color="inverse" if high_risk_count > 0 else "off",
        border=True,
        height="stretch",
        chart_data=[2, 2, 3, 2, 3, 3, high_risk_count],
        chart_type="bar",
    )
    st.metric(
        "Overdue accounts",
        f"{len(overdue_accounts)}",
        f"${overdue_accounts['Overdue Amount'].sum():,.0f} past due",
        delta_color="inverse" if len(overdue_accounts) > 0 else "off",
        border=True,
        height="stretch",
        chart_data=[0, 1, 1, 2, 1, 2, len(overdue_accounts)],
        chart_type="bar",
    )

# Operational charts row (Apache ECharts — auto-themed for light & dark mode)
chart_col1, chart_col2 = st.columns([3, 2], gap="medium")

with chart_col1:
    with st.container(border=True):
        st.subheader("Loan volume by purpose", icon=":material/bar_chart:")
        purpose_df = (
            filtered.groupby("Purpose", as_index=False)["Loan Amount"]
            .sum()
            .sort_values("Loan Amount", ascending=False)
        )
        if not purpose_df.empty:
            st.echarts_chart(
                {
                    "tooltip": {"trigger": "axis", "valueFormatter": "dollar"},
                    "grid": {"left": 56, "right": 20, "top": 20, "bottom": 36},
                    "dataset": {"source": purpose_df},
                    "xAxis": {"type": "category"},
                    "yAxis": {"type": "value"},
                    "series": [
                        {
                            "type": "bar",
                            "barMaxWidth": 44,
                            "itemStyle": {"borderRadius": [6, 6, 0, 0]},
                        }
                    ],
                },
                height=300,
                alt="Total loan amount grouped by loan purpose",
            )
        else:
            st.caption("No applications in the selected reporting window.")

with chart_col2:
    with st.container(border=True):
        st.subheader("Risk tier distribution", icon=":material/donut_large:")
        risk_counts = (
            filtered["Risk Tier"]
            .value_counts()
            .reindex(["Low Risk", "Medium Risk", "High Risk"], fill_value=0)
            .reset_index()
        )
        risk_counts.columns = ["Risk Tier", "Count"]
        st.echarts_chart(
            {
                "tooltip": {"trigger": "item"},
                "legend": {"bottom": 0},
                "dataset": {"source": risk_counts},
                "series": [
                    {
                        "type": "pie",
                        "radius": ["48%", "74%"],
                        "center": ["50%", "44%"],
                        "label": {"show": False},
                        "encode": {"itemName": "Risk Tier", "value": "Count"},
                    }
                ],
            },
            height=300,
            alt="Count of applications by illustrative risk tier",
        )

# Recent applications + Priority alerts
bottom_left, bottom_right = st.columns([3, 2], gap="medium")

with bottom_left:
    with st.container(border=True):
        st.subheader("Recent loan applications", icon=":material/receipt_long:")
        recent = filtered.sort_values("Date", ascending=False).head(8)
        st.dataframe(
            recent[
                [
                    "Application ID",
                    "Applicant",
                    "Purpose",
                    "Loan Amount",
                    "Projected DTI (%)",
                    "Risk Tier",
                    "Status",
                ]
            ],
            hide_index=True,
            column_config={
                "Loan Amount": st.column_config.NumberColumn("Loan amount", format="$%,.0f"),
                "Projected DTI (%)": st.column_config.ProgressColumn(
                    "Projected DTI",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
            },
            alt="Recent loan applications summary table",
        )

with bottom_right:
    with st.container(border=True):
        st.subheader("Priority action queue", icon=":material/notifications_active:")
        if overdue_accounts.empty and review_queue.empty:
            st.success("No urgent alerts in the selected window.", icon=":material/check_circle:")
        else:
            for _, row in overdue_accounts.head(3).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1], vertical_alignment="center")
                    with c1:
                        st.markdown(f"**{row['Loan Account']} · {row['Applicant']}**")
                        st.caption(f"{row['DPD']} days past due · ${row['Overdue Amount']:,.0f} overdue")
                    with c2:
                        st.badge(row["Aging Bucket"], color="red")

            for _, row in review_queue.head(3).iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1], vertical_alignment="center")
                    with c1:
                        st.markdown(f"**{row['Application ID']} · {row['Applicant']}**")
                        st.caption(f"${row['Loan Amount']:,.0f} · {row['Purpose']} · {row['Status']}")
                    with c2:
                        color = "red" if row["Risk Tier"] == "High Risk" else "orange" if row["Risk Tier"] == "Medium Risk" else "green"
                        st.badge(row["Risk Tier"], color=color)
