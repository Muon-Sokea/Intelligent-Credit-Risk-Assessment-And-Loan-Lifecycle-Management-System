import html
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from data.dashboard_demo import create_dashboard_demo_data


_RISK_ORDER = ("Low Risk", "Medium Risk", "High Risk")
_RISK_COLORS = ("#16A36A", "#E9A23B", "#DC4B4B")

_ICON_PATHS = {
    "applications": (
        '<rect x="5" y="3.5" width="14" height="17" rx="2"/>'
        '<path d="M9 8h6M9 12h6M9 16h3"/>'
    ),
    "loans": (
        '<path d="M3 9.5 12 4l9 5.5M5 10v8m4-8v8m6-8v8m4-8v8M3 20h18"/>'
    ),
    "risk": (
        '<path d="M12 3 19 6v5c0 4.4-2.8 7.7-7 10-4.2-2.3-7-5.6-7-10V6l7-3Z"/>'
        '<path d="M12 8v4m0 3h.01"/>'
    ),
    "overdue": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M12 7v5l3 2"/>'
    ),
    "warning": (
        '<path d="M12 3.5 2.8 20h18.4L12 3.5Z"/>'
        '<path d="M12 9v4.5m0 3h.01"/>'
    ),
    "schedule": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M12 7v5l3 2"/>'
    ),
    "monitoring": (
        '<path d="M3 17 9 11l4 4 8-8"/>'
        '<path d="M15 7h6v6"/>'
    ),
}

