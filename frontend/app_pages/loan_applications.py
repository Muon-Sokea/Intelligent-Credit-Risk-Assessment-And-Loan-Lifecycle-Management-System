"""FinGuard AI — Loan applications workspace."""

from __future__ import annotations

from datetime import date, datetime, timezone

import streamlit as st

from utils.new_application import open_new_application_dialog
from utils.state import (
    APPLICATION_STATUSES,
    LOAN_PURPOSES,
    STAFF_ROLES,
    add_handoff,
    get_record_by_id,
    get_records,
    records_to_dataframe,
)

st.caption(
    "Review, filter, and create customer loan applications. "
    "Select any row to inspect borrower details or advance an application to credit assessment."
)


df = records_to_dataframe()
active_role = st.session_state.get("staff_role", "All roles (full preview)")
can_intake = active_role in {"All roles (full preview)", "Loan officer"}
allowed_pages = set(STAFF_ROLES.get(active_role, {}).get("pages", []))

# Summary metrics
pending_review = int(df["Status"].isin(["Pending", "Under Review"]).sum())
under_assessment = int((df["Status"] == "Under Assessment").sum())
approved_active = int(df["Status"].isin(["Approved", "Disbursed", "Fully Repaid"]).sum())

with st.grid(4, gap="medium"):
    st.metric("Total applications", len(df), border=True, height="stretch")
    st.metric("Pending review", pending_review, border=True, height="stretch")
    st.metric("Under assessment", under_assessment, border=True, height="stretch")
    st.metric("Approved / active", approved_active, border=True, height="stretch")

# Filter toolbar + New application action (intake roles only)
with st.container(border=True):
    if can_intake:
        f_col1, f_col2, f_col3, f_col4 = st.columns([3, 2, 2, 1.5], vertical_alignment="bottom")
    else:
        f_col1, f_col2, f_col3 = st.columns([3, 2, 2], vertical_alignment="bottom")
        f_col4 = None
    search_query = f_col1.text_input(
        "Search applicant or ID",
        placeholder="Name, application ID, or loan account...",
        icon=":material/search:",
        key="apps_search",
    )
    status_filter = f_col2.multiselect(
        "Status",
        options=list(APPLICATION_STATUSES),
        default=[],
        placeholder="All statuses",
        key="apps_status_filter",
    )
    purpose_filter = f_col3.multiselect(
        "Loan purpose",
        options=list(LOAN_PURPOSES),
        default=[],
        placeholder="All purposes",
        key="apps_purpose_filter",
    )
    if f_col4 is not None and f_col4.button(
        "New application", type="primary", icon=":material/add:", width="stretch"
    ):
        open_new_application_dialog()

filtered = df.copy()
if search_query.strip():
    q = search_query.strip().lower()
    filtered = filtered[
        filtered["Application ID"].str.lower().str.contains(q)
        | filtered["Applicant"].str.lower().str.contains(q)
        | filtered["Loan Account"].str.lower().str.contains(q)
    ]
if status_filter:
    filtered = filtered[filtered["Status"].isin(status_filter)]
if purpose_filter:
    filtered = filtered[filtered["Purpose"].isin(purpose_filter)]

# Interactive application table
table_cols = [
    "Application ID",
    "Applicant",
    "Type",
    "Purpose",
    "Date",
    "Loan Amount",
    "Term (mo)",
    "Projected DTI (%)",
    "Risk Tier",
    "Status",
]

with st.container(border=True):
    top_bar_l, top_bar_r = st.columns([4, 1], vertical_alignment="center")
    top_bar_l.subheader(f"Applications ({len(filtered)})", icon=":material/table_chart:")
    top_bar_r.download_button(
        "Export CSV",
        data=filtered[table_cols].to_csv(index=False).encode("utf-8"),
        file_name="finguard_loan_applications.csv",
        mime="text/csv",
        icon=":material/download:",
        width="stretch",
    )

    selection = st.dataframe(
        filtered[table_cols],
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Loan Amount": st.column_config.NumberColumn("Loan amount", format="$%,.0f"),
            "Projected DTI (%)": st.column_config.NumberColumn("Projected DTI", format="%.1f%%"),
        },
        alt="Filterable table of customer loan applications",
    )

