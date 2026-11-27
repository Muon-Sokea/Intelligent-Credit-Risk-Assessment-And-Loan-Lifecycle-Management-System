"""FinGuard AI — Risk monitoring, overdue aging & collection follow-up."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from utils.state import add_handoff, get_record_by_id, get_records, records_to_dataframe

st.caption(
    "Monitor borrower repayment warnings, days past due (DPD), portfolio at risk (PAR30), and log collection follow-ups."
)

df = records_to_dataframe()
active_df = df[df["Status"] == "Disbursed"]

total_outstanding = float(active_df["Outstanding"].sum())
overdue_df = active_df[active_df["DPD"] > 0].sort_values("DPD", ascending=False)
par30_balance = float(active_df[active_df["DPD"] >= 30]["Outstanding"].sum())
par30_pct = (par30_balance / total_outstanding * 100.0) if total_outstanding > 0 else 0.0

with st.grid(4, gap="medium"):
    st.metric("Monitored active loans", len(active_df), f"${total_outstanding:,.0f} outstanding", delta_color="off", border=True, height="stretch")
    st.metric("Overdue accounts", len(overdue_df), f"${overdue_df['Overdue Amount'].sum():,.0f} past due", delta_color="inverse" if len(overdue_df) > 0 else "off", border=True, height="stretch")
    st.metric("PAR 30+ ratio", f"{par30_pct:.1f}%", f"${par30_balance:,.0f} at risk", delta_color="inverse" if par30_pct > 5 else "off", border=True, height="stretch")
    st.metric("High-DTI active loans", int((active_df["Projected DTI (%)"] > 45).sum()), "Early-warning watch", delta_color="off", border=True, height="stretch")

chart_col, list_col = st.columns([2, 3], gap="medium")

with chart_col:
    with st.container(border=True):
        st.subheader("Portfolio aging buckets", icon=":material/bar_chart:")
        buckets = ["Current", "1-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"]
        aging_df = (
            active_df.groupby("Aging Bucket", as_index=False)["Outstanding"]
            .sum()
            .set_index("Aging Bucket")
            .reindex(buckets, fill_value=0.0)
            .reset_index()
        )
        st.echarts_chart(
            {
                "tooltip": {"trigger": "axis", "valueFormatter": "dollar"},
                "grid": {"left": 56, "right": 16, "top": 20, "bottom": 36},
                "dataset": {"source": aging_df},
                "xAxis": {"type": "category"},
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "type": "bar",
                        "barMaxWidth": 38,
                        "itemStyle": {"borderRadius": [6, 6, 0, 0]},
                    }
                ],
            },
            height=290,
            alt="Outstanding loan balance grouped by days-past-due aging bucket",
        )

with list_col:
    with st.container(border=True):
        st.subheader("Overdue & early-warning watch list", icon=":material/warning:")
        watch_df = active_df[(active_df["DPD"] > 0) | (active_df["Projected DTI (%)"] > 45)].sort_values(
            ["DPD", "Projected DTI (%)"], ascending=False
        )
        if watch_df.empty:
            st.success("All active loans are current with no early-warning flags.", icon=":material/check_circle:")
        else:
            st.dataframe(
                watch_df[
                    [
                        "Loan Account",
                        "Applicant",
                        "Outstanding",
                        "DPD",
                        "Aging Bucket",
                        "Overdue Amount",
                        "Projected DTI (%)",
                    ]
                ],
                hide_index=True,
                column_config={
                    "Outstanding": st.column_config.NumberColumn("Outstanding", format="$%,.0f"),
                    "Overdue Amount": st.column_config.NumberColumn("Overdue", format="$%,.0f"),
                    "Projected DTI (%)": st.column_config.NumberColumn("DTI", format="%.1f%%"),
                },
                alt="Overdue and early-warning monitored loan accounts",
            )

# Collection follow-up logger
if not active_df.empty:
    with st.container(border=True):
        st.subheader("Collection & borrower follow-up", icon=":material/support_agent:")
        active_ids = active_df["Application ID"].tolist()
        sel_id = st.selectbox(
            "Select monitored account",
            options=active_ids,
            format_func=lambda aid: next(
                f"{r['loan_account_id']} · {r['applicant_name']}"
                for r in get_records()
                if r["application_id"] == aid
            ),
            key="monitor_selected_app",
        )
        rec = get_record_by_id(sel_id)
        if rec:
            c_left, c_right = st.columns([2, 3], gap="medium")
            with c_left:
                with st.form(f"collection_log_form_{sel_id}"):
                    channel = st.selectbox("Contact channel", options=["Phone call", "Branch visit", "SMS reminder", "Field visit"])
                    outcome = st.text_area("Contact outcome & borrower notes", placeholder="Summarize borrower response or restructuring request...")
                    promise_date = st.date_input("Promise-to-pay date", value=date.today() + timedelta(days=7))
                    add_log = st.form_submit_button("Log follow-up", type="primary", width="stretch")

                if add_log and outcome.strip():
                    rec["collection_logs"].insert(
                        0,
                        {
                            "date": date.today().isoformat(),
                            "officer": st.session_state.get("staff_role", "Risk officer"),
                            "channel": channel,
                            "outcome": outcome.strip(),
                            "promise_date": promise_date.isoformat(),
                        },
                    )
                    sender_role = st.session_state.get("staff_role", "Risk management officer")
                    target_role = "Loan manager" if sender_role != "Loan manager" else "Risk management officer"
                    add_handoff(
                        from_role=sender_role if sender_role != "All roles (full preview)" else "Risk management officer",
                        to_role=target_role,
                        application_id=rec["application_id"],
                        subject=f"Collection follow-up logged ({rec['loan_account_id']})",
                        message=f"{channel}: {outcome.strip()} (Promise date: {promise_date.isoformat()})",
                        target_page="app_pages/risk_monitoring.py",
                        target_slug="risk-monitoring",
                    )
                    st.toast(f"Collection follow-up logged & {target_role} notified.", icon=":material/check_circle:")
                    st.rerun()

            with c_right:
                logs = rec.get("collection_logs") or []
                if logs:
                    st.dataframe(
                        pd.DataFrame(logs),
                        hide_index=True,
                        alt="Collection follow-up history for selected account",
                    )
                else:
                    st.caption("No follow-up interactions logged for this account yet.")
