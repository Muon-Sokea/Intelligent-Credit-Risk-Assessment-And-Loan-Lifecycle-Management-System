"""FinGuard AI — Credit assessment & financial inclusion workspace."""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from utils.calculations import illustrative_risk_assessment
from utils.ml_bridge import predict_default_risk
from utils.state import add_handoff, get_record_by_id, get_records, refresh_record_metrics

st.caption(
    "Evaluate borrower risk indicators, thin-file financial inclusion evidence, and record analyst recommendations. "
    "Illustrative risk indicators are decision-support aids—never automated lending decisions."
)

records = get_records()
if not records:
    st.info("No applications available for assessment.", icon=":material/info:")
    st.stop()

# Queue selector bar
sel_col1, sel_col2 = st.columns([3, 2], vertical_alignment="bottom")
queue_mode = sel_col2.segmented_control(
    "Queue filter",
    options=["Assessment queue", "All applications"],
    default="Assessment queue",
    key="assess_queue_mode",
)

if queue_mode == "Assessment queue":
    eligible = [r for r in records if r["status"] in {"Pending", "Under Review", "Under Assessment"}]
    if not eligible:
        eligible = records
else:
    eligible = records

app_ids = [r["application_id"] for r in eligible]
default_idx = app_ids.index(st.session_state.selected_app_id) if st.session_state.selected_app_id in app_ids else 0

selected_id = sel_col1.selectbox(
    "Select borrower application",
    options=app_ids,
    index=default_idx,
    format_func=lambda aid: next(
        f"{r['application_id']} · {r['applicant_name']} (${r['loan_amount']:,.0f} · {r['status']})"
        for r in eligible
        if r["application_id"] == aid
    ),
    key="assess_selected_app",
)
st.session_state.selected_app_id = selected_id
record = get_record_by_id(selected_id)
if record is None:
    st.stop()

assessment = illustrative_risk_assessment(record)
ml_pred = predict_default_risk(record)
display_pd = ml_pred["pd_pct"] if ml_pred else assessment["pd_pct"]
display_tier = ml_pred["tier"] if ml_pred else assessment["tier"]

# Top summary banner
with st.grid(4, gap="medium"):
    st.metric(
        "ML default probability" if ml_pred else "Indicative default risk",
        f"{display_pd:.1f}%",
        display_tier,
        delta_color="inverse" if display_tier == "High Risk" else "normal" if display_tier == "Low Risk" else "off",
        border=True,
        height="stretch",
    )
    st.metric(
        "Projected DTI",
        f"{assessment['projected_dti']:.1f}%",
        "All debt + new loan",
        delta_color="off",
        border=True,
        height="stretch",
    )
    st.metric(
        "Est. monthly surplus",
        f"${assessment['net_surplus']:,.0f}",
        f"{assessment['expense_ratio']:.0f}% expense ratio",
        delta_color="normal" if assessment["net_surplus"] >= 0 else "inverse",
        border=True,
        height="stretch",
    )
    docs = record.get("docs_verified", {})
    docs_done = sum(1 for v in docs.values() if v)
    st.metric(
        "Document readiness",
        f"{docs_done} / {len(docs)}",
        "Verified documents",
        delta_color="off",
        border=True,
        height="stretch",
    )

left_col, right_col = st.columns([3, 2], gap="medium")

with left_col:
    # Risk gauge + transparent risk factors
    with st.container(border=True):
        st.subheader("Default risk decision-support summary", icon=":material/speed:")
        if ml_pred:
            auc_txt = f" · Test ROC-AUC: {ml_pred['test_roc_auc']:.3f}" if ml_pred.get("test_roc_auc") else ""
            st.badge(
                f"Live ML model: {ml_pred['model_name']}{auc_txt}",
                icon=":material/model_training:",
                color="green",
            )
            st.caption(
                f"Trained on credit_risk_dataset.csv. Rule-based capacity check: {assessment['pd_pct']:.1f}% ({assessment['tier']}). "
                "Predictions support human review only."
            )
        else:
            st.caption(
                "Currently uses transparent rule-based indicators. Run `python -m ml.train` to connect the trained ML model."
            )
        st.echarts_chart(
            {
                "series": [
                    {
                        "type": "gauge",
                        "startAngle": 200,
                        "endAngle": -20,
                        "min": 0,
                        "max": 100,
                        "progress": {"show": True, "width": 14},
                        "axisLine": {"lineStyle": {"width": 14}},
                        "axisTick": {"show": False},
                        "splitLine": {"length": 8},
                        "axisLabel": {"distance": 18, "fontSize": 11},
                        "pointer": {"show": True, "length": "58%"},
                        "title": {"offsetCenter": [0, "30%"], "fontSize": 12},
                        "detail": {
                            "valueAnimation": True,
                            "offsetCenter": [0, "62%"],
                            "fontSize": 22,
                            "formatter": "{value}%",
                        },
                        "data": [{"value": display_pd, "name": display_tier}],
                    }
                ]
            },
            height=250,
            alt=f"Default risk gauge showing {display_pd} percent ({display_tier})",
        )

        st.markdown("**Key risk & capacity factors**")
        for title, detail, severity in assessment["factors"]:
            color = "red" if severity == "high" else "orange" if severity == "medium" else "green"
            f_left, f_right = st.columns([4, 1], vertical_alignment="center")
            f_left.markdown(f"**{title}** — {detail}")
            f_right.badge(severity.capitalize(), color=color)

    # Credit Access & Financial Inclusion card
    with st.container(border=True):
        st.subheader("Credit access & financial inclusion", icon=":material/diversity_3:")
        st.caption(
            "Applicants with thin traditional credit files are evaluated using verified alternative evidence "
            "and are never treated as automatically high risk."
        )
        inc1, inc2 = st.columns(2)
        new_thin = inc1.toggle(
            "Thin traditional credit file",
            value=bool(record.get("thin_file", False)),
            key=f"thin_{record['application_id']}",
        )
        new_alt = inc2.toggle(
            "Alternative data verified (utility, rent, mobile money)",
            value=bool(record.get("alt_data_verified", False)),
            key=f"alt_{record['application_id']}",
        )
        if new_thin != record.get("thin_file") or new_alt != record.get("alt_data_verified"):
            record["thin_file"] = new_thin
            record["alt_data_verified"] = new_alt
            refresh_record_metrics(record)
            st.rerun()

        if record.get("thin_file"):
            if record.get("alt_data_verified"):
                st.success(
                    "Alternative cash-flow and utility payment evidence verified. Eligible for fair human review.",
                    icon=":material/check_circle:",
                )
            else:
                st.warning(
                    "Limited traditional bureau history. Request 6-12 months of utility, mobile-money, or bank-deposit statements before deciding.",
                    icon=":material/info:",
                )
        else:
            st.caption("Standard credit bureau file available for this applicant.")

