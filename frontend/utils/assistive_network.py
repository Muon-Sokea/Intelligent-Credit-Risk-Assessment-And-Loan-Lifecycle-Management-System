"""FinGuard AI — Floating AssistiveTouch Role Network & Live Handoff Hub."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import time

import streamlit as st

from utils.calculations import calculate_dpd_and_bucket, illustrative_risk_assessment
from utils.ml_bridge import load_model_metrics, predict_default_risk
from utils.state import (
    STAFF_ROLES,
    add_handoff,
    get_handoffs_for_role,
    get_record_by_id,
    get_records,
    mark_handoff_read,
)

_CATEGORIES = [
    {"name": "Origination (Maker)", "itemStyle": {"color": "#2563EB"}},
    {"name": "Assessment (Checker)", "itemStyle": {"color": "#7C3AED"}},
    {"name": "ML Engine", "itemStyle": {"color": "#059669"}},
    {"name": "Approval (Approver)", "itemStyle": {"color": "#D97706"}},
    {"name": "Risk Monitoring", "itemStyle": {"color": "#DC2626"}},
    {"name": "Customer Support", "itemStyle": {"color": "#0284C7"}},
]

_ROLE_POSITIONS = {
    "Loan officer": (100, 150, 0, "Maker · Intake"),
    "Credit analyst": (300, 90, 1, "Checker · Risk Review"),
    "ML Scoring Engine": (300, 230, 2, "Auto PD% Scoring"),
    "Loan manager": (500, 90, 3, "Approver · Disbursement"),
    "Risk management officer": (690, 150, 4, "DPD · Portfolio Alerts"),
    "Customer service officer": (500, 230, 5, "Borrower Support"),
}

_BASE_LINKS = [
    ("Loan officer", "Credit analyst", "Intake → Assessment", 0.14),
    ("Credit analyst", "Loan officer", "Doc Request", 0.20),
    ("Credit analyst", "ML Scoring Engine", "Live PD%", 0.18),
    ("ML Scoring Engine", "Credit analyst", "Risk Score", 0.18),
    ("Credit analyst", "Loan manager", "Recommendation", 0.14),
    ("Loan manager", "Loan officer", "Decision", 0.22),
    ("Loan manager", "Risk management officer", "Disbursed", 0.14),
    ("Risk management officer", "Loan manager", "DPD Alert", 0.20),
    ("Customer service officer", "Loan manager", "Escalation", 0.18),
    ("Loan manager", "Customer service officer", "Loan Terms", 0.18),
]

_STAGES = [
    ("1. Intake", "Loan officer"),
    ("2. Assessment + ML", "Credit analyst"),
    ("3. Final Approval", "Loan manager"),
    ("4. Disbursement", "Loan manager"),
    ("5. Monitoring", "Risk officer"),
]

_STAGE_INDEX_BY_STATUS = {
    "Pending": 0,
    "Under Review": 0,
    "Under Assessment": 1,
    "Pending Approval": 2,
    "Approved": 3,
    "Disbursed": 4,
    "Fully Repaid": 5,
    "Rejected": 2,
}

_SIM_SPEEDS = {"Slow": 2.6, "Normal": 1.6, "Fast": 0.9}

# Read-only walkthrough of one existing loan across the network (never changes records).
_SIM_STEP_COUNT = 9


def _build_steps(rec: dict) -> list[dict]:
    """Build the 9-step demonstration from the selected case's existing data."""
    name = rec["applicant_name"]
    amount = float(rec["loan_amount"])
    term = int(rec["loan_term_months"])
    ml = predict_default_risk(rec)
    assess = illustrative_risk_assessment(rec)
    pd_val = ml["pd_pct"] if ml else assess["pd_pct"]
    tier = ml["tier"] if ml else assess["tier"]
    model = ml["model_name"] if ml else "rule-based indicators"
    verdict = "Recommend Approve" if pd_val < 42 else "Recommend Decline"
    docs = rec.get("docs_verified", {})
    docs_done = sum(1 for v in docs.values() if v)
    schedule = rec.get("repayment_schedule") or []
    if schedule:
        dpd, bucket, overdue = calculate_dpd_and_bucket(schedule)
        account = rec.get("loan_account_id") or "loan account"
        monitor_txt = (
            f"{account}: {len(schedule)} installments, status {bucket}"
            + (f", {dpd} days past due (${overdue:,.0f} overdue)." if dpd else ", all payments on time.")
        )
        disb_txt = f"{account} was disbursed on {rec.get('disbursed_date')} with {len(schedule)} scheduled installments."
        terms_txt = f"{account} schedule and balances are available for {name}'s inquiries."
    else:
        monitor_txt = "No schedule yet; monitoring starts once the loan is disbursed."
        disb_txt = f"On approval a loan account and {term}-month schedule would be created (installment about ${assess['estimated_installment']:,.0f})."
        terms_txt = "Once disbursed, Customer service can read the schedule and balances."

    return [
        {
            "title": "Borrower applies",
            "nodes": ["Loan officer"],
            "edges": [],
            "stage": 0,
            "text": (
                f"{name} ({rec['borrower_type']}, {rec['occupation']}) requests ${amount:,.0f} for "
                f"{rec['loan_purpose']} over {term} months at {rec['interest_rate']:.1f}%. "
                f"Documents verified: {docs_done} of {len(docs)}."
            ),
        },
        {
            "title": "Handoff to Credit analyst",
            "nodes": ["Loan officer", "Credit analyst"],
            "edges": [("Loan officer", "Credit analyst")],
            "stage": 1,
            "text": (
                f"{rec['application_id']} enters the Credit analyst queue. Monthly income ${rec['monthly_income']:,.0f}, "
                f"expenses ${rec['monthly_expenses']:,.0f}, existing debt payments ${rec['monthly_debt_payment']:,.0f}."
            ),
        },
        {
            "title": "ML model scores default risk",
            "nodes": ["Credit analyst", "ML Scoring Engine"],
            "edges": [("Credit analyst", "ML Scoring Engine"), ("ML Scoring Engine", "Credit analyst")],
            "stage": 1,
            "text": (
                f"{model} returns a {pd_val:.1f}% default probability ({tier}). "
                f"Projected DTI {assess['projected_dti']:.1f}%, monthly surplus ${assess['net_surplus']:,.0f}."
            ),
        },
        {
            "title": "Recommendation to Loan manager",
            "nodes": ["Credit analyst", "Loan manager"],
            "edges": [("Credit analyst", "Loan manager")],
            "stage": 2,
            "text": f"Analyst submits: {verdict}. The case would become Pending Approval (recorded status: {rec['status']}).",
        },
        {
            "title": "Loan manager decides",
            "nodes": ["Loan manager"],
            "edges": [],
            "stage": 2,
            "text": (
                f"Loan manager weighs PD {pd_val:.1f}%, DTI {assess['projected_dti']:.1f}% and the "
                f"{'thin credit file' if rec.get('thin_file') else 'standard credit file'} before the final Approve / Reject."
            ),
        },
        {
            "title": "Decision notice to Loan officer",
            "nodes": ["Loan manager", "Loan officer"],
            "edges": [("Loan manager", "Loan officer")],
            "stage": 3,
            "text": f"Loan officer is told the outcome so {name} can be informed and disbursement prepared.",
        },
        {
            "title": "Disbursement to monitoring",
            "nodes": ["Loan manager", "Risk management officer"],
            "edges": [("Loan manager", "Risk management officer")],
            "stage": 3,
            "text": disb_txt,
        },
        {
            "title": "Risk monitoring begins",
            "nodes": ["Risk management officer"],
            "edges": [],
            "stage": 4,
            "text": monitor_txt,
        },
        {
            "title": "Customer service gets loan terms",
            "nodes": ["Loan manager", "Customer service officer"],
            "edges": [("Loan manager", "Customer service officer")],
            "stage": 4,
            "text": terms_txt,
        },
    ]