_DASHBOARD_CSS = """
<style>
.st-key-dashboard-page {
    padding-top: 0;
}

.st-key-dashboard-page > [data-testid="stVerticalBlock"] {
    gap: 8px !important;
}

.st-key-dashboard-snapshot-header {
    margin-bottom: 8px;
}

.st-key-dashboard-snapshot-header [data-testid="stVerticalBlock"] {
    gap: 4px !important;
}

.dashboard-snapshot-title {
    color: var(--dashboard-text);
    font-size: 1.05rem;
    font-weight: 680;
    line-height: 1.35;
    margin: 0;
}

.dashboard-snapshot-description {
    color: var(--dashboard-muted);
    font-size: 0.75rem;
    line-height: 1.4;
    margin: 8px 0 0;
}

.dashboard-period-caption {
    color: var(--dashboard-muted);
    font-size: 0.72rem;
    line-height: 1.35;
    margin-top: 4px;
    text-align: right;
}

.st-key-dashboard-period [data-baseweb="select"],
.st-key-dashboard-custom-date [data-baseweb="select"] {
    background: var(--dashboard-surface);
    border: 1px solid var(--dashboard-border);
    border-radius: 10px;
    min-height: 40px;
}

.dashboard-section-heading {
    align-items: end;
    display: flex;
    justify-content: space-between;
    margin: 8px 0 12px;
}

.dashboard-section-title {
    color: var(--dashboard-text);
    font-size: 1rem;
    font-weight: 680;
    line-height: 1.35;
    margin: 0;
}

.dashboard-section-caption {
    color: var(--dashboard-muted);
    font-size: 0.75rem;
    margin: 3px 0 0;
}

.st-key-dashboard-kpi-grid [data-testid="stHorizontalBlock"] {
    align-items: stretch;
    gap: 12px;
}

.dashboard-kpi-card {
    background: var(--dashboard-surface);
    border: 1px solid var(--dashboard-border);
    border-radius: 14px;
    box-shadow: var(--dashboard-shadow);
    box-sizing: border-box;
    min-height: 142px;
    padding: 16px 17px;
    transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}

.dashboard-kpi-card:hover {
    border-color: rgba(37, 99, 235, 0.3);
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
    transform: translateY(-2px);
}

.dashboard-kpi-heading {
    align-items: center;
    color: var(--dashboard-muted);
    display: flex;
    font-size: 0.76rem;
    font-weight: 620;
    gap: 9px;
    line-height: 1.3;
    min-height: 34px;
}

.dashboard-kpi-icon {
    align-items: center;
    background: color-mix(in srgb, var(--kpi-accent) 10%, transparent);
    border-radius: 10px;
    color: var(--kpi-accent);
    display: inline-flex;
    flex: 0 0 34px;
    height: 34px;
    justify-content: center;
    width: 34px;
}

.dashboard-kpi-icon svg,
.dashboard-alert-icon svg {
    fill: none;
    height: 18px;
    stroke: currentColor;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-width: 1.7;
    width: 18px;
}

.dashboard-kpi-value {
    color: var(--dashboard-text);
    font-size: 1.7rem;
    font-variant-numeric: tabular-nums;
    font-weight: 720;
    letter-spacing: -0.04em;
    line-height: 1.2;
    margin-top: 13px;
}

.dashboard-kpi-support {
    color: var(--dashboard-muted);
    font-size: 0.7rem;
    line-height: 1.35;
    margin-top: 4px;
}

.st-key-dashboard-charts-row [data-testid="stHorizontalBlock"] {
    align-items: stretch;
    gap: 16px;
}

.st-key-dashboard-performance-row [data-testid="stHorizontalBlock"] {
    align-items: stretch;
    display: grid !important;
    gap: 16px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
}

.st-key-dashboard-performance-row [data-testid="stColumn"] {
    align-self: stretch;
    display: flex !important;
    min-width: 0 !important;
    width: auto !important;
}

.st-key-dashboard-performance-row [data-testid="stColumn"] > div {
    display: flex;
    flex: 1 1 auto;
    min-width: 0;
    width: 100%;
}

.st-key-dashboard-panel-portfolio,
.st-key-dashboard-panel-risk,
.st-key-dashboard-panel-repayments,
.st-key-dashboard-panel-alerts,
.st-key-dashboard-applications-panel {
    background: var(--dashboard-surface);
    border: 1px solid var(--dashboard-border);
    border-radius: 14px;
    box-shadow: var(--dashboard-shadow);
    padding: 17px 18px 12px;
    box-sizing: border-box;
}

.st-key-dashboard-panel-repayments,
.st-key-dashboard-panel-alerts {
    min-height: 320px;
    width: 100%;
}

.st-key-dashboard-panel-alerts {
    display: flex;
    flex-direction: column;
}

.st-key-dashboard-panel-portfolio [data-testid="stVerticalBlock"],
.st-key-dashboard-panel-risk [data-testid="stVerticalBlock"],
.st-key-dashboard-panel-repayments [data-testid="stVerticalBlock"],
.st-key-dashboard-panel-alerts [data-testid="stVerticalBlock"],
.st-key-dashboard-applications-panel [data-testid="stVerticalBlock"] {
    gap: 8px;
}

.dashboard-panel-heading {
    margin-bottom: 0;
}

.dashboard-panel-title {
    color: var(--dashboard-text);
    font-size: 0.91rem;
    font-weight: 660;
    line-height: 1.35;
    margin: 0;
}

.dashboard-panel-caption {
    color: var(--dashboard-muted);
    font-size: 0.72rem;
    line-height: 1.4;
    margin: 3px 0 0;
}

.dashboard-alert-card {
    display: flex;
    flex-direction: column;
    background: var(--dashboard-subtle);
    border: 1px solid var(--dashboard-border);
    border-radius: 12px;
    box-sizing: border-box;
    height: 160px;
    min-height: 160px;
    padding: 13px;
    width: 100%;
}

.st-key-dashboard-alerts-grid [data-testid="stHorizontalBlock"] {
    align-items: stretch;
    display: grid !important;
    gap: 12px;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    width: 100%;
}

.st-key-dashboard-alerts-grid [data-testid="stColumn"] {
    align-self: stretch;
    display: flex !important;
    min-width: 0 !important;
    width: auto !important;
}

.st-key-dashboard-alerts-grid [data-testid="stColumn"] > div {
    display: flex;
    flex: 1 1 auto;
    min-width: 0;
    width: 100%;
}

.st-key-dashboard-panel-alerts [data-testid="stElementContainer"]:has(.st-key-dashboard-alerts-grid) {
    margin-block: auto;
}

.dashboard-alert-topline {
    align-items: center;
    display: flex;
    gap: 8px;
    min-height: 32px;
}

.dashboard-alert-icon {
    align-items: center;
    background: var(--alert-tint);
    border-radius: 8px;
    color: var(--alert-color);
    display: inline-flex;
    flex: 0 0 32px;
    height: 32px;
    justify-content: center;
    width: 32px;
}

.dashboard-alert-icon svg {
    height: 16px;
    width: 16px;
}

.dashboard-alert-label {
    background: var(--alert-tint);
    border-radius: 999px;
    color: var(--alert-color);
    display: inline-flex;
    font-size: 0.56rem;
    font-weight: 760;
    letter-spacing: 0.075em;
    line-height: 1.2;
    overflow: hidden;
    padding: 4px 7px;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.dashboard-alert-caseid {
    color: var(--dashboard-muted);
    font-size: 0.63rem;
    font-weight: 650;
    letter-spacing: 0.015em;
    line-height: 1.2;
    margin-top: 9px;
    white-space: nowrap;
}

.dashboard-alert-title {
    color: var(--dashboard-text);
    font-size: 0.82rem;
    font-weight: 700;
    line-height: 1.35;
    margin-top: 4px;
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}

.dashboard-alert-description {
    color: var(--dashboard-muted);
    font-size: 0.68rem;
    line-height: 1.4;
    margin-top: 4px;
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}

.st-key-dashboard-applications-panel [data-testid="stDataFrame"] {
    border: 1px solid var(--dashboard-border);
    border-radius: 10px;
    overflow: hidden;
}

.st-key-dashboard-applications-panel [data-testid="stDataFrame"] * {
    font-size: 0.78rem;
}

.st-key-dashboard-page [data-testid="stAlert"] {
    border-radius: 10px;
}

@media (max-width: 900px) {
    .st-key-dashboard-kpi-grid [data-testid="stHorizontalBlock"],
    .st-key-dashboard-charts-row [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }

    .st-key-dashboard-kpi-grid [data-testid="stColumn"] {
        flex: 1 1 calc(50% - 8px) !important;
        min-width: calc(50% - 8px) !important;
    }

    .st-key-dashboard-charts-row [data-testid="stColumn"] {
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }

    .st-key-dashboard-performance-row [data-testid="stHorizontalBlock"] {
        grid-template-columns: minmax(0, 1fr);
    }

    .st-key-dashboard-alerts-grid [data-testid="stHorizontalBlock"] {
        grid-template-columns: minmax(0, 1fr);
    }

    .st-key-dashboard-panel-repayments,
    .st-key-dashboard-panel-alerts {
        min-height: 0;
    }
}

@media (max-width: 600px) {
    .dashboard-snapshot-title {
        font-size: 1rem;
    }

    .dashboard-kpi-card {
        min-height: 132px;
        padding: 13px;
    }

    .dashboard-kpi-value {
        font-size: 1.5rem;
    }

    .st-key-dashboard-panel-portfolio,
    .st-key-dashboard-panel-risk,
    .st-key-dashboard-panel-repayments,
    .st-key-dashboard-panel-alerts,
    .st-key-dashboard-applications-panel {
        padding: 14px 12px 10px;
    }
}
</style>
"""