with right_col:
    # Analyst review & recommendation form (Recommender only — final approval is Loan manager's role)
    with st.container(border=True):
        st.subheader("Analyst review & recommendation", icon=":material/edit_note:")
        st.caption(
            "Credit analysts submit a recommendation only. Final Approve / Reject decisions are made by the Loan manager."
        )
        locked_decision = record["status"] in {"Approved", "Disbursed", "Fully Repaid", "Rejected"}
        with st.form(f"analyst_review_form_{record['application_id']}", clear_on_submit=True):
            rec_options = [
                "Pending analyst review",
                "Recommend Approve",
                "Recommend Approve with conditions",
                "Request additional documentation",
                "Recommend Decline",
            ]
            current_rec = record.get("recommendation", "Pending analyst review")
            if current_rec not in rec_options:
                rec_options.append(current_rec)

            recommendation = st.selectbox(
                "Analyst recommendation",
                options=rec_options,
                index=rec_options.index(current_rec),
                disabled=locked_decision,
            )
            notes = st.text_area(
                "Assessment justification & findings",
                value="",
                height=140,
                placeholder="Write your findings or missing document request (clears after submit and saves to the log below)...",
                disabled=locked_decision,
            )
            save_review = st.form_submit_button(
                "Submit recommendation",
                type="primary",
                width="stretch",
                disabled=locked_decision,
            )

        if locked_decision:
            st.caption(f"Final decision already recorded ({record['status']}).")

        if save_review and not locked_decision:
            clean_note = notes.strip()
            record["recommendation"] = recommendation
            if clean_note:
                record["analyst_notes"] = clean_note
            if recommendation in {"Recommend Approve", "Recommend Approve with conditions", "Recommend Decline"}:
                record["status"] = "Pending Approval"
                add_handoff(
                    from_role="Credit analyst",
                    to_role="Loan manager",
                    application_id=record["application_id"],
                    subject=f"Pending approval — {recommendation}",
                    message=(
                        f"{record['applicant_name']} (${record['loan_amount']:,.0f}, {record['risk_tier']}): "
                        f"{recommendation}. {clean_note or 'Ready for Loan manager final decision.'}"
                    ),
                    target_page="app_pages/loan_management.py",
                    target_slug="loan-management",
                )
            elif recommendation == "Request additional documentation":
                record["status"] = "Under Review"
                add_handoff(
                    from_role="Credit analyst",
                    to_role="Loan officer",
                    application_id=record["application_id"],
                    subject="Additional documentation requested",
                    message=(
                        f"{record['applicant_name']}: {clean_note or 'Please collect missing borrower documents.'}"
                    ),
                    target_page="app_pages/loan_applications.py",
                    target_slug="loan-applications",
                )
            record["activity_log"].append(
                {
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "actor": st.session_state.get("staff_role", "Credit analyst"),
                    "event": f"Analyst submitted: {recommendation} (Status: {record['status']})",
                    "note": clean_note,
                }
            )
            st.toast(f"Recommendation submitted ({record['status']}).", icon=":material/send:")
            st.rerun()

    # Activity timeline (preserves full submitted notes)
    with st.container(border=True):
        st.subheader("Assessment activity log", icon=":material/history:")
        if record.get("analyst_notes") and not any(e.get("note") for e in record.get("activity_log", [])):
            st.caption(f"Latest saved note: {record['analyst_notes']}")
        for entry in reversed(record.get("activity_log", [])[-8:]):
            with st.container(border=True):
                st.markdown(f"**{entry['event']}**")
                st.caption(f"{entry['timestamp']} · {entry['actor']}")
                if entry.get("note"):
                    st.write(entry["note"])
