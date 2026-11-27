"""FinGuard AI — Loan manager approval queue & loan repayment servicing."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from utils.calculations import build_amortization_schedule, calculate_dpd_and_bucket
from utils.state import add_handoff, get_record_by_id, get_records, records_to_dataframe

active_role = st.session_state.get("staff_role", "All roles (full preview)")
can_manage = active_role in {"All roles (full preview)", "Loan manager"}

st.caption(
    "Approve or reject recommended loan applications, disburse approved loans, inspect amortization schedules, "
    "and record borrower repayments."
    if can_manage
    else "Read-only customer service view of loan terms, balances, and repayment schedules."
)

df = records_to_dataframe()
pending_approval_df = df[df["Status"] == "Pending Approval"]
serviced_df = df[df["Status"].isin(["Approved", "Disbursed", "Fully Repaid"])]

active_df = serviced_df[serviced_df["Status"] == "Disbursed"]
awaiting_disb = serviced_df[serviced_df["Status"] == "Approved"]
repaid_df = serviced_df[serviced_df["Status"] == "Fully Repaid"]

with st.grid(4, gap="medium"):
    st.metric("Pending approval", len(pending_approval_df), "Awaiting manager decision", delta_color="off", border=True, height="stretch")
    st.metric("Awaiting disbursement", len(awaiting_disb), "Approved loans", delta_color="off", border=True, height="stretch")
    st.metric("Active loan accounts", len(active_df), f"${active_df['Outstanding'].sum():,.0f} outstanding", delta_color="off", border=True, height="stretch")
    st.metric("Fully repaid", len(repaid_df), border=True, height="stretch")

# --- Approval Queue (Loan manager / All roles) -------------------------------
if can_manage:
    with st.container(border=True):
        st.subheader(
            f"Manager approval queue ({len(pending_approval_df)})",
            icon=":material/gavel:",
        )
        if pending_approval_df.empty:
            st.caption(
                "No applications are waiting for final approval. "
                "When a Credit analyst submits a recommendation, it appears here for your Approve / Reject decision."
            )
        else:
            for _, row in pending_approval_df.iterrows():
                rec = get_record_by_id(row["Application ID"])
                if not rec:
                    continue
                with st.container(border=True):
                    h_left, h_right = st.columns([4, 2], vertical_alignment="center")
                    with h_left:
                        st.markdown(
                            f"**{rec['application_id']} · {rec['applicant_name']}** "
                            f"(${rec['loan_amount']:,.0f} · {rec['loan_purpose']} · {rec['loan_term_months']} mo)"
                        )
                        st.caption(
                            f"Analyst recommendation: **{rec.get('recommendation', '—')}** · "
                            f"Projected DTI: {rec['projected_dti']:.1f}% · Indicative PD: {rec['risk_pd_pct']:.1f}%"
                        )
                        if rec.get("analyst_notes"):
                            st.write(rec["analyst_notes"])
                    with h_right:
                        risk_color = "red" if rec["risk_tier"] == "High Risk" else "orange" if rec["risk_tier"] == "Medium Risk" else "green"
                        with st.container(horizontal=True, horizontal_alignment="right"):
                            st.badge(rec["risk_tier"], color=risk_color)
                            st.badge("Pending Approval", color="blue")

                    dec_note = st.text_input(
                        "Manager decision note (optional)",
                        placeholder="e.g. Approved subject to collateral registration...",
                        key=f"mgr_note_{rec['application_id']}",
                    )
                    b_approve, b_reject = st.columns(2)
                    if b_approve.button(
                        "Approve loan",
                        type="primary",
                        icon=":material/check_circle:",
                        key=f"mgr_approve_{rec['application_id']}",
                        width="stretch",
                    ):
                        rec["status"] = "Approved"
                        rec["activity_log"].append(
                            {
                                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                                "actor": active_role,
                                "event": f"Final decision: Approved. {dec_note.strip()}".strip(),
                            }
                        )
                        add_handoff(
                            from_role="Loan manager",
                            to_role="Loan officer",
                            application_id=rec["application_id"],
                            subject="Loan approved by Loan manager",
                            message=(
                                f"{rec['applicant_name']} (${rec['loan_amount']:,.0f}) has been approved. "
                                f"{dec_note.strip() or 'Proceed with customer notification.'}"
                            ),
                            target_page="app_pages/loan_applications.py",
                            target_slug="loan-applications",
                        )
                        st.session_state.selected_app_id = rec["application_id"]
                        st.toast(f"Approved {rec['application_id']} — ready for disbursement.", icon=":material/check_circle:")
                        st.rerun()

                    if b_reject.button(
                        "Reject loan",
                        icon=":material/cancel:",
                        key=f"mgr_reject_{rec['application_id']}",
                        width="stretch",
                    ):
                        rec["status"] = "Rejected"
                        rec["activity_log"].append(
                            {
                                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                                "actor": active_role,
                                "event": f"Final decision: Rejected. {dec_note.strip()}".strip(),
                            }
                        )
                        add_handoff(
                            from_role="Loan manager",
                            to_role="Loan officer",
                            application_id=rec["application_id"],
                            subject="Loan rejected by Loan manager",
                            message=(
                                f"{rec['applicant_name']} (${rec['loan_amount']:,.0f}) was rejected. "
                                f"{dec_note.strip() or 'See analyst findings for details.'}"
                            ),
                            target_page="app_pages/loan_applications.py",
                            target_slug="loan-applications",
                        )
                        st.toast(f"Rejected {rec['application_id']}.", icon=":material/cancel:")
                        st.rerun()

if serviced_df.empty:
    st.info("No approved or disbursed loans yet. Approve a recommended application above first.", icon=":material/info:")
    st.stop()

with st.container(border=True):
    st.subheader("Loan accounts register", icon=":material/account_balance:")
    st.dataframe(
        serviced_df[
            [
                "Loan Account",
                "Application ID",
                "Applicant",
                "Purpose",
                "Loan Amount",
                "Outstanding",
                "Rate (%)",
                "Term (mo)",
                "DPD",
                "Status",
            ]
        ],
        hide_index=True,
        column_config={
            "Loan Amount": st.column_config.NumberColumn("Approved amount", format="$%,.0f"),
            "Outstanding": st.column_config.NumberColumn("Outstanding", format="$%,.0f"),
        },
        alt="Approved, disbursed, and repaid loan accounts",
    )

eligible_ids = serviced_df["Application ID"].tolist()
default_idx = eligible_ids.index(st.session_state.selected_app_id) if st.session_state.selected_app_id in eligible_ids else 0

selected_id = st.selectbox(
    "Select loan account to inspect or manage",
    options=eligible_ids,
    index=default_idx,
    format_func=lambda aid: next(
        f"{r.get('loan_account_id') or 'Pending ID'} · {r['applicant_name']} ({r['status']} · ${r['loan_amount']:,.0f})"
        for r in get_records()
        if r["application_id"] == aid
    ),
    key="mgmt_selected_loan",
)
st.session_state.selected_app_id = selected_id
record = get_record_by_id(selected_id)
if record is None:
    st.stop()

tab_terms, tab_schedule, tab_payments = st.tabs(
    [
        ":material/assignment_turned_in: Terms & disbursement",
        ":material/calendar_month: Repayment schedule",
        ":material/payments: Payments",
    ],
    on_change="rerun",
)

with tab_terms:
    if tab_terms.open:
        with st.container(border=True):
            if record["status"] == "Approved":
                if not can_manage:
                    st.info("This loan is approved and awaiting disbursement by a Loan manager.", icon=":material/info:")
                else:
                    st.subheader("Record loan disbursement")
                    st.caption(
                        "Generate the loan account ID and initial fixed-rate amortization schedule once disbursement is authorized."
                    )
                    with st.form(f"disburse_form_{record['application_id']}"):
                        c1, c2, c3 = st.columns(3)
                        disb_date = c1.date_input("Disbursement date", value=date.today())
                        disb_rate = c2.number_input("Approved rate (%)", min_value=0.0, max_value=36.0, value=float(record["interest_rate"]), step=0.25)
                        disb_term = c3.number_input("Approved term (months)", min_value=6, max_value=240, value=int(record["loan_term_months"]), step=6)
                        confirm_disb = st.form_submit_button("Disburse & generate schedule", type="primary")

                    if confirm_disb:
                        existing_count = sum(1 for r in get_records() if r.get("loan_account_id"))
                        record["loan_account_id"] = f"LN-2026-{existing_count + 1:04d}"
                        record["disbursed_date"] = disb_date
                        record["interest_rate"] = float(disb_rate)
                        record["loan_term_months"] = int(disb_term)
                        record["status"] = "Disbursed"
                        record["repayment_schedule"] = build_amortization_schedule(
                            principal=float(record["loan_amount"]),
                            annual_rate_pct=float(disb_rate),
                            months=int(disb_term),
                            first_due_date=disb_date + timedelta(days=30),
                        )
                        record["activity_log"].append(
                            {
                                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                                "actor": active_role,
                                "event": f"Disbursed as {record['loan_account_id']}",
                            }
                        )
                        add_handoff(
                            from_role="Loan manager",
                            to_role="Risk management officer",
                            application_id=record["application_id"],
                            subject=f"Loan {record['loan_account_id']} disbursed — active monitoring",
                            message=(
                                f"{record['applicant_name']} (${record['loan_amount']:,.0f}, {record['loan_term_months']} mo) "
                                "is now active and added to portfolio monitoring."
                            ),
                            target_page="app_pages/risk_monitoring.py",
                            target_slug="risk-monitoring",
                        )
                        st.toast(f"Loan {record['loan_account_id']} disbursed & Risk officer notified.", icon=":material/check_circle:")
                        st.rerun()
            else:
                st.subheader(f"Account {record['loan_account_id']} — {record['applicant_name']}")
                dpd, bucket, overdue_amt = calculate_dpd_and_bucket(record.get("repayment_schedule") or [])
                t1, t2, t3, t4 = st.columns(4)
                t1.metric("Disbursed amount", f"${record['loan_amount']:,.0f}")
                t2.metric("Disbursed date", str(record.get("disbursed_date") or "—"))
                t3.metric("Interest / Term", f"{record['interest_rate']:.1f}% · {record['loan_term_months']} mo")
                t4.metric("Current status", bucket, f"${overdue_amt:,.0f} past due" if overdue_amt > 0 else "Up to date", delta_color="inverse" if overdue_amt > 0 else "normal")

with tab_schedule:
    if tab_schedule.open:
        schedule = record.get("repayment_schedule") or []
        if not schedule:
            st.info("Disburse the loan first to generate its amortization schedule.", icon=":material/info:")
        else:
            sched_df = pd.DataFrame(schedule)
            with st.container(border=True):
                h1, h2 = st.columns([4, 1], vertical_alignment="center")
                h1.subheader(f"Amortization schedule ({len(sched_df)} installments)")
                h2.download_button(
                    "Download CSV",
                    data=sched_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"{record['loan_account_id']}_schedule.csv",
                    mime="text/csv",
                    icon=":material/download:",
                    width="stretch",
                )
                st.dataframe(
                    sched_df,
                    hide_index=True,
                    column_config={
                        "installment_no": st.column_config.NumberColumn("#", format="%d"),
                        "due_date": st.column_config.DateColumn("Due date"),
                        "opening_balance": st.column_config.NumberColumn("Opening", format="$%,.2f"),
                        "scheduled_principal": st.column_config.NumberColumn("Principal", format="$%,.2f"),
                        "scheduled_interest": st.column_config.NumberColumn("Interest", format="$%,.2f"),
                        "total_due": st.column_config.NumberColumn("Total due", format="$%,.2f"),
                        "amount_paid": st.column_config.NumberColumn("Paid", format="$%,.2f"),
                        "remaining_due": st.column_config.NumberColumn("Remaining", format="$%,.2f"),
                        "closing_balance": st.column_config.NumberColumn("Closing", format="$%,.2f"),
                        "status": st.column_config.TextColumn("Status"),
                    },
                    alt="Loan installment amortization schedule",
                )

with tab_payments:
    if tab_payments.open:
        schedule = record.get("repayment_schedule") or []
        if not schedule:
            st.info("No active repayment schedule for this account.", icon=":material/info:")
        else:
            if can_manage:
                p_left, p_right = st.columns([2, 3], gap="medium")
                with p_left:
                    with st.container(border=True):
                        st.subheader("Log borrower payment")
                        unpaid_rows = [row for row in schedule if row["remaining_due"] > 0.01]
                        suggested_amt = float(unpaid_rows[0]["remaining_due"]) if unpaid_rows else 0.0
                        with st.form(f"payment_form_{record['application_id']}"):
                            pay_date = st.date_input("Payment date", value=date.today())
                            pay_amount = st.number_input("Amount received ($)", min_value=0.0, value=suggested_amt, step=25.0)
                            pay_method = st.selectbox("Payment method", options=["Bank transfer", "Cash at branch", "Mobile banking", "Cheque"])
                            pay_notes = st.text_input("Reference / notes", placeholder="Receipt # or remarks")
                            log_pay = st.form_submit_button("Record payment", type="primary", width="stretch", disabled=not unpaid_rows)

                        if log_pay and pay_amount > 0:
                            remaining_cash = float(pay_amount)
                            for row in schedule:
                                if remaining_cash <= 0.01:
                                    break
                                if row["remaining_due"] > 0.01:
                                    applied = min(remaining_cash, float(row["remaining_due"]))
                                    row["amount_paid"] = round(float(row["amount_paid"]) + applied, 2)
                                    row["remaining_due"] = round(max(float(row["total_due"]) - float(row["amount_paid"]), 0.0), 2)
                                    row["status"] = "Paid" if row["remaining_due"] <= 0.01 else "Partial"
                                    remaining_cash = round(remaining_cash - applied, 2)

                            record["payments"].append(
                                {
                                    "payment_id": f"PAY-{len(record['payments']) + 1:03d}",
                                    "payment_date": pay_date,
                                    "amount": round(float(pay_amount), 2),
                                    "method": pay_method,
                                    "notes": pay_notes.strip() or "Recorded in session",
                                }
                            )
                            if all(r["remaining_due"] <= 0.01 for r in schedule):
                                record["status"] = "Fully Repaid"
                            st.toast(f"Recorded payment of ${pay_amount:,.2f}", icon=":material/check_circle:")
                            st.rerun()
            else:
                p_right = st.container()

            with p_right:
                with st.container(border=True):
                    st.subheader("Payment history")
                    payments = record.get("payments") or []
                    if payments:
                        pay_df = pd.DataFrame(payments)
                        st.dataframe(
                            pay_df,
                            hide_index=True,
                            column_config={
                                "payment_date": st.column_config.DateColumn("Date"),
                                "amount": st.column_config.NumberColumn("Amount", format="$%,.2f"),
                            },
                            alt="Recorded payment history for this loan account",
                        )
                    else:
                        st.caption("No payments recorded yet.")
