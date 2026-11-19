import streamlit as st


NAV_GROUPS = (
    (
        "Workspace",
        (
            ("Dashboard", "space_dashboard"),
            ("Loan Applications", "description"),
        ),
    ),
    (
        "Credit & affordability",
        (
            ("Credit Assessment", "verified_user"),
            ("Debt & Affordability", "account_balance_wallet"),
        ),
    ),
    (
        "Portfolio",
        (
            ("Loan Monitoring", "monitoring"),
            ("Banking Analytics", "analytics"),
        ),
    ),
)

PAGE_NAMES = tuple(page_name for _, items in NAV_GROUPS for page_name, _ in items)
PAGE_TO_SLUG = {
    "Dashboard": "dashboard",
    "Loan Applications": "loan-applications",
    "Credit Assessment": "credit-assessment",
    "Debt & Affordability": "debt-affordability",
    "Loan Monitoring": "loan-monitoring",
    "Banking Analytics": "banking-analytics",
}
SLUG_TO_PAGE = {slug: page_name for page_name, slug in PAGE_TO_SLUG.items()}
ACTIVE_PAGE_QUERY_KEY = "page"
LAST_PAGE_ROUTE_STATE_KEY = "_last_active_page_route"


def synchronize_page_navigation() -> str:
    """Initialize the landing page and keep the visible page and URL in sync."""
    query_slug = st.query_params.get(ACTIVE_PAGE_QUERY_KEY)
    last_route = st.session_state.get(LAST_PAGE_ROUTE_STATE_KEY)
    current_page = st.session_state.get("active_page")

    if last_route is None:
        page_name = SLUG_TO_PAGE.get(query_slug) or (current_page if current_page in PAGE_NAMES else "Dashboard")
    elif query_slug != last_route:
        # A changed URL represents browser back/forward or a direct page link.
        page_name = SLUG_TO_PAGE.get(query_slug, "Dashboard")
    else:
        # Session state wins for ordinary widget reruns and in-app navigation.
        page_name = current_page if current_page in PAGE_NAMES else "Dashboard"

    st.session_state.active_page = page_name
    route = PAGE_TO_SLUG[page_name]
    if query_slug != route:
        st.query_params[ACTIVE_PAGE_QUERY_KEY] = route
    st.session_state[LAST_PAGE_ROUTE_STATE_KEY] = route
    return page_name


def _select_page(page_name):
    st.session_state.active_page = page_name
    if page_name == "Loan Applications":
        st.session_state["loan_application_view"] = "list"


def _open_new_application():
    from modules.loan_application import open_new_application

    open_new_application()


def _toggle_sidebar():
    st.session_state.sidebar_collapsed = not st.session_state.sidebar_collapsed


def _toggle_dark_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode


def _render_sidebar_toggle(collapsed):
    st.button(
        "Expand sidebar" if collapsed else "Collapse sidebar",
        key="sidebar-toggle",
        icon=":material/keyboard_double_arrow_right:" if collapsed else ":material/keyboard_double_arrow_left:",
        help="Expand sidebar" if collapsed else "Collapse sidebar",
        type="tertiary",
        width="stretch",
        on_click=_toggle_sidebar
    )