def _init_sim_state() -> None:
    st.session_state.setdefault("at_sim_step", -1)
    st.session_state.setdefault("at_sim_count", 0)
    st.session_state.setdefault("at_sim_running", False)
    st.session_state.setdefault("at_sim_done", False)
    st.session_state.setdefault("at_sim_current", None)
    st.session_state.setdefault("at_sim_last_tick", 0.0)
    st.session_state.setdefault("at_sim_log", [])


def _selected_case() -> dict | None:
    return get_record_by_id(st.session_state.get("at_selected_app", st.session_state.selected_app_id))


def _advance_sim() -> None:
    rec = _selected_case()
    nxt = st.session_state.at_sim_step + 1
    if rec is None or nxt >= _SIM_STEP_COUNT:
        st.session_state.at_sim_running = False
        st.session_state.at_sim_done = True
        return
    step = _build_steps(rec)[nxt]
    st.session_state.at_sim_step = nxt
    st.session_state.at_sim_count = nxt + 1
    st.session_state.at_sim_current = step
    st.session_state.at_sim_last_tick = time.time()
    st.session_state.at_sim_log.append(f"{nxt + 1}. {step['title']} - {step['text']}")
    if nxt == _SIM_STEP_COUNT - 1:
        st.session_state.at_sim_running = False
        st.session_state.at_sim_done = True
        st.session_state.at_sim_log.append("Walkthrough complete.")