def _dashboard_styles(dark_mode):
    if dark_mode:
        palette = {
            "surface": "#172338",
            "text": "#F1F5F9",
            "muted": "#A7B4C5",
            "border": "#33445C",
            "subtle": "#1A2940",
            "shadow": "0 2px 8px rgba(0, 0, 0, 0.16)",
            "grid": "#33445C",
        }
    else:
        palette = {
            "surface": "#FFFFFF",
            "text": "#1E293B",
            "muted": "#64748B",
            "border": "#E2E8F0",
            "subtle": "#F8FAFC",
            "shadow": "0 2px 8px rgba(15, 23, 42, 0.035)",
            "grid": "#E8EDF4",
        }

    variables = f"""
    <style>
    .st-key-dashboard-page {{
        --dashboard-surface: {palette["surface"]};
        --dashboard-text: {palette["text"]};
        --dashboard-muted: {palette["muted"]};
        --dashboard-border: {palette["border"]};
        --dashboard-subtle: {palette["subtle"]};
        --dashboard-shadow: {palette["shadow"]};
        --dashboard-grid: {palette["grid"]};
    }}
    </style>
    """
    return variables + _DASHBOARD_CSS


def _icon_svg(icon_name):
    path = _ICON_PATHS[icon_name]
    return (
        '<svg aria-hidden="true" viewBox="0 0 24 24" '
        'xmlns="http://www.w3.org/2000/svg">'
        f"{path}</svg>"
    )