def _render_sidebar():
    collapsed = st.session_state.sidebar_collapsed

    with st.sidebar:
        if collapsed:
            st.markdown('<div class="sidebar-collapsed-marker"></div>', unsafe_allow_html=True)

        brand_markup = """
            <div class="brand-lockup">
                <svg class="brand-mark" width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
                    <path d="M4 12 16 5l12 7H4Zm2 2h3v10H6V14Zm8 0h4v10h-4V14Zm9 0h3v10h-3V14ZM4 27h24v2H4v-2Z"
                          fill="none" stroke="currentColor" stroke-width="1.8"
                          stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span class="brand-copy">
                    <strong>FinGuard AI</strong>
                    <small>Credit Risk Management</small>
                </span>
            </div>
        """

        with st.container(key="sidebar-brand-row"):
            if collapsed:
                st.markdown(brand_markup, unsafe_allow_html=True)
                _render_sidebar_toggle(collapsed=True)
            else:
                brand_col, toggle_col = st.columns(
                    [1, 0.22],
                    vertical_alignment="center",
                    gap="small"
                )
                with brand_col:
                    st.markdown(brand_markup, unsafe_allow_html=True)
                with toggle_col:
                    _render_sidebar_toggle(collapsed=False)

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        for group_name, group_items in NAV_GROUPS:
            st.markdown(
                f'<div class="sidebar-section-title nav-group-title">{group_name}</div>',
                unsafe_allow_html=True
            )
            for page_name, icon_name in group_items:
                st.button(
                    page_name,
                    key=f"navigation-{page_name}",
                    icon=f":material/{icon_name}:",
                    icon_position="left",
                    help=page_name if collapsed else None,
                    type="primary" if st.session_state.active_page == page_name else "tertiary",
                    width="stretch",
                    on_click=_select_page,
                    args=(page_name,)
                )

        with st.container(key="sidebar-bottom"):
            st.markdown(
                """
                <div class="sidebar-support-heading">
                    <div class="sidebar-section-title">Support & preferences</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            help_clicked = st.button(
                "Help & Support",
                key="help-support",
                icon=":material/help_outline:",
                help="Help & Support",
                type="tertiary",
                width="stretch"
            )
            settings_clicked = st.button(
                "Settings",
                key="settings",
                icon=":material/settings:",
                help="Settings",
                type="tertiary",
                width="stretch"
            )

            with st.container(key="sidebar-profile"):
                profile_markup = """
                    <div class="user-profile">
                        <span class="user-avatar">DU</span>
                        <span class="user-profile-copy">
                            <strong>Demo User</strong>
                            <small>Demo Account</small>
                        </span>
                    </div>
                """

                if collapsed:
                    st.markdown(profile_markup, unsafe_allow_html=True)
                    logout_clicked = st.button(
                        "Log out",
                        key="logout",
                        icon=":material/logout:",
                        help="Log out (demo only)",
                        type="tertiary",
                        width="stretch"
                    )
                else:
                    profile_col, logout_col = st.columns(
                        [1, 0.22],
                        vertical_alignment="center",
                        gap="small"
                    )
                    with profile_col:
                        st.markdown(profile_markup, unsafe_allow_html=True)
                    with logout_col:
                        logout_clicked = st.button(
                            "Log out",
                            key="logout",
                            icon=":material/logout:",
                            help="Log out (demo only)",
                            type="tertiary",
                            width="stretch"
                        )

    if help_clicked:
        st.toast("Help & Support is a prototype placeholder.")
    if settings_clicked:
        st.toast("Settings is a prototype placeholder.")
    if logout_clicked:
        st.toast("This demo does not use authentication.")


def _render_navbar():
    page_name = st.session_state.active_page
    dark_mode = st.session_state.dark_mode
    demo_badge = (
        '<span class="navbar-demo-badge">DEMO</span>'
        if page_name == "Loan Applications"
        else ""
    )

    with st.container(key="top-navbar"):
        title_col, search_col, controls_col = st.columns(
            [2, 4, 6],
            vertical_alignment="center",
            gap="small",
            wrap=False
        )

        with title_col:
            st.markdown(
                f'<div class="page-heading-row"><div class="page-heading">{page_name}</div>'
                f'{demo_badge}</div><div class="breadcrumb">Home <span>/</span> {page_name}</div>',
                unsafe_allow_html=True
            )

        with search_col:
            st.text_input(
                "Global search",
                placeholder="Search applications, attendees, events…",
                type="search",
                icon=":material/search:",
                label_visibility="collapsed",
                key="global-search"
            )

        with controls_col:
            with st.container(
                key="navbar-controls",
                horizontal=True,
                vertical_alignment="center",
                gap="small",
                wrap=False
            ):
                with st.container(
                    key="navbar-utilities",
                    horizontal=True,
                    vertical_alignment="center",
                    gap="small",
                    wrap=False
                ):
                    with st.popover(
                        "Notifications",
                        icon=":material/notifications:",
                        help="1 unread sample notification",
                        key="navbar-notifications"
                    ):
                        st.markdown("#### Notifications")
                        st.caption("Sample content only. No live alerts are connected.")
                        st.markdown(":material/info: **Example notification**")
                        st.caption("Notification examples will appear here.")

                    st.selectbox(
                        "Language",
                        options=("English", "Khmer"),
                        format_func=lambda language: "EN" if language == "English" else "KM",
                        index=0,
                        label_visibility="collapsed",
                        key="language",
                        width=68
                    )

                    st.button(
                        "Theme",
                        key="theme-toggle",
                        icon=":material/light_mode:" if dark_mode else ":material/dark_mode:",
                        help="Switch to light mode" if dark_mode else "Switch to dark mode",
                        type="tertiary",
                        on_click=_toggle_dark_mode
                    )

                st.markdown(
                    '<span class="navbar-divider" role="separator" '
                    'aria-orientation="vertical"></span>',
                    unsafe_allow_html=True
                )

                with st.container(
                    key="navbar-identity",
                    horizontal=True,
                    vertical_alignment="center",
                    gap="small",
                    wrap=False
                ):
                    st.markdown(
                        '<div class="navbar-avatar" role="img" '
                        'aria-label="Demo User">DU</div>',
                        unsafe_allow_html=True
                    )

                    with st.popover(
                        "Demo User",
                        help="Demo User account",
                        key="navbar-profile"
                    ):
                        st.markdown("**Demo User**")
                        st.caption("Demo Account")

                st.button(
                    "New Application",
                    key="new-application",
                    icon=":material/add:",
                    help="Open the new application form",
                    type="primary",
                    width="content",
                    wrap=False,
                    on_click=_open_new_application,
                )


def render_app_shell(show_workspace=True):
    _render_sidebar()
    _render_navbar()
    st.markdown(
        '<div class="top-navbar-spacer" aria-hidden="true"></div>',
        unsafe_allow_html=True
    )
    if show_workspace:
        st.markdown(
            '<div class="empty-workspace" aria-label="Main workspace"></div>',
            unsafe_allow_html=True
        )