def _sim_play() -> None:
    if st.session_state.at_sim_done:
        _sim_reset()
    st.session_state.at_sim_running = True
    st.session_state.at_sim_last_tick = 0.0


def _sim_pause() -> None:
    st.session_state.at_sim_running = False


def _sim_step_once() -> None:
    st.session_state.at_sim_running = False
    if st.session_state.at_sim_done:
        _sim_reset()
    _advance_sim()


def _sim_reset() -> None:
    st.session_state.at_sim_step = -1
    st.session_state.at_sim_count = 0
    st.session_state.at_sim_running = False
    st.session_state.at_sim_done = False
    st.session_state.at_sim_current = None
    st.session_state.at_sim_last_tick = 0.0
    st.session_state.at_sim_log = []


def _sim_panel(records: list[dict], handoffs: list[dict], ml_model_name: str, interval: float) -> None:
    """Animated network graph + current step. Re-runs on its own timer while playing."""
    if st.session_state.at_sim_running and time.time() - st.session_state.at_sim_last_tick >= interval * 0.85:
        _advance_sim()

    sim = st.session_state.at_sim_current

    st.echarts_chart(
        _build_network_option(records, handoffs, ml_model_name, sim),
        height=340,
        alt="Interactive live role communication network graph with department legend and simulation highlight",
    )

    if sim:
        st.progress(
            st.session_state.at_sim_count / _SIM_STEP_COUNT,
            text=f"Step {st.session_state.at_sim_count} of {_SIM_STEP_COUNT}: {sim['title']}",
        )
        st.caption(sim["text"])
        stage_cols = st.columns(len(_STAGES))
        for idx, (stage_title, owner_role) in enumerate(_STAGES):
            with stage_cols[idx]:
                with st.container(border=True):
                    st.markdown(f"**{stage_title}**")
                    st.caption(owner_role)
                    if idx < sim["stage"]:
                        st.badge("Done", icon=":material/check:", color="green")
                    elif idx == sim["stage"]:
                        st.badge("In progress", icon=":material/radio_button_checked:", color="orange")
                    else:
                        st.badge("Waiting", color="gray")
    else:
        st.caption(
            "Press Play to walk the selected case through every role. Each step shows that case's "
            "existing data (borrower, ML risk score, DTI, schedule). Nothing is changed."
        )

    log = st.session_state.at_sim_log
    if log:
        with st.container(border=True):
            st.markdown("**Walkthrough log**")
            for line in reversed(log[-6:]):
                st.caption(line)