def _period_dates(period, today, custom_range):
    if period == "Last 7 days":
        start = today - timedelta(days=6)
    elif period == "Last 30 days":
        start = today - timedelta(days=29)
    elif period == "This year":
        start = today.replace(month=1, day=1)
    elif period == "Custom date range" and custom_range:
        start, end = custom_range
        return (start, end) if start <= end else (end, start)
    else:
        start = today - timedelta(days=89)
    return start, today


def _filter_date_range(frame, column, start, end):
    dates = pd.to_datetime(frame[column]).dt.date
    return frame.loc[dates.between(start, end)].copy()


def _panel_heading(title, caption):
    return f"""
    <div class="dashboard-panel-heading">
        <h3 class="dashboard-panel-title">{html.escape(title)}</h3>
        <p class="dashboard-panel-caption">{html.escape(caption)}</p>
    </div>
    """


def _kpi_card(label, value, support, icon_name, accent):
    return f"""
    <div class="dashboard-kpi-card">
        <div class="dashboard-kpi-heading">
            <span class="dashboard-kpi-icon" style="--kpi-accent:{accent}">
                {_icon_svg(icon_name)}
            </span>
            <span>{html.escape(label)}</span>
        </div>
        <div class="dashboard-kpi-value">{value:,}</div>
        <div class="dashboard-kpi-support">{html.escape(support)}</div>
    </div>
    """


def _alert_card(alert):
    colors = {
        "high": ("#B42318", "rgba(220, 38, 38, 0.1)"),
        "warning": ("#A15C00", "rgba(233, 162, 59, 0.14)"),
        "info": ("#2563EB", "rgba(37, 99, 235, 0.1)"),
    }
    color, tint = colors[alert["severity"]]
    return f"""
    <div class="dashboard-alert-card">
        <div class="dashboard-alert-topline">
            <span class="dashboard-alert-icon"
                  style="--alert-color:{color};--alert-tint:{tint}"
                  aria-hidden="true">
                {_icon_svg(alert["icon"])}
            </span>
            <div class="dashboard-alert-label">{html.escape(alert["label"])}</div>
        </div>
        <div class="dashboard-alert-caseid">{html.escape(alert["case_id"])}</div>
        <div class="dashboard-alert-title">{html.escape(alert["title"])}</div>
        <div class="dashboard-alert-description">
            {html.escape(alert["description"])}
        </div>
    </div>
    """


def _base_figure(dark_mode, margin=None):
    if dark_mode:
        text_color = "#D8E2EF"
        muted_color = "#A7B4C5"
        grid_color = "#33445C"
    else:
        text_color = "#334155"
        muted_color = "#64748B"
        grid_color = "#E8EDF4"

    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {
            "family": "Inter, Segoe UI, sans-serif",
            "color": text_color,
            "size": 11,
        },
        "hoverlabel": {
            "bgcolor": "#172338" if dark_mode else "#FFFFFF",
            "font": {"color": text_color},
            "bordercolor": grid_color,
        },
        "margin": margin or {"l": 8, "r": 8, "t": 28, "b": 8},
        "legend": {
            "orientation": "h",
            "x": 0,
            "y": 1.15,
            "font": {"color": muted_color, "size": 10},
        },
    }


