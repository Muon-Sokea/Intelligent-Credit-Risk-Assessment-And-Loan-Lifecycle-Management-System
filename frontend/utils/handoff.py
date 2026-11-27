"""Sidebar Role Inbox trigger & high-contrast @st.dialog handoff hub."""

from __future__ import annotations

import streamlit as st

from utils.state import (
    STAFF_ROLES,
    add_handoff,
    get_handoffs_for_role,
    get_records,
    mark_handoff_read,
)

_SENDABLE_ROLES = [r for r in STAFF_ROLES if r != "All roles (full preview)"]

_ROLE_DEFAULT_PAGE = {
    "Loan officer": ("app_pages/loan_applications.py", "loan-applications"),
    "Credit analyst": ("app_pages/credit_assessment.py", "credit-assessment"),
    "Loan manager": ("app_pages/loan_management.py", "loan-management"),
    "Risk management officer": ("app_pages/risk_monitoring.py", "risk-monitoring"),
    "Customer service officer": ("app_pages/loan_management.py", "loan-management"),
}


@st.dialog("Role handoff inbox", width="medium")
def open_role_inbox_dialog(active_role: str) -> None:
    """High-contrast modal dialog for reading and sending inter-role handoffs."""
    incoming = get_handoffs_for_role(active_role)
    allowed_slugs = set(STAFF_ROLES.get(active_role, {}).get("pages", []))

    st.caption(
        f"Active role: **{active_role}** · View tasks handed off from other roles or send a new handoff note."
    )

    tab_in, tab_send = st.tabs(
        [
            f":material/inbox: Incoming ({len(incoming)})",
            ":material/send: Send handoff",
        ]
    )

    with tab_in:
        if not incoming:
            st.info("No handoffs for this role yet.", icon=":material/inbox:")
        else:
            for msg in incoming[:8]:
                with st.container(border=True):
                    top_l, top_r = st.columns([4, 1], vertical_alignment="center")
                    top_l.markdown(f"**{msg['subject']}**")
                    if not msg["read"]:
                        top_r.badge("New", color="orange")
                    else:
                        top_r.badge("Read", color="gray")

                    st.caption(
                        f"{msg['from_role']} → {msg['to_role']} · {msg['application_id']} · {msg['timestamp']}"
                    )
                    st.write(msg["message"])

                    btn_l, btn_r = st.columns(2)
                    if not msg["read"]:
                        if btn_l.button(
                            "Mark read",
                            key=f"read_{msg['id']}",
                            width="stretch",
                        ):
                            mark_handoff_read(msg["id"])
                            st.rerun()

                    if msg["target_slug"] in allowed_slugs:
                        if btn_r.button(
                            "Open case",
                            key=f"open_{msg['id']}",
                            type="primary",
                            width="stretch",
                        ):
                            mark_handoff_read(msg["id"])
                            st.session_state.selected_app_id = msg["application_id"]
                            st.switch_page(msg["target_page"])

    with tab_send:
        records = get_records()
        app_ids = [r["application_id"] for r in records]
        default_from = (
            active_role if active_role in _SENDABLE_ROLES else "Loan officer"
        )
        to_options = [r for r in _SENDABLE_ROLES if r != default_from] or _SENDABLE_ROLES

        to_role = st.selectbox("Send to role", options=to_options, key="ho_to_role")
        app_id = st.selectbox("Application / case", options=app_ids, key="ho_app_id")
        subject = st.text_input(
            "Subject",
            placeholder="e.g. Missing bank statement or borrower inquiry",
            key="ho_subject",
        )
        note = st.text_area(
            "Handoff message",
            placeholder="Describe what the next role needs to check or do...",
            height=90,
            key="ho_message",
        )
        if st.button("Send handoff", type="primary", width="stretch", key="ho_send_btn"):
            if not subject.strip() or not note.strip():
                st.error("Enter both a subject and a message.")
            else:
                target_page, target_slug = _ROLE_DEFAULT_PAGE.get(
                    to_role, ("app_pages/dashboard.py", "dashboard")
                )
                add_handoff(
                    from_role=default_from,
                    to_role=to_role,
                    application_id=app_id,
                    subject=subject.strip(),
                    message=note.strip(),
                    target_page=target_page,
                    target_slug=target_slug,
                )
                st.toast(f"Handoff sent to {to_role}", icon=":material/send:")
                st.rerun()


def render_role_inbox(active_role: str) -> None:
    """Render the sidebar button that opens the Role Handoff Inbox dialog."""
    incoming = get_handoffs_for_role(active_role)
    unread_count = sum(1 for m in incoming if not m["read"])

    label = f"Role inbox ({unread_count} new)" if unread_count else "Role inbox"
    icon = ":material/mark_email_unread:" if unread_count else ":material/mail:"

    if st.button(
        label,
        icon=icon,
        type="primary" if unread_count else "secondary",
        width="stretch",
        key="role_inbox_btn",
    ):
        open_role_inbox_dialog(active_role)