def _build_network_option(
    records: list[dict],
    handoffs: list[dict],
    ml_model_name: str,
    sim: dict | None = None,
) -> dict:
    unread_by_role: dict[str, int] = defaultdict(int)
    edge_stats: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"total": 0, "unread": 0})
    for h in handoffs:
        src, dst = h["from_role"], h["to_role"]
        edge_stats[(src, dst)]["total"] += 1
        if not h["read"]:
            unread_by_role[dst] += 1
            edge_stats[(src, dst)]["unread"] += 1

    owned_counts = {
        "Loan officer": sum(1 for r in records if r["status"] in {"Pending", "Under Review"}),
        "Credit analyst": sum(1 for r in records if r["status"] == "Under Assessment"),
        "ML Scoring Engine": len(records),
        "Loan manager": sum(1 for r in records if r["status"] in {"Pending Approval", "Approved"}),
        "Risk management officer": sum(1 for r in records if r["status"] == "Disbursed"),
        "Customer service officer": sum(1 for r in records if r["status"] in {"Disbursed", "Fully Repaid"}),
    }

    nodes = []
    for role_name, (x, y, cat_idx, subtitle) in _ROLE_POSITIONS.items():
        u_cnt = unread_by_role.get(role_name, 0)
        o_cnt = owned_counts.get(role_name, 0)
        sub_label = f"{subtitle} ({ml_model_name})" if role_name == "ML Scoring Engine" else subtitle
        badge_txt = f" ({u_cnt})" if u_cnt else ""
        nodes.append(
            {
                "name": role_name,
                "category": cat_idx,
                "x": x,
                "y": y,
                "symbolSize": 44 if role_name == "ML Scoring Engine" else (46 + min(u_cnt * 3, 10)),
                "itemStyle": {
                    "borderColor": "#FDE68A" if u_cnt > 0 else "#FFFFFF",
                    "borderWidth": 4 if u_cnt > 0 else 2,
                    "shadowBlur": 12 if u_cnt > 0 else 4,
                    "shadowColor": "rgba(217, 169, 78, 0.55)" if u_cnt > 0 else "rgba(15, 23, 42, 0.15)",
                },
                "label": {
                    "show": True,
                    "position": "bottom",
                    "distance": 6,
                    "fontWeight": "bold",
                    "fontSize": 11,
                    "formatter": f"{role_name}{badge_txt}",
                },
                "value": f"{sub_label} | Cases: {o_cnt} | Unread: {u_cnt}",
            }
        )

    seen_pairs: set[tuple[str, str]] = set()
    links = []
    for src, dst, default_label, curveness in _BASE_LINKS:
        seen_pairs.add((src, dst))
        stats = edge_stats.get((src, dst), {"total": 0, "unread": 0})
        is_ml = "ML Scoring Engine" in (src, dst)
        active = stats["total"] > 0 or is_ml
        has_unread = stats["unread"] > 0

        if is_ml:
            edge_label, line_color, width, line_type = default_label, "#059669", 2.2, "dashed"
        elif has_unread:
            edge_label = f"{stats['total']} ({stats['unread']} new)"
            line_color, width, line_type = "#D97706", 3.2, "solid"
        elif stats["total"] > 0:
            edge_label = f"{stats['total']} msg"
            line_color, width, line_type = "#2563EB", 2.2, "solid"
        else:
            edge_label, line_color, width, line_type = default_label, "#64748B", 1.6, "dashed"

        links.append(
            {
                "source": src,
                "target": dst,
                "label": {"show": True, "formatter": edge_label, "fontSize": 9, "color": line_color},
                "lineStyle": {
                    "color": line_color,
                    "width": width,
                    "curveness": curveness,
                    "type": line_type,
                    "opacity": 0.95 if active else 0.72,
                },
            }
        )

    for (src, dst), stats in edge_stats.items():
        if (src, dst) not in seen_pairs and src in _ROLE_POSITIONS and dst in _ROLE_POSITIONS:
            links.append(
                {
                    "source": src,
                    "target": dst,
                    "label": {
                        "show": True,
                        "formatter": f"{stats['total']} ({stats['unread']} new)" if stats["unread"] else f"{stats['total']} msg",
                        "fontSize": 10,
                        "color": "#D97706" if stats["unread"] else "#2563EB",
                    },
                    "lineStyle": {
                        "color": "#D97706" if stats["unread"] else "#2563EB",
                        "width": 2.8 if stats["unread"] else 2.0,
                        "curveness": 0.24,
                    },
                }
            )

    if sim:
        active_nodes = set(sim["nodes"])
        active_edges = set(sim["edges"])
        for node in nodes:
            if node["name"] in active_nodes:
                node["symbolSize"] = node["symbolSize"] + 12
                node["itemStyle"] = {
                    "borderColor": "#F59E0B",
                    "borderWidth": 5,
                    "shadowBlur": 26,
                    "shadowColor": "rgba(245, 158, 11, 0.85)",
                }
        for link in links:
            if (link["source"], link["target"]) in active_edges:
                link["label"] = {
                    "show": True,
                    "formatter": "▶ " + sim["title"],
                    "fontSize": 10,
                    "fontWeight": "bold",
                    "color": "#EA580C",
                }
                link["lineStyle"] = {
                    "color": "#F59E0B",
                    "width": 5,
                    "curveness": link["lineStyle"].get("curveness", 0.14),
                    "type": "solid",
                    "opacity": 1,
                }

    return {
        "tooltip": {"trigger": "item"},
        "legend": {
            "top": 0,
            "left": "center",
            "itemWidth": 12,
            "itemHeight": 12,
            "textStyle": {"fontSize": 11},
            "data": [c["name"] for c in _CATEGORIES],
        },
        "animationDurationUpdate": 500,
        "series": [
            {
                "type": "graph",
                "layout": "none",
                "left": "10%",
                "right": "10%",
                "top": "18%",
                "bottom": "16%",
                "roam": False,
                "categories": _CATEGORIES,
                "edgeSymbol": ["circle", "arrow"],
                "edgeSymbolSize": [4, 10],
                "data": nodes,
                "links": links,
                "emphasis": {"focus": "adjacency", "lineStyle": {"width": 4}},
            }
        ],
    }