def _portfolio_figure(portfolio, dark_mode):
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(
            x=portfolio["Month"],
            y=portfolio["Applications"],
            name="Applications",
            marker_color="#CBD5E1" if not dark_mode else "#47617F",
            opacity=0.75,
            hovertemplate="%{x|%b %Y}<br>%{y:,} applications<extra></extra>",
        ),
        secondary_y=True,
    )
    figure.add_trace(
        go.Scatter(
            x=portfolio["Month"],
            y=portfolio["Loan Amount"],
            name="Loan amount",
            mode="lines+markers",
            line={"color": "#2563EB" if not dark_mode else "#60A5FA", "width": 3},
            marker={"size": 7, "color": "#2563EB" if not dark_mode else "#60A5FA"},
            fill="tozeroy",
            fillcolor="rgba(37, 99, 235, 0.08)",
            hovertemplate="%{x|%b %Y}<br>$%{y:,.0f} portfolio<extra></extra>",
        ),
        secondary_y=False,
    )
    figure.update_layout(
        **_base_figure(dark_mode),
        barmode="overlay",
        height=330,
        hovermode="x unified",
    )
    figure.update_xaxes(
        title_text="Month",
        tickformat="%b %Y",
        tickangle=-25,
        showgrid=False,
        linecolor="#33445C" if dark_mode else "#E2E8F0",
    )
    figure.update_yaxes(
        title_text="Loan amount (USD)",
        tickprefix="$",
        separatethousands=True,
        showgrid=True,
        gridcolor="#33445C" if dark_mode else "#E8EDF4",
        zeroline=False,
        secondary_y=False,
    )
    figure.update_yaxes(
        title_text="Applications",
        rangemode="tozero",
        showgrid=False,
        secondary_y=True,
    )
    return figure


def _risk_figure(risk_counts, dark_mode):
    figure = go.Figure(
        go.Pie(
            labels=list(_RISK_ORDER),
            values=[int(risk_counts.get(label, 0)) for label in _RISK_ORDER],
            hole=0.66,
            sort=False,
            direction="clockwise",
            marker={"colors": list(_RISK_COLORS), "line": {"width": 2, "color": "#FFFFFF"}},
            textinfo="label+percent",
            textposition="outside",
            textfont={"size": 10},
            hovertemplate="<b>%{label}</b><br>%{value} applicants<br>%{percent}<extra></extra>",
        )
    )
    figure.update_layout(
        **_base_figure(dark_mode, margin={"l": 28, "r": 28, "t": 20, "b": 8}),
        height=330,
        showlegend=False,
        uniformtext={"minsize": 9, "mode": "hide"},
    )
    return figure


def _repayment_figure(payments, dark_mode):
    status_counts = payments["Payment Status"].value_counts()
    total = int(status_counts.sum())
    statuses = (
        ("On-time", "#16A36A"),
        ("Late", "#E9A23B"),
    )
    figure = go.Figure()
    for label, color in statuses:
        count = int(status_counts.get(label, 0))
        percentage = count / total * 100 if total else 0
        figure.add_trace(
            go.Bar(
                x=[percentage],
                y=[label],
                orientation="h",
                name=label,
                marker_color=color,
                text=[f"{percentage:.0f}%"],
                textposition="outside",
                cliponaxis=False,
                hovertemplate=f"{label}: %{{x:.1f}}% ({count} payments)<extra></extra>",
            )
        )
    figure.update_layout(
        **_base_figure(dark_mode, margin={"l": 4, "r": 42, "t": 8, "b": 30}),
        barmode="overlay",
        height=190,
        showlegend=False,
    )
    figure.update_xaxes(
        range=[0, 112],
        tickvals=[0, 25, 50, 75, 100],
        ticksuffix="%",
        title_text="Share of recorded payments",
        showgrid=True,
        gridcolor="#33445C" if dark_mode else "#E8EDF4",
        zeroline=False,
    )
    figure.update_yaxes(
        categoryorder="array",
        categoryarray=["Late", "On-time"],
        showgrid=False,
    )
    return figure


def _style_table_cell(value):
    styles = {
        "Low Risk": ("#166534", "#DCFCE7"),
        "Medium Risk": ("#92400E", "#FEF3C7"),
        "High Risk": ("#991B1B", "#FEE2E2"),
        "Approved": ("#166534", "#DCFCE7"),
        "Under review": ("#1D4ED8", "#DBEAFE"),
        "Pending": ("#92400E", "#FEF3C7"),
        "Declined": ("#475569", "#E2E8F0"),
    }
    if value not in styles:
        return ""
    color, background = styles[value]
    return f"color: {color}; background-color: {background}; font-weight: 600;"


