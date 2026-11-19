def load_css(dark_mode=False, sidebar_collapsed=False):
    if dark_mode:
        background = "#101827"
        surface = "#172338"
        sidebar = "#0B1728"
        text = "#F1F5F9"
        secondary = "#A7B4C5"
        border = "#33445C"
        input_background = "#1A2940"
        search_background = "#172338"
        profile_background = "#1E2B40"
        profile_border = "#344359"
        profile_text = "#C7D9F5"
        navbar_border = "rgba(255, 255, 255, 0.07)"
        navbar_search_border = "#2D3C52"
        navbar_hover_background = "#1B2A40"
    else:
        background = "#F5F7FA"
        surface = "#FFFFFF"
        sidebar = "#142B4A"
        text = "#1E293B"
        secondary = "#64748B"
        border = "#E2E8F0"
        input_background = "#FFFFFF"
        search_background = "#FBFCFD"
        profile_background = "#F1F5F9"
        profile_border = "#E2E8F0"
        profile_text = "#475569"
        navbar_border = "rgba(0, 0, 0, 0.05)"
        navbar_search_border = "#E9EEF4"
        navbar_hover_background = "#F8FAFC"

    sidebar_width = "80px" if sidebar_collapsed else "272px"

    return f"""
    <style>
    :root {{
        --fin-primary: #2563EB;
        --fin-primary-hover: #1D4ED8;
        --fin-sidebar-width: {sidebar_width};
        --fin-content-padding: 1.5rem;
    }}

    :root:has([data-testid="stSidebar"][aria-expanded="false"]) {{
        --fin-sidebar-width: 16px;
    }}

    .stApp,
    [data-testid="stAppViewContainer"] {{
        background: {background};
        color: {text};
    }}

    [data-testid="stMain"] .block-container {{
        max-width: 1600px;
        padding: 0.8rem 1.6rem 1rem;
    }}

    [data-testid="stMain"] .block-container > [data-testid="stVerticalBlock"] {{
        gap: 8px !important;
    }}

    [data-testid="stHeader"] {{
        background: transparent;
    }}

    [data-testid="stToolbar"],
    [data-testid="stDeployButton"] {{
        display: none;
    }}

    footer {{
        display: none;
    }}

    [data-testid="stSidebar"],
    section[data-testid="stSidebar"] {{
        width: {sidebar_width} !important;
        min-width: {sidebar_width} !important;
        background: {sidebar};
        border-right: 1px solid #263F5D;
        transition: width 180ms ease, min-width 180ms ease;
    }}

    [data-testid="stSidebar"] > div:first-child {{
        background: {sidebar};
    }}

    [data-testid="stSidebarHeader"] {{
        display: none !important;
    }}

    [data-testid="stSidebar"] .block-container {{
        display: flex;
        flex-direction: column;
        min-height: calc(100vh - 1rem);
        padding: 16px;
    }}

    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        gap: 8px !important;
    }}

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        margin-bottom: 0 !important;
    }}

    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label {{
        color: #E5EDF7;
    }}

    .brand-lockup {{
        display: flex;
        align-items: center;
        gap: 8px;
        min-height: 40px;
    }}

    .brand-mark {{
        box-sizing: border-box;
        display: block;
        flex: 0 0 40px;
        width: 40px;
        height: 40px;
        padding: 8px;
        color: #FFFFFF;
        background: #294D78;
        border-radius: 12px;
    }}

    .brand-copy {{
        display: flex;
        flex-direction: column;
        gap: 0;
        min-width: 0;
    }}

    .brand-copy strong {{
        color: #FFFFFF;
        font-size: 0.92rem;
        font-weight: 700;
        line-height: 1.2;
        white-space: nowrap;
    }}

    .brand-copy small {{
        color: #B7C6D9;
        font-size: 0.625rem;
        line-height: 16px;
        white-space: nowrap;
    }}

    .sidebar-divider {{
        height: 1px;
        width: 100%;
        background: #304865;
        margin: 0;
    }}

    .sidebar-section-title {{
        color: #91A8C2;
        font-size: 0.66rem;
        font-weight: 650;
        letter-spacing: 0.075em;
        line-height: 16px;
        margin: 0;
        min-height: 16px;
        padding-left: 40px;
        text-transform: uppercase;
    }}

    .nav-group-title {{
        margin-top: 8px;
    }}

    .sidebar-support-heading {{
        border-top: 1px solid #304865;
        padding-top: 8px;
    }}

    [data-testid="stSidebar"] .st-key-sidebar-bottom {{
        margin-top: auto;
    }}

    [data-testid="stSidebar"] .st-key-sidebar-profile {{
        border-top: 1px solid #304865;
        padding-top: 8px;
    }}

    [data-testid="stSidebar"] .st-key-sidebar-brand-row [data-testid="stHorizontalBlock"],
    [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="stHorizontalBlock"] {{
        align-items: center;
        flex-wrap: nowrap;
        gap: 8px !important;
    }}

    [data-testid="stSidebar"] .st-key-sidebar-brand-row [data-testid="column"]:first-child,
    [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="column"]:first-child {{
        flex: 1 1 auto !important;
        min-width: 0 !important;
        width: auto !important;
    }}

    [data-testid="stSidebar"] .st-key-sidebar-brand-row [data-testid="column"]:last-child,
    [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="column"]:last-child {{
        flex: 0 0 40px !important;
        min-width: 40px !important;
        width: 40px !important;
    }}

    [data-testid="stSidebar"] .st-key-sidebar-brand-row .st-key-sidebar-toggle {{
        width: 40px;
    }}

    [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] {{
        width: 100%;
    }}

    [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] > button[data-testid^="stBaseButton-"] {{
        box-sizing: border-box;
        align-items: center;
        display: flex !important;
        gap: 8px;
        justify-content: flex-start !important;
        min-height: 40px;
        padding: 8px;
        text-align: left !important;
        width: 100%;
    }}

    [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] > button > div {{
        align-items: center;
        display: flex;
        justify-content: flex-start !important;
        width: 100%;
    }}

    [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] > button > div > span > span:first-child {{
        align-items: center;
        display: flex;
        flex: 0 0 24px;
        height: 24px;
        justify-content: center;
        width: 24px;
    }}

    [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] > button [data-testid="stIconMaterial"] {{
        font-size: 20px !important;
        text-align: center;
    }}

    [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] > button p {{
        margin: 0 !important;
        font-size: 0.875rem;
        line-height: 20px;
        text-align: left !important;
    }}

    /* Navigation buttons without hover help use a direct Streamlit wrapper. */
    [data-testid="stSidebar"] [class*="st-key-navigation-"] {{
        width: 100%;
    }}

    [data-testid="stSidebar"] [class*="st-key-navigation-"] button[data-testid^="stBaseButton-"] {{
        box-sizing: border-box;
        align-items: center;
        display: flex !important;
        gap: 8px;
        justify-content: flex-start !important;
        min-height: 40px;
        padding: 8px;
        text-align: left !important;
        width: 100%;
    }}

    [data-testid="stSidebar"] [class*="st-key-navigation-"] button > div {{
        align-items: center;
        display: flex;
        justify-content: flex-start !important;
        width: 100%;
    }}

    [data-testid="stSidebar"] [class*="st-key-navigation-"] button > div > span > span:first-child {{
        align-items: center;
        display: flex;
        flex: 0 0 24px;
        height: 24px;
        justify-content: center;
        width: 24px;
    }}

    [data-testid="stSidebar"] button[data-testid="stBaseButton-tertiary"] {{
        justify-content: flex-start;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 9px;
        color: #D8E3F0;
        transition: background-color 160ms ease, color 160ms ease;
    }}

    [data-testid="stSidebar"] .st-key-sidebar-toggle button p,
    [data-testid="stSidebar"] .st-key-logout button p {{
        display: none !important;
    }}

    [data-testid="stSidebar"] .st-key-logout button {{
        width: 40px;
        min-width: 40px;
        min-height: 40px;
        justify-content: center !important;
        padding: 0;
        background: transparent;
        border-color: transparent;
    }}

    [data-testid="stSidebar"] .st-key-logout button:hover {{
        background: #193657;
        border-color: #284766;
    }}

    [data-testid="stSidebar"] .st-key-logout button:focus-visible {{
        outline: 2px solid #60A5FA;
        outline-offset: 1px;
    }}

    [data-testid="stSidebar"] [data-testid="stBaseButton-tertiary"]:hover {{
        color: #FFFFFF;
        background: #193657;
        border-color: #284766;
    }}

    [data-testid="stButton"] > button[kind="primary"],
    button[data-testid="stBaseButton-primary"] {{
        color: #FFFFFF !important;
        background: #2563EB !important;
        border: 1px solid #2563EB !important;
    }}

    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {{
        justify-content: flex-start;
        border-radius: 9px;
        background: #1E4774 !important;
        border-color: #1E4774 !important;
        box-shadow: inset 3px 0 #60A5FA;
    }}

    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover {{
        background: #25568A !important;
        border-color: #25568A !important;
    }}

    [data-testid="stButton"] > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {{
        background: #1D4ED8 !important;
        border-color: #1D4ED8 !important;
    }}

    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] *,
    [data-testid="stSidebar"] button[data-testid="stBaseButton-tertiary"] * {{
        color: inherit;
    }}

    [data-testid="stSidebar"] .st-key-sidebar-toggle button {{
        width: 40px;
        min-width: 40px;
        min-height: 40px;
        justify-content: center;
        padding: 0;
        color: #C6D4E5;
        background: transparent;
        border: 1px solid transparent;
    }}

    .user-profile {{
        display: flex;
        align-items: center;
        gap: 8px;
        min-height: 48px;
        padding: 0;
    }}

    .user-avatar {{
        align-items: center;
        background: #345B84;
        border: 1px solid #52769A;
        border-radius: 50%;
        color: #FFFFFF;
        display: inline-flex;
        flex: 0 0 40px;
        font-size: 0.74rem;
        font-weight: 700;
        height: 40px;
        justify-content: center;
        width: 40px;
    }}

    .user-profile-copy {{
        display: flex;
        flex-direction: column;
        gap: 0;
        min-width: 0;
    }}

    .user-profile-copy strong {{
        color: #FFFFFF;
        font-size: 0.75rem;
        line-height: 1.2;
    }}

    .user-profile-copy small {{
        color: #B7C6D9;
        font-size: 0.625rem;
        line-height: 16px;
    }}

    [data-testid="stMain"] .block-container > div[data-testid="stHorizontalBlock"] {{
        align-items: center;
    }}

    .st-key-top-navbar {{
        align-items: center;
        background: {surface};
        border: 1px solid {navbar_border};
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
        box-sizing: border-box;
        flex: 0 0 72px !important;
        height: 72px !important;
        min-height: 72px !important;
        margin-bottom: 0;
        left: calc(var(--fin-sidebar-width) + var(--fin-content-padding));
        right: var(--fin-content-padding);
        width: calc(100% - var(--fin-sidebar-width) - var(--fin-content-padding) - var(--fin-content-padding));
        max-width: 1552px;
        margin-left: auto;
        margin-right: auto;
        display: flex;
        justify-content: center;
        padding: 0 16px;
        position: fixed;
        top: 12px;
        z-index: 1000;
    }}

    .st-key-top-navbar [data-testid="stVerticalBlock"] {{
        gap: 0 !important;
    }}

    .top-navbar-spacer {{
        height: 72px;
    }}

    [data-testid="stMain"] .block-container {{
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }}

    .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) {{
        align-items: center;
        display: grid !important;
        gap: 12px;
        grid-template-columns: minmax(150px, 1fr) minmax(0, 320px) minmax(540px, 2fr);
        width: 100%;
    }}

    .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) > [data-testid="stColumn"] {{
        align-items: center;
        min-width: 0 !important;
        width: auto !important;
        flex: none !important;
    }}

    .st-key-navbar-controls {{
        align-items: center !important;
        display: flex !important;
        flex: 0 1 auto;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 0 !important;
        justify-content: flex-end;
        min-width: 0;
        overflow: visible;
        width: 100%;
    }}

    .st-key-navbar-controls > * {{
        flex: 0 0 auto !important;
    }}

    .st-key-navbar-controls > [data-testid="stLayoutWrapper"]:has(.st-key-navbar-utilities) {{
        flex: 0 0 auto !important;
        width: auto !important;
    }}

    .st-key-navbar-utilities {{
        align-items: center !important;
        display: flex !important;
        flex: 0 0 auto;
        flex-direction: row !important;
        gap: 10px !important;
        width: auto !important;
    }}

    .st-key-navbar-utilities > * {{
        flex: 0 0 auto !important;
        width: auto !important;
    }}

    .st-key-global-search {{
        max-width: 320px;
        min-width: 0;
        width: 100%;
    }}

    .st-key-global-search input {{
        box-sizing: border-box;
        background: {search_background};
        border: 1px solid {navbar_search_border};
        border-radius: 10px;
        height: 44px !important;
        min-height: 44px !important;
        font-size: 0.875rem;
        transition: border-color 200ms ease, box-shadow 200ms ease, background-color 200ms ease;
    }}

    .st-key-navbar-notifications {{
        flex: 0 0 36px;
        width: 36px;
    }}

    .st-key-navbar-notifications button[data-testid="stPopoverButton"] {{
        align-items: center;
        box-sizing: border-box;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 10px;
        color: {secondary};
        height: 36px;
        justify-content: center;
        padding: 0;
        position: relative;
        width: 36px;
    }}

    .st-key-navbar-notifications button[data-testid="stPopoverButton"]::after {{
        background: #2563EB;
        border: 2px solid {surface};
        border-radius: 50%;
        content: "";
        height: 6px;
        position: absolute;
        right: 5px;
        top: 5px;
        width: 6px;
    }}

    .st-key-navbar-notifications button[data-testid="stPopoverButton"] > div > div[aria-hidden="true"] {{
        display: none !important;
    }}

    .st-key-navbar-notifications [data-testid="stMarkdownContainer"] {{
        height: 1px;
        margin: -1px;
        overflow: hidden;
        position: absolute;
        white-space: nowrap;
        width: 1px;
        clip: rect(0, 0, 0, 0);
    }}

    .st-key-language {{
        flex: 0 0 68px !important;
        width: 68px !important;
    }}

    .st-key-language [data-baseweb="select"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 9px;
        box-sizing: border-box;
        height: 36px;
        min-height: 36px;
    }}

    .st-key-language [data-baseweb="select"]:hover {{
        background: {navbar_hover_background};
        border-color: {navbar_border};
    }}

    .st-key-navbar-controls > [data-testid="stElementContainer"]:has(.navbar-divider) {{
        flex: 0 0 1px !important;
        width: 1px !important;
        margin: 0 6px;
    }}

    .navbar-divider {{
        background: {navbar_border};
        display: block;
        height: 24px;
        width: 1px;
    }}

    .st-key-theme-toggle {{
        align-items: center;
        display: flex;
        flex: 0 0 36px;
        height: 36px;
        justify-content: center;
        width: 36px;
    }}

    .st-key-theme-toggle button {{
        align-items: center;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 10px;
        color: {secondary};
        height: 36px;
        justify-content: center;
        min-height: 36px;
        padding: 0;
        transition: background-color 200ms ease, border-color 200ms ease, color 200ms ease;
        width: 36px;
    }}

    .st-key-theme-toggle button p {{
        clip: rect(0, 0, 0, 0);
        height: 1px;
        margin: -1px;
        overflow: hidden;
        position: absolute;
        white-space: nowrap;
        width: 1px;
    }}

    .st-key-theme-toggle button [data-testid="stIconMaterial"] {{
        font-size: 19px;
    }}

    .st-key-navbar-identity {{
        align-items: center !important;
        display: flex !important;
        flex-direction: row !important;
        flex: 0 0 auto;
        gap: 6px !important;
        width: auto !important;
    }}

    .st-key-navbar-identity > * {{
        flex: 0 0 auto !important;
    }}

    .st-key-navbar-identity > [data-testid="stElementContainer"] {{
        align-items: center;
        display: flex;
        flex: 0 0 30px !important;
        height: 40px;
        width: 30px !important;
    }}

    .st-key-navbar-controls > [data-testid="stLayoutWrapper"]:has(.st-key-navbar-identity) {{
        flex: 0 0 auto !important;
        width: auto !important;
    }}

    .st-key-navbar-profile {{
        flex: 0 0 auto;
        width: auto;
    }}

    .st-key-navbar-profile button[data-testid="stPopoverButton"] {{
        align-items: center;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 9px;
        box-sizing: border-box;
        color: {text};
        font-size: 0.8125rem;
        font-weight: 600;
        height: 36px;
        justify-content: flex-start;
        min-height: 36px;
        padding: 0 4px;
        transition: background-color 200ms ease, border-color 200ms ease;
        white-space: nowrap;
        width: auto !important;
    }}

    .navbar-avatar {{
        align-items: center;
        background: {profile_background};
        border: 1px solid {profile_border};
        border-radius: 50%;
        box-sizing: border-box;
        color: {profile_text};
        display: flex;
        font-size: 0.6875rem;
        font-weight: 700;
        height: 30px;
        justify-content: center;
        width: 30px;
    }}

    .st-key-navbar-controls button:focus-visible,
    .st-key-navbar-controls input:focus-visible,
    .st-key-navbar-controls [data-baseweb="select"]:focus-within {{
        outline: 2px solid #60A5FA;
        outline-offset: 2px;
    }}

    .page-heading-row {{
        align-items: center;
        display: flex;
        gap: 7px;
        white-space: nowrap;
    }}

    .page-heading {{
        color: {text};
        font-size: 1.0625rem;
        font-weight: 700;
        line-height: 20px;
        white-space: nowrap;
    }}

    .navbar-demo-badge {{
        align-items: center;
        background: {profile_background};
        border: 1px solid {profile_border};
        border-radius: 999px;
        color: {profile_text};
        display: inline-flex;
        font-size: 0.5625rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        line-height: 1;
        padding: 3px 6px;
    }}

    .breadcrumb {{
        color: {secondary};
        font-size: 0.75rem;
        line-height: 16px;
        margin-top: 2px;
        white-space: nowrap;
    }}

    .breadcrumb span {{
        color: #94A3B8;
        padding: 0 0.2rem;
    }}

    .st-key-new-application {{
        flex: 0 0 156px !important;
        margin-left: 20px;
        width: 156px !important;
    }}

    .st-key-new-application button {{
        align-items: center;
        box-sizing: border-box;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(37, 99, 235, 0.12);
        font-size: 0.8125rem;
        font-weight: 650;
        height: 40px;
        min-height: 40px;
        padding: 0 10px;
        transition: box-shadow 200ms ease, transform 200ms ease, background-color 200ms ease;
        white-space: nowrap;
        width: 156px;
    }}

    .st-key-new-application button:hover {{
        box-shadow: 0 3px 8px rgba(37, 99, 235, 0.18);
        transform: translateY(-1px);
    }}

    .stTextInput input,
    .stSelectbox div[data-baseweb="select"] {{
        background: {input_background};
        border-color: {border};
        border-radius: 9px;
        min-height: 40px;
    }}

    .stTextInput input:focus,
    .stSelectbox div[data-baseweb="select"]:focus-within {{
        border-color: #2563EB;
        box-shadow: 0 0 0 1px #2563EB;
    }}

    .st-key-global-search input:focus {{
        background: {surface};
        border-color: #2563EB;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
    }}

    button[data-testid="stPopoverButton"] {{
        border-radius: 9px;
        font-size: 0.78rem;
        font-weight: 600;
        min-height: 40px;
        transition: background-color 160ms ease, border-color 160ms ease, transform 160ms ease;
    }}

    .st-key-navbar-notifications button[data-testid="stPopoverButton"],
    .st-key-navbar-profile button[data-testid="stPopoverButton"] {{
        transition: background-color 200ms ease, border-color 200ms ease, color 200ms ease;
    }}

    [data-testid="stMain"] .stButton > button[kind="secondary"],
    button[data-testid="stPopoverButton"] {{
        background: {surface};
        border: 1px solid {border};
        color: {text};
    }}

    .stSelectbox div[data-baseweb="select"],
    .stSelectbox div[data-baseweb="select"] * {{
        color: {text};
    }}

    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="option"] {{
        background: {surface};
        color: {text};
    }}

    .stButton > button:hover {{
        transform: translateY(-1px);
    }}

    button[data-testid="stPopoverButton"] {{
        width: 100%;
        justify-content: center;
    }}

    .st-key-navbar-notifications button[data-testid="stPopoverButton"]:hover,
    .st-key-theme-toggle button:hover,
    .st-key-navbar-profile button[data-testid="stPopoverButton"]:hover {{
        background: {navbar_hover_background};
        border-color: {navbar_border};
        color: {text};
    }}

    .empty-workspace {{
        min-height: calc(100vh - 150px);
    }}

    [data-testid="stPopoverBody"] {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 12px;
        color: {text};
    }}

    [data-testid="stPopoverBody"] p {{
        color: {secondary};
    }}

    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) {{
        width: 80px !important;
        min-width: 80px !important;
    }}

    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) .brand-copy,
    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) .sidebar-section-title,
    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) .sidebar-divider:not(.profile-divider),
    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) .user-profile-copy,
    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) [data-testid="stTooltipHoverTarget"] > button p,
    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) [class*="st-key-navigation-"] button p {{
        display: none !important;
    }}

    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) .brand-lockup,
    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) .user-profile {{
        justify-content: center;
    }}

    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) [data-testid="stTooltipHoverTarget"] > button {{
        justify-content: center !important;
        padding: 0;
    }}

    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) [class*="st-key-navigation-"] button {{
        justify-content: center !important;
        padding: 0;
    }}

    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) [data-testid="stTooltipHoverTarget"] > button > div {{
        justify-content: center !important;
    }}

    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) [class*="st-key-navigation-"] button > div {{
        justify-content: center !important;
    }}

    [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) .st-key-sidebar-toggle button {{
        margin: 0 auto;
    }}

    @media (max-width: 1280px) and (min-width: 1101px) {{
        :root:not(:has([data-testid="stSidebar"][aria-expanded="false"])):not(:has(.sidebar-collapsed-marker)) .st-key-top-navbar {{
            flex: 0 0 auto !important;
            height: auto !important;
            min-height: 0 !important;
            padding: 4px 16px;
        }}

        :root:not(:has([data-testid="stSidebar"][aria-expanded="false"])):not(:has(.sidebar-collapsed-marker)) .top-navbar-spacer {{
            height: 104px;
        }}

        :root:not(:has([data-testid="stSidebar"][aria-expanded="false"])):not(:has(.sidebar-collapsed-marker)) .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) {{
            grid-template-columns: minmax(144px, 1.5fr) minmax(0, 4.5fr);
            grid-template-rows: auto auto;
            row-gap: 8px;
        }}

        :root:not(:has([data-testid="stSidebar"][aria-expanded="false"])):not(:has(.sidebar-collapsed-marker)) .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) > [data-testid="stColumn"]:nth-child(1) {{
            grid-column: 1;
            grid-row: 1;
        }}

        :root:not(:has([data-testid="stSidebar"][aria-expanded="false"])):not(:has(.sidebar-collapsed-marker)) .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) > [data-testid="stColumn"]:nth-child(2) {{
            grid-column: 2;
            grid-row: 1;
        }}

        :root:not(:has([data-testid="stSidebar"][aria-expanded="false"])):not(:has(.sidebar-collapsed-marker)) .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) > [data-testid="stColumn"]:nth-child(3) {{
            grid-column: 1 / -1;
            grid-row: 2;
        }}
    }}

    @media (max-width: 1100px) and (min-width: 761px) {{
        :root {{
            --fin-sidebar-width: {"80px" if sidebar_collapsed else "240px"};
            --fin-content-padding: 0.9rem;
        }}

        .st-key-top-navbar {{
            flex: 0 0 auto !important;
            height: auto !important;
            min-height: 0 !important;
            padding: 4px 16px;
        }}

        .top-navbar-spacer {{
            height: 104px;
        }}

        .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) {{
            grid-template-columns: minmax(144px, 1.5fr) minmax(0, 4.5fr);
            grid-template-rows: auto auto;
            row-gap: 8px;
        }}

        .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) > [data-testid="stColumn"]:nth-child(1) {{
            grid-column: 1;
            grid-row: 1;
        }}

        .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) > [data-testid="stColumn"]:nth-child(2) {{
            grid-column: 2;
            grid-row: 1;
        }}

        .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) > [data-testid="stColumn"]:nth-child(3) {{
            grid-column: 1 / -1;
            grid-row: 2;
        }}
    }}

    @media (max-width: 1100px) and (min-width: 761px) {{
        .st-key-navbar-controls {{
            justify-content: flex-end;
        }}

        [data-testid="stSidebar"],
        section[data-testid="stSidebar"] {{
            width: 240px !important;
            min-width: 240px !important;
        }}

        [data-testid="stSidebar"]:has(.sidebar-collapsed-marker) {{
            width: 80px !important;
            min-width: 80px !important;
        }}

        [data-testid="stMain"] .block-container {{
            padding-left: 0.9rem;
            padding-right: 0.9rem;
        }}

    }}

    @media (max-width: 760px) {{
        [data-testid="stMain"] .block-container {{
            padding: 0.8rem 0.65rem;
        }}

        :root {{
            --fin-sidebar-width: 80px;
            --fin-content-padding: 0.65rem;
        }}

        .st-key-top-navbar {{
            flex: 0 0 auto !important;
            height: auto !important;
            min-height: 0 !important;
            padding: 4px 8px 8px;
        }}

        .top-navbar-spacer {{
            height: 152px;
        }}

        .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) {{
            grid-template-columns: minmax(0, 1fr);
            grid-template-rows: auto auto auto;
            row-gap: 8px;
        }}

        .st-key-top-navbar [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) > [data-testid="stColumn"] {{
            grid-column: 1 !important;
            grid-row: auto !important;
        }}

        .st-key-global-search {{
            max-width: none;
        }}

        .st-key-navbar-controls {{
            max-width: 100%;
            overflow-x: auto;
        }}

        [data-testid="stSidebar"],
        section[data-testid="stSidebar"] {{
            width: 80px !important;
            min-width: 80px !important;
        }}

        [data-testid="stSidebar"] .block-container {{
            padding: 8px;
        }}

        [data-testid="stSidebar"] .brand-copy,
        [data-testid="stSidebar"] .sidebar-section-title,
        [data-testid="stSidebar"] .sidebar-divider:not(.profile-divider),
        [data-testid="stSidebar"] .user-profile-copy,
        [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] > button p {{
            display: none !important;
        }}

        [data-testid="stSidebar"] .brand-lockup,
        [data-testid="stSidebar"] .user-profile {{
            justify-content: center;
        }}

        [data-testid="stSidebar"] .st-key-sidebar-brand-row [data-testid="stHorizontalBlock"],
        [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="stHorizontalBlock"] {{
            flex-direction: column;
            gap: 8px !important;
        }}

        [data-testid="stSidebar"] .st-key-sidebar-brand-row [data-testid="column"],
        [data-testid="stSidebar"] .st-key-sidebar-profile [data-testid="column"] {{
            flex: 1 1 100% !important;
            min-width: 0 !important;
            width: 100% !important;
        }}

        [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] > button {{
            justify-content: center !important;
            padding: 0;
        }}

        [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] > button > div {{
            justify-content: center !important;
        }}

        .empty-workspace {{
            min-height: calc(100vh - 220px);
        }}
    }}
    </style>
    """