@st.dialog("Role Network — Live Assistive Hub", width="large")
def open_role_network_dialog() -> None:
    """Floating AssistiveTouch overlay showing live role network, tracker, and messaging."""
    records = get_records()
    handoffs = st.session_state.get("handoff_messages", [])
    active_role = st.session_state.get("staff_role", "All roles (full preview)")
    metrics = load_model_metrics() or {}
    ml_model_name = metrics.get("best_model", "Rule-Based")
    ml_auc = metrics.get("test_metrics", {}).get("roc_auc")

    unread_all = sum(1 for h in handoffs if not h["read"])
    st.caption(
        f"Active role: **{active_role}** · Background ML: **{ml_model_name}**"
        + (f" (ROC-AUC {ml_auc:.3f})" if ml_auc else "")
        + f" · **{unread_all}** unread handoffs across roles"
    )

    tab_net, tab_feed, tab_send = st.tabs(
        [
            ":material/hub: Live network & tracker",
            f":material/forum: Communication feed ({len(handoffs)})",
            ":material/send: Broadcast message",
        ]
    )

    with tab_net:
        _init_sim_state()
        running = st.session_state.at_sim_running

        app_ids = [r["application_id"] for r in records]
        default_idx = app_ids.index(st.session_state.selected_app_id) if st.session_state.selected_app_id in app_ids else 0
        sel_id = st.selectbox(
            "Case to demonstrate",
            options=app_ids,
            index=default_idx,
            format_func=lambda aid: next(
                f"{r['application_id']} - {r['applicant_name']} (${r['loan_amount']:,.0f} - {r['status']})"
                for r in records
                if r["application_id"] == aid
            ),
            key="at_selected_app",
            on_change=_sim_reset,
        )
        st.session_state.selected_app_id = sel_id
        st.caption("The walkthrough uses this case's existing data and never changes it.")

        speed_label = st.session_state.get("at_sim_speed", "Normal")
        interval = _SIM_SPEEDS.get(speed_label, 1.6)
        ctl_play, ctl_step, ctl_reset, ctl_speed = st.columns([2, 1.4, 1.4, 2.4], vertical_alignment="bottom")
        if running:
            ctl_play.button(
                "Pause",
                icon=":material/pause:",
                type="primary",
                width="stretch",
                on_click=_sim_pause,
                key="at_sim_pause_btn",
            )
        else:
            ctl_play.button(
                "Play simulation",
                icon=":material/play_arrow:",
                type="primary",
                width="stretch",
                on_click=_sim_play,
                key="at_sim_play_btn",
            )
        ctl_step.button("Step", icon=":material/skip_next:", width="stretch", on_click=_sim_step_once, key="at_sim_step_btn")
        ctl_reset.button("Reset", icon=":material/restart_alt:", width="stretch", on_click=_sim_reset, key="at_sim_reset_btn")
        ctl_speed.select_slider("Speed", options=list(_SIM_SPEEDS), value="Normal", key="at_sim_speed")

        # Timer-driven fragment: only the graph and step text refresh while playing.
        panel = st.fragment(run_every=interval if running else None)(_sim_panel)
        panel(records, handoffs, ml_model_name, interval)
        st.caption(
            "Orange glow = sample case location · Gold arrows = unread handoffs · Blue = read · "
            "Green dashed = live ML scoring service."
        )


    with tab_feed:
        role_filter = st.selectbox(
            "Filter by role",
            options=["All roles"] + [r for r in STAFF_ROLES if r != "All roles (full preview)"],
            key="at_feed_filter",
        )
        shown = [
            h
            for h in handoffs
            if role_filter == "All roles" or h["from_role"] == role_filter or h["to_role"] == role_filter
        ]
        if not shown:
            st.caption("No handoff messages yet.")
        else:
            for msg in shown[:8]:
                with st.container(border=True):
                    top_l, top_r = st.columns([4, 1], vertical_alignment="center")
                    top_l.markdown(f"**{msg['from_role']} → {msg['to_role']}** · `{msg['application_id']}`")
                    top_r.badge("New" if not msg["read"] else "Read", color="orange" if not msg["read"] else "gray")
                    st.markdown(f"**{msg['subject']}** — {msg['message']}")
                    b_l, b_r = st.columns([3, 1], vertical_alignment="center")
                    b_l.caption(msg["timestamp"])
                    if not msg["read"] and b_r.button("Mark read", key=f"at_read_{msg['id']}", width="stretch"):
                        mark_handoff_read(msg["id"])
                        st.rerun()

    with tab_send:
        role_list = [r for r in STAFF_ROLES if r != "All roles (full preview)"]
        with st.form("at_compose_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            from_r = c1.selectbox("From role", options=role_list, index=0)
            to_r = c2.selectbox("To role", options=role_list, index=1)
            case_id = st.selectbox("Related case", options=[r["application_id"] for r in records])
            subj = st.text_input("Subject", placeholder="e.g. Urgent income verification needed")
            body = st.text_area("Message", placeholder="Write message to light up the role network...", height=85)
            sent = st.form_submit_button("Broadcast handoff", type="primary", width="stretch")

        if sent:
            if from_r == to_r:
                st.error("Choose two different roles.")
            elif not subj.strip() or not body.strip():
                st.error("Enter both a subject and a message.")
            else:
                add_handoff(from_r, to_r, case_id, subj.strip(), body.strip())
                st.toast(f"Sent {from_r} → {to_r}", icon=":material/send:")
                st.rerun()


def render_assistive_touch(active_role: str) -> None:
    """Render a floating AssistiveTouch orb pinned to bottom-right across all pages."""
    incoming = get_handoffs_for_role(active_role)
    unread = sum(1 for m in incoming if not m["read"])

    st.html(
        """
        <style>
        .st-key-assistive-touch-fab {
            position: fixed !important;
            bottom: 24px !important;
            right: 24px !important;
            z-index: 9999 !important;
            width: auto !important;
        }
        .st-key-assistive-touch-fab button {
            border-radius: 999px !important;
            min-height: 52px !important;
            padding: 0 18px !important;
            background: linear-gradient(135deg, #0F2342 0%, #1B3A6B 100%) !important;
            color: #FDE68A !important;
            border: 2px solid rgba(229, 185, 92, 0.85) !important;
            box-shadow: 0 8px 24px rgba(15, 35, 66, 0.42) !important;
            font-weight: 700 !important;
            transition: transform 150ms ease, box-shadow 150ms ease !important;
        }
        .st-key-assistive-touch-fab button:hover {
            transform: scale(1.06) !important;
            box-shadow: 0 12px 28px rgba(15, 35, 66, 0.55) !important;
            border-color: #FDE68A !important;
        }
        </style>
        """
    )

    with st.container(key="assistive-touch-fab"):
        label = f"Role Hub · {unread}" if unread else "Role Hub"
        if st.button(
            label,
            icon=":material/hub:",
            help="AssistiveTouch — Open Live Role Network & Handoffs",
            type="primary",
            key="assistive_touch_btn",
        ):
            open_role_network_dialog()