def show_dashboard():
    today = date.today()
    demo_data = create_dashboard_demo_data(today)
    dark_mode = st.session_state.get("dark_mode", False)

    st.markdown(_dashboard_styles(dark_mode), unsafe_allow_html=True)

    with st.container(key="dashboard-page"):
        with st.container(key="dashboard-snapshot-header"):
            title_column, period_column = st.columns(
                [2.6, 1],
                vertical_alignment="center",
                gap="medium",
            )
            with title_column:
                snapshot_heading = st.empty()
            with period_column:
                period = st.selectbox(
                    "Reporting period",
                    options=(
                        "Last 7 days",
                        "Last 30 days",
                        "Last 90 days",
                        "This year",
                        "Custom date range",
                    ),
                    index=2,
                    label_visibility="collapsed",
                    key="dashboard-period",
                    width="stretch",
                )
                custom_range = None
                if period == "Custom date range":
                    selected_dates = st.date_input(
                        "Custom date range",
                        value=(today - timedelta(days=29), today),
                        format="MMM DD, YYYY",
                        key="dashboard-custom-date",
                    )
                    if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
                        custom_range = (selected_dates[0], selected_dates[1])
                reporting_period = st.empty()

        start_date, end_date = _period_dates(period, today, custom_range)
        snapshot_heading.markdown(
            """
            <h2 class="dashboard-snapshot-title">Portfolio Snapshot</h2>
            <p class="dashboard-snapshot-description">
                Key indicators for the selected reporting period
            </p>
            """,
            unsafe_allow_html=True,
        )
        reporting_period.markdown(
            f"""
            <div class="dashboard-period-caption">
                {start_date:%b %d, %Y} – {end_date:%b %d, %Y}
            </div>
            """,
            unsafe_allow_html=True,
        )

        applications = _filter_date_range(
            demo_data["applications"], "Application Date", start_date, end_date
        )
        loans_by_origin = _filter_date_range(
            demo_data["loans"], "Origination Date", start_date, end_date
        )
        overdue_loans = _filter_date_range(
            demo_data["loans"].loc[demo_data["loans"]["Payment Status"].eq("Overdue")],
            "Due Date",
            start_date,
            end_date,
        )
        payments = _filter_date_range(
            demo_data["payments"], "Payment Date", start_date, end_date
        )

        metrics = (
            (
                "Total Applications",
                len(applications),
                "Submitted in the selected period",
                "applications",
                "#2563EB",
            ),
            (
                "Active Loans",
                len(loans_by_origin.loc[loans_by_origin["Loan Status"].eq("Active")]),
                "Approved sample accounts in period",
                "loans",
                "#0F766E",
            ),
            (
                "High-Risk Applicants",
                int(applications["Risk Level"].eq("High Risk").sum()),
                "Flagged in the selected period",
                "risk",
                "#D97706",
            ),
            (
                "Overdue Loans",
                len(overdue_loans),
                "Overdue demo accounts in period",
                "overdue",
                "#DC4B4B",
            ),
        )
        with st.container(key="dashboard-kpi-grid"):
            columns = st.columns(4, gap="small")
            for column, metric in zip(columns, metrics):
                with column:
                    st.markdown(
                        _kpi_card(*metric),
                        unsafe_allow_html=True,
                    )

        st.markdown(
            """
            <div class="dashboard-section-heading">
                <div>
                    <h2 class="dashboard-section-title">Portfolio overview</h2>
                    <p class="dashboard-section-caption">
                        Monthly loan balance and application volume
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="dashboard-charts-row"):
            portfolio_column, risk_column = st.columns(
                [1.65, 1],
                gap="medium",
            )
            with portfolio_column:
                with st.container(key="dashboard-panel-portfolio"):
                    st.markdown(
                        _panel_heading(
                            "Loan portfolio trends",
                            "Monthly amount and application activity · demo data",
                        ),
                        unsafe_allow_html=True,
                    )
                    portfolio = demo_data["portfolio"]
                    month_start = date(start_date.year, start_date.month, 1)
                    month_end = date(end_date.year, end_date.month, 1)
                    portfolio_months = portfolio.loc[
                        portfolio["Month"].dt.date.between(month_start, month_end)
                    ]
                    if portfolio_months.empty:
                        st.info("No monthly sample data is available for this date range.")
                    else:
                        st.plotly_chart(
                            _portfolio_figure(portfolio_months, dark_mode),
                            width="stretch",
                            config={"displayModeBar": False, "responsive": True},
                            key="dashboard-portfolio-chart",
                        )

            with risk_column:
                with st.container(key="dashboard-panel-risk"):
                    st.markdown(
                        _panel_heading(
                            "Credit risk distribution",
                            "Applicants by sample risk category",
                        ),
                        unsafe_allow_html=True,
                    )
                    risk_counts = (
                        applications["Risk Level"]
                        .value_counts()
                        .reindex(_RISK_ORDER, fill_value=0)
                    )
                    if int(risk_counts.sum()) == 0:
                        st.info("No applicant sample data is available for this date range.")
                    else:
                        st.plotly_chart(
                            _risk_figure(risk_counts, dark_mode),
                            width="stretch",
                            config={"displayModeBar": False, "responsive": True},
                            key="dashboard-risk-chart",
                        )

        st.markdown(
            """
            <div class="dashboard-section-heading">
                <div>
                    <h2 class="dashboard-section-title">Repayment &amp; risk watch</h2>
                    <p class="dashboard-section-caption">
                        Sample payment outcomes and review reminders
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="dashboard-performance-row"):
            repayment_column, alerts_column = st.columns(
                [1, 1],
                gap="medium",
            )
            with repayment_column:
                with st.container(key="dashboard-panel-repayments"):
                    st.markdown(
                        _panel_heading(
                            "Loan repayment performance",
                            "On-time vs. late sample payments",
                        ),
                        unsafe_allow_html=True,
                    )
                    if payments.empty:
                        st.info("No payment sample data is available for this date range.")
                    else:
                        st.plotly_chart(
                            _repayment_figure(payments, dark_mode),
                            width="stretch",
                            config={"displayModeBar": False, "responsive": True},
                            key="dashboard-repayment-chart",
                        )

            with alerts_column:
                with st.container(key="dashboard-panel-alerts"):
                    st.markdown(
                        _panel_heading(
                            "Risk & repayment alerts",
                            "Cases requiring attention",
                        ),
                        unsafe_allow_html=True,
                    )
                    with st.container(key="dashboard-alerts-grid"):
                        alert_columns = st.columns(3, gap="small")
                        for column, alert in zip(alert_columns, demo_data["alerts"]):
                            with column:
                                st.markdown(
                                    _alert_card(alert),
                                    unsafe_allow_html=True,
                                )

        st.markdown(
            """
            <div class="dashboard-section-heading">
                <div>
                    <h2 class="dashboard-section-title">Recent loan applications</h2>
                    <p class="dashboard-section-caption">
                        Latest sample applications in the selected period
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="dashboard-applications-panel"):
            recent = applications.sort_values(
                "Application Date", ascending=False
            ).head(8)
            styled_recent = recent.style.map(
                _style_table_cell,
                subset=["Risk Level", "Status"],
            )
            st.dataframe(
                styled_recent,
                column_config={
                    "Application ID": st.column_config.TextColumn(
                        "Application ID",
                        width="small",
                    ),
                    "Applicant": st.column_config.TextColumn(
                        "Applicant",
                        width="medium",
                    ),
                    "Application Date": st.column_config.DateColumn(
                        "Application date",
                        format="MMM DD, YYYY",
                    ),
                    "Loan Amount": st.column_config.NumberColumn(
                        "Loan amount",
                        format="$%,.0f",
                    ),
                    "Risk Level": st.column_config.TextColumn("Risk level"),
                    "Status": st.column_config.TextColumn("Status"),
                },
                hide_index=True,
                height=340,
                width="stretch",
            )

        st.caption(
            "Demonstration dashboard only. All figures, applicants, accounts, "
            "and alerts are illustrative sample data and are not connected to "
            "a live banking system."
        )