selected_rows = selection.selection.rows if selection and selection.selection else []
if selected_rows and not filtered.empty:
    st.session_state.selected_app_id = filtered.iloc[selected_rows[0]]["Application ID"]

# Selected application detail panel
record = get_record_by_id(st.session_state.selected_app_id)
if record:
    with st.container(border=True):
        d_head_l, d_head_r = st.columns([4, 2], vertical_alignment="center")
        with d_head_l:
            st.subheader(
                f"{record['application_id']} — {record['applicant_name']}",
                icon=":material/person:",
            )
            st.caption(
                f"{record['borrower_type']} · {record['occupation']} · {record['province']} · {record['phone']}"
            )
        with d_head_r:
            with st.container(horizontal=True, horizontal_alignment="right"):
                risk_color = "red" if record["risk_tier"] == "High Risk" else "orange" if record["risk_tier"] == "Medium Risk" else "green"
                st.badge(record["status"], color="blue")
                st.badge(record["risk_tier"], color=risk_color)
                if record.get("thin_file"):
                    st.badge("Thin file", icon=":material/diversity_3:", color="violet")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Requested loan", f"${record['loan_amount']:,.0f}")
        m2.metric("Monthly income", f"${record['monthly_income']:,.0f}")
        m3.metric("Est. installment", f"${record['estimated_installment']:,.0f}/mo")
        m4.metric("Projected DTI", f"{record['projected_dti']:.1f}%")

        doc_col, action_col = st.columns([3, 2], gap="medium")
        with doc_col:
            st.markdown("**Document checklist**" + ("" if can_intake else " (read-only)"))
            docs = record.get("docs_verified", {})
            doc_cols = st.columns(len(docs) or 1)
            for idx, (doc_name, verified) in enumerate(docs.items()):
                new_val = doc_cols[idx].checkbox(
                    doc_name,
                    value=bool(verified),
                    disabled=not can_intake,
                    key=f"doc_{record['application_id']}_{doc_name}",
                )
                if can_intake:
                    docs[doc_name] = new_val

        with action_col:
            st.markdown("**Workflow actions**")
            with st.container(horizontal=True):
                if can_intake and record["status"] in {"Pending", "Under Review"}:
                    if st.button(
                        "Send to assessment",
                        type="primary",
                        icon=":material/send:",
                        key=f"advance_{record['application_id']}",
                    ):
                        record["status"] = "Under Assessment"
                        record["activity_log"].append(
                            {
                                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                                "actor": active_role,
                                "event": "Submitted to Credit Assessment queue",
                            }
                        )
                        add_handoff(
                            from_role="Loan officer",
                            to_role="Credit analyst",
                            application_id=record["application_id"],
                            subject="New case for credit assessment",
                            message=(
                                f"{record['applicant_name']} (${record['loan_amount']:,.0f}, {record['loan_purpose']}) "
                                "submitted by Loan Officer for risk assessment."
                            ),
                            target_page="app_pages/credit_assessment.py",
                            target_slug="credit-assessment",
                        )
                        st.toast("Sent to Credit analyst inbox", icon=":material/send:")
                        st.rerun()

                if "credit-assessment" in allowed_pages:
                    if st.button(
                        "Open credit assessment",
                        type="secondary" if can_intake else "primary",
                        icon=":material/verified_user:",
                        key=f"goto_assess_{record['application_id']}",
                    ):
                        st.switch_page("app_pages/credit_assessment.py")
                elif "debt-analysis" in allowed_pages:
                    if st.button(
                        "Open debt analysis",
                        icon=":material/account_balance_wallet:",
                        key=f"goto_debt_{record['application_id']}",
                    ):
                        st.switch_page("app_pages/debt_analysis.py")
