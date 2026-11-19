"""Read-only portfolio analytics over the application's shared session records."""
from __future__ import annotations

import html
import io
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

import pandas as pd
import plotly.express as px
import streamlit as st

from data.loan_applications_demo import create_loan_application_demo_data
from modules.loan_application import latest_risk_summary
from modules.loan_monitoring import (
    APPLICATIONS_KEY, _eligible, _monitor, _disbursement, _decimal, _date,
    _outstanding_principal, _overdue_rows, _payment_allocation_total,
    account_monitoring_row, build_loan_overview,
)
from modules.debt_analysis import (
    OBLIGATION_COLLECTIONS, _borrower_type as _debt_borrower_type,
    calculate_obligations_summary, normalize_monthly_amount,
)

_RISK = ("Low", "Medium", "High", "Not Assessed")
_BLUE = "#2563EB"
_RISK_COLOR = {"Low": "#16A34A", "Medium": "#F59E0B", "High": "#DC2626", "Not Assessed": "#94A3B8"}

# Compact chart sizing keeps comparable charts aligned within a row.
_CHART_STANDARD = 300
_CHART_PIE = 280
_CHART_SMALL = 260

_ANALYTICS_CSS = """
<style>
    /* Analytics-only spacing: tighter rows and card padding, unchanged global theme. */
    .st-key-ba-analytics [data-testid="stHorizontalBlock"] { gap: 14px; align-items: flex-start; }
    .st-key-ba-analytics [data-testid="stMarkdownContainer"],
    .st-key-ba-analytics [data-testid="stCaptionContainer"] { margin-bottom: 0; }
    .st-key-ba-analytics [data-testid="stMarkdownContainer"] h4 { padding: 0.125rem 0 0.375rem; }
    .st-key-ba-analytics [data-testid="stPlotlyChart"] { margin-bottom: -6px; }
    .st-key-ba-analytics .ba-empty-state { align-items: center; background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 10px; color: #64748B; display: flex; font-size: 0.8rem; justify-content: center; line-height: 1.5; padding: 12px 18px; text-align: center; }
    @media (max-width: 760px) {
        /* Stack paired charts on phones so labels stay readable without horizontal overflow. */
        .st-key-ba-analytics [data-testid="stHorizontalBlock"] { flex-direction: column; gap: 10px; }
        .st-key-ba-analytics [data-testid="stColumn"] { flex: 1 1 100% !important; min-width: 0 !important; width: 100% !important; }
    }
</style>
"""


def _records() -> list[dict[str, Any]]:
    # Match the shared application's normal initialization when this page is opened directly.
    if APPLICATIONS_KEY not in st.session_state:
        st.session_state[APPLICATIONS_KEY] = create_loan_application_demo_data()
    value = st.session_state.get(APPLICATIONS_KEY)
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        result = float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
    return result if pd.notna(result) and result >= 0 else None


def _borrower_type(record: Mapping[str, Any]) -> str:
    value = _debt_borrower_type(record)
    if value != "Not specified":
        return value
    analysis = record.get("financial_analysis", {})
    value = analysis.get("borrower_type") if isinstance(analysis, Mapping) else None
    return value if value in {"Personal", "Business"} else "Not specified"


def _risk(record: Mapping[str, Any]) -> str:
    value = latest_risk_summary(record)
    normalized = str(value or "Not Assessed").strip().casefold()
    for category in _RISK[:3]:
        if normalized == category.casefold() or normalized.startswith(category.casefold() + " "):
            return category
    return "Not Assessed"


def _status(record: Mapping[str, Any]) -> str:
    decision = record.get("final_lending_decision")
    if isinstance(decision, Mapping) and decision.get("status"):
        return str(decision["status"])
    return "Not recorded"


def _application_id(record: Mapping[str, Any]) -> str:
    return str(record.get("application_id") or "")


def _dedupe_applications(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Do not double count duplicate application IDs; preserve ID-less rows individually."""
    seen: set[str] = set()
    result = []
    for record in records:
        application_id = _application_id(record).strip().casefold()
        if application_id and application_id in seen:
            continue
        if application_id:
            seen.add(application_id)
        result.append(record)
    return result


def _in_period(value: Any, start: date | None, end: date | None) -> bool:
    parsed = _date(value)
    if start is None and end is None:
        return True
    return parsed is not None and (start is None or parsed >= start) and (end is None or parsed <= end)


def _date_period() -> tuple[date | None, date | None]:
    today = date.today()
    choice = st.selectbox("Reporting period", ["All Time", "This Month", "Last Month", "Last 3 Months", "Last 6 Months", "This Year", "Last Year", "Custom Date Range"], key="ba-period")
    if choice == "All Time":
        return None, None
    if choice == "Custom Date Range":
        selected = st.date_input("Custom reporting dates", value=(), key="ba-custom-period")
        if isinstance(selected, (tuple, list)) and len(selected) == 2:
            if selected[0] > selected[1]:
                st.error("The start date must be on or before the end date.")
                return date.max, date.min
            return selected[0], selected[1]
        st.caption("Choose both a start and end date to apply the custom range.")
        return None, None
    month_start = today.replace(day=1)
    if choice == "This Month":
        return month_start, today
    if choice == "Last Month":
        end = month_start - timedelta(days=1)
        return end.replace(day=1), end
    if choice in {"Last 3 Months", "Last 6 Months"}:
        months = 3 if choice.startswith("Last 3") else 6
        month_index = month_start.month - months
        year = month_start.year + (month_index - 1) // 12
        month = (month_index - 1) % 12 + 1
        return date(year, month, 1), today
    if choice == "This Year":
        return date(today.year, 1, 1), today
    return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)


def _global_filters(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], date | None, date | None, dict[str, str]]:
    st.markdown("### Global filters")
    c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1.3, 1.3, .65])
    with c1:
        start, end = _date_period()
    with c2:
        borrower = st.selectbox("Borrower type", ["All", "Personal", "Business", "Not specified"], key="ba-borrower")
    purposes = sorted({str(r.get("loan_purpose") or r.get("purpose")) for r in records if r.get("loan_purpose") or r.get("purpose")})
    with c3:
        purpose = st.selectbox("Loan purpose", ["All"] + purposes, key="ba-purpose")
    statuses = sorted({f"Application · {r.get('status')}" for r in records if r.get("status")} | {f"Decision · {r.get('final_lending_decision', {}).get('status')}" for r in records if isinstance(r.get("final_lending_decision"), Mapping) and r["final_lending_decision"].get("status")} | {f"Loan · {_monitor(r).get('account_status')}" for r in records if _monitor(r).get("account_status")})
    with c4:
        status = st.selectbox("Application / loan status", ["All"] + statuses, key="ba-status")
    with c5:
        if st.button("Reset", key="ba-reset-filters", width="stretch"):
            for key in ("ba-period", "ba-custom-period", "ba-borrower", "ba-purpose", "ba-status", "ba-risk", "ba-grouping", "ba-report-type"):
                st.session_state.pop(key, None)
            st.rerun()
    risk = st.selectbox("Credit risk category", ["All", *_RISK], key="ba-risk", label_visibility="collapsed")
    st.caption("Dates apply to each measure's own event date: application date, disbursement date, or payment date. Status options identify their source.")
    filtered_apps = []
    for record in records:
        app_date = record.get("application_date")
        app_status_matches = status == "All" or not status.startswith("Application ·") or str(record.get("status")) == status.split("·", 1)[1].strip()
        decision_matches = status == "All" or not status.startswith("Decision ·") or _status(record) == status.split("·", 1)[1].strip()
        if not _in_period(app_date, start, end) or borrower != "All" and _borrower_type(record) != borrower or purpose != "All" and (record.get("loan_purpose") or record.get("purpose")) != purpose or risk != "All" and _risk(record) != risk or not app_status_matches or not decision_matches:
            continue
        filtered_apps.append(record)
    accounts = _eligible(records)
    filtered_accounts = []
    for record in accounts:
        disb = _disbursement(record)
        loan_status_matches = status == "All" or not status.startswith("Loan ·") or str(_monitor(record).get("account_status")) == status.split("·", 1)[1].strip()
        if borrower != "All" and _borrower_type(record) != borrower or purpose != "All" and (record.get("loan_purpose") or record.get("purpose")) != purpose or risk != "All" and _risk(record) != risk or not loan_status_matches:
            continue
        filtered_accounts.append(record)
    return filtered_apps, filtered_accounts, start, end, {"Borrower": borrower, "Purpose": purpose, "Status": status, "Risk": risk}


def _period_accounts(accounts: Sequence[dict[str, Any]], start: date | None, end: date | None) -> list[dict[str, Any]]:
    """Disbursement-event cohort; other metrics apply the period to their own event date."""
    return [r for r in accounts if _in_period(_disbursement(r).get("disbursed_at"), start, end)]


def _fmt(value: Any, currency: str | None = None, precision: int = 2) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, (int, float)) and pd.notna(value):
        return f"{currency} {value:,.{precision}f}" if currency else f"{value:,.{precision}f}"
    return str(value)


def _common_currency(records: Sequence[dict[str, Any]]) -> str | None:
    values = {str(_disbursement(r).get("currency") or "").strip().upper() for r in records}
    return next(iter(values)) if len(values) == 1 and "" not in values else None


def _kpis(items: Sequence[tuple[str, str, str]]) -> None:
    for offset in range(0, len(items), 3):
        cols = st.columns(min(3, len(items) - offset))
        for col, (label, value, help_text) in zip(cols, items[offset:offset + 3]):
            with col:
                st.metric(label, value, help=help_text)


def _chart_empty(message: str, height: int = _CHART_SMALL) -> None:
    """Compact empty state sized to balance the chart beside it."""
    st.markdown(
        f"<div class='ba-empty-state' style='min-height:{max(120, height - 46)}px'>{html.escape(message)}</div>",
        unsafe_allow_html=True,
    )


def _plot(chart: Any, key: str, height: int = _CHART_STANDARD) -> None:
    """Render a figure at a compact, uniform height with tight, consistent spacing."""
    has_title = bool(chart.layout.title.text)
    chart.update_layout(
        height=height,
        autosize=True,
        margin=dict(l=4, r=4, t=46 if has_title else 34, b=4),
        title=dict(font=dict(size=13), x=0, xanchor="left"),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=10.5), title=None),
        font=dict(size=11),
    )
    chart.update_xaxes(automargin=True, title_standoff=8, tickfont=dict(size=10.5), title_font=dict(size=11))
    chart.update_yaxes(automargin=True, title_standoff=8, tickfont=dict(size=10.5), title_font=dict(size=11))
    st.plotly_chart(chart, width="stretch", key=f"ba-chart-{key}")


def _app_frame(records: Sequence[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for r in records:
        requested = _num(r.get("loan_amount"))
        term = _num(r.get("loan_term_months"))
        rows.append({
            "Application ID": _application_id(r) or "Not available",
            "Borrower": _application_id(r) or "Anonymized application record",
            "Borrower Type": _borrower_type(r), "Loan Purpose": r.get("loan_purpose") or r.get("purpose") or "Not specified",
            "Requested Amount": requested, "Currency": str(r.get("currency") or "Not specified").upper(), "Application Date": _date(r.get("application_date")),
            "Application Status": r.get("status") or "Not specified", "Final Decision": _status(r),
            "Credit Risk": _risk(r), "Term (months)": term,
        })
    return pd.DataFrame(rows)


def _loan_rows(records: Sequence[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    today = date.today()
    for record in records:
        source = account_monitoring_row(record, today)
        rows.append({"Loan Account ID": source["Loan Account ID"], "Application ID": source["Application ID"], "Borrower Ref": source["Application ID"], "Borrower Type": _borrower_type(record), "Loan Purpose": source["Loan Purpose"], "Currency": source["Currency"], "Disbursed Amount": source["Disbursed Amount"], "Outstanding Balance": source["Outstanding Balance"], "Loan Status": source["Loan Status"], "Disbursement Date": source["Disbursement Date"], "Overdue Amount": source["Overdue Amount"], "Days Past Due": source["Days Past Due"], "Credit Risk": _risk(record)})
    return pd.DataFrame(rows)


def calculate_par(accounts: Sequence[dict[str, Any]], today: date, threshold_days: int) -> float | None:
    """Current PAR from unique loan principal balances; unknown schedules/balances stay unavailable."""
    eligible = _eligible(accounts)
    if not eligible or _common_currency(eligible) is None:
        return None
    balances = [_outstanding_principal(record) for record in eligible]
    if any(value is None for value in balances):
        return None
    denominator = sum((value for value in balances if value is not None), Decimal(0))
    if denominator <= 0:
        return None
    numerator = Decimal(0)
    for record, balance in zip(eligible, balances):
        overdue, complete = _overdue_rows(record, today)
        if not complete:
            return None
        if any(row["days_past_due"] > threshold_days for row in overdue):
            numerator += balance or Decimal(0)
    return float(numerator / denominator * 100)


def _application_trend(apps: Sequence[dict[str, Any]], grouping: str) -> pd.DataFrame:
    values = []
    for record in apps:
        day = _date(record.get("application_date"))
        if day:
            values.append({"Period": day.strftime("%Y" if grouping == "Yearly" else "%Y-%m"), "Application Count": 1, "Requested Amount": _num(record.get("loan_amount")), "Currency": str(record.get("currency") or "Not specified").upper()})
    if not values:
        return pd.DataFrame()
    return pd.DataFrame(values).groupby(["Period", "Currency"], as_index=False).agg({"Application Count": "sum", "Requested Amount": lambda x: x.sum(min_count=1)})


def _disbursement_trend(accounts: Sequence[dict[str, Any]], grouping: str) -> pd.DataFrame:
    rows = []
    for r in accounts:
        disb = _disbursement(r)
        day, amount = _date(disb.get("disbursed_at")), _num(disb.get("disbursed_amount"))
        if day and amount is not None:
            rows.append({"Period": day.strftime("%Y" if grouping == "Yearly" else "%Y-%m"), "Disbursed Amount": amount, "Disbursed Loans": 1, "Currency": str(disb.get("currency") or "").upper()})
    return pd.DataFrame(rows).groupby(["Period", "Currency"], as_index=False).agg({"Disbursed Amount": "sum", "Disbursed Loans": "sum"}) if rows else pd.DataFrame()


def _portfolio_overview(apps: list[dict[str, Any]], accounts: list[dict[str, Any]], start: date | None, end: date | None, flags: Mapping[str, str]) -> None:
    st.markdown("### Portfolio Overview")
    disbursement_cohort = _period_accounts(accounts, start, end)
    currency = _common_currency(accounts)
    summary = build_loan_overview(accounts, today=date.today())
    disb_summary = build_loan_overview(disbursement_cohort, today=date.today())
    actual_decisions = [r for r in apps if isinstance(r.get("final_lending_decision"), Mapping) and str(r["final_lending_decision"].get("status", "")).casefold() == "approved"]
    _kpis([
        ("Loan Applications", f"{len(apps):,}", "Unique application IDs; application-date cohort"),
        ("Approved Applications", f"{len(actual_decisions):,}", "Explicit final_lending_decision status only"),
        ("Total Disbursed Amount", _fmt(disb_summary["disbursed_total"], disb_summary["disbursed_currency"]), "Actual eligible disbursements in selected disbursement-date cohort"),
        ("Outstanding Loan Balance", _fmt(summary["outstanding_total"], summary["outstanding_currency"]), "Loan Monitoring principal calculation"),
        ("Active Loans", str(len(summary["active"])), "Explicitly disbursed Active accounts"),
        ("Overdue Loans", str(len(summary["overdue_accounts"])) if summary["overdue_accounts"] is not None else "Not available", "Needs complete actual repayment schedules"),
    ])
    st.caption("Previous-period comparisons are not shown for these event cohorts when reliable equivalent historical periods are not available.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Application trend")
        grouping = st.selectbox("Application grouping", ["Monthly", "Yearly"], key="ba-grouping")
        trend = _application_trend(apps, grouping)
        if not trend.empty:
            _plot(px.line(trend.groupby("Period", as_index=False)["Application Count"].sum(), x="Period", y="Application Count", markers=True, color_discrete_sequence=[_BLUE]), "application-trend")
            currencies = set(trend.Currency)
            st.markdown("Requested loan amounts by application date")
            if len(currencies) == 1 and "NOT SPECIFIED" not in currencies:
                _plot(px.line(trend, x="Period", y="Requested Amount", markers=True, color_discrete_sequence=["#0F766E"], title=f"Requested amount ({next(iter(currencies))})"), "requested-amount-trend", height=_CHART_SMALL)
            else:
                st.dataframe(trend[["Period", "Currency", "Requested Amount"]], hide_index=True, width="stretch")
                st.caption("Requested amounts are not combined because the application currency is missing or mixed.")
        else:
            _chart_empty("No dated application records match these filters. Application Date is required for the trend.")
    with c2:
        st.markdown("#### Actual disbursement trend")
        trend = _disbursement_trend(disbursement_cohort, grouping)
        if not trend.empty:
            if trend.Currency.nunique() == 1:
                _plot(px.bar(trend, x="Period", y="Disbursed Amount", color_discrete_sequence=[_BLUE], hover_data=["Disbursed Loans"]), "disbursement-trend")
            else:
                st.dataframe(trend, hide_index=True, width="stretch")
        else:
            _chart_empty("No actual dated disbursements match these filters. Application or approval dates are not used as substitutes.")
    if apps:
        frame = _app_frame(apps)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Borrower classification")
            _plot(px.pie(frame, names="Borrower Type", hole=.55, color_discrete_sequence=[_BLUE, "#0F766E", "#94A3B8"]), "portfolio-borrower-type", height=_CHART_PIE)
        with c2:
            st.markdown("#### Application purposes")
            purpose = frame.groupby("Loan Purpose", as_index=False).size()
            _plot(px.bar(purpose, x="Loan Purpose", y="size", color_discrete_sequence=[_BLUE]), "portfolio-purpose", height=_CHART_PIE)
        values = [v for v in frame["Requested Amount"] if v is not None]
        requested_currencies = set(frame.loc[frame["Requested Amount"].notna(), "Currency"])
        amount_distribution_ok = bool(values) and len(requested_currencies) == 1 and "Not specified" not in requested_currencies
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Application status")
            status = frame.groupby("Application Status", as_index=False).size()
            _plot(px.pie(status, names="Application Status", hole=.55), "portfolio-status", height=_CHART_PIE)
        with c2:
            if amount_distribution_ok:
                st.markdown("#### Requested loan amount distribution (application-level)")
                _plot(px.histogram(frame.dropna(subset=["Requested Amount"]), x="Requested Amount", nbins=min(10, max(3, len(values))), color_discrete_sequence=[_BLUE]), "requested-amount", height=_CHART_PIE)
            else:
                st.markdown("#### Requested loan amount distribution (application-level)")
                _chart_empty("Requested amount distribution is not combined because application currency is missing or mixed.", height=_CHART_PIE)
        insights = []
        if len(apps):
            borrower_counts = frame["Borrower Type"].value_counts()
            if len(borrower_counts): insights.append(f"Most applications are classified as {borrower_counts.index[0]} ({borrower_counts.iloc[0]} of {len(frame)}).")
            purpose_counts = frame["Loan Purpose"].value_counts()
            if len(purpose_counts): insights.append(f"Most common recorded purpose: {purpose_counts.index[0]} ({purpose_counts.iloc[0]} applications).")
            dated = frame.dropna(subset=["Application Date"])
            if not dated.empty:
                top_period = dated.assign(Period=dated["Application Date"].map(lambda d: d.strftime("%Y-%m"))).groupby("Period").size().sort_values(ascending=False)
                if len(top_period): insights.append(f"Highest application month in the selected cohort: {top_period.index[0]} ({top_period.iloc[0]} applications).")
        if insights:
            st.markdown("#### Evidence-based portfolio observations")
            for item in insights: st.write(f"• {item}")
    else:
        st.info("No applications match the selected filters. Review the period, borrower type, purpose, status, or risk filters.")
    if not accounts:
        st.info("No eligible disbursed loan records match these filters. Check Loan Monitoring for explicitly recorded disbursements; approved applications are not active loans.")
    elif not disbursement_cohort:
        st.info("No disbursed records fall within the selected reporting period. Current active and outstanding balance KPIs use all matching accounts because historical balance snapshots are not stored.")
    if summary["outstanding_total"] is None:
        st.caption("Outstanding amount is unavailable when eligible balances are missing or account currencies are mixed.")


def _loan_portfolio_analysis(apps: list[dict[str, Any]], accounts: list[dict[str, Any]]) -> None:
    st.markdown("### Loan Portfolio Analysis")
    app_frame, loan_frame = _app_frame(apps), _loan_rows(accounts)
    if not app_frame.empty:
        st.markdown("#### Application-level analysis by borrower type")
        rows = []
        for (group, currency), part in app_frame.groupby(["Borrower Type", "Currency"]):
            amounts = part["Requested Amount"].dropna()
            currency_known = currency != "Not specified"
            rows.append({"Borrower Type": group, "Currency": currency, "Applications": len(part), "Requested Amount Total": amounts.sum() if len(amounts) and currency_known else None, "Average Requested Amount": amounts.mean() if len(amounts) and currency_known else None, "Median Requested Amount": amounts.median() if len(amounts) and currency_known else None, "Approved Applications": int((part["Final Decision"].str.casefold() == "approved").sum())})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if not loan_frame.empty:
            actual_rows = []
            for (borrower_type, account_currency), part in loan_frame.groupby(["Borrower Type", "Currency"]):
                amounts = pd.to_numeric(part["Disbursed Amount"], errors="coerce")
                balances = pd.to_numeric(part["Outstanding Balance"], errors="coerce")
                actual_rows.append({"Borrower Type": borrower_type, "Disbursed loans": len(part), "Disbursed amount": amounts.sum(min_count=1), "Outstanding balance": balances.sum(min_count=1), "Currency": account_currency})
            st.markdown("#### Actual disbursement and current balance by borrower type")
            st.dataframe(pd.DataFrame(actual_rows), hide_index=True, width="stretch")
        p1, p2 = st.columns(2)
        by_purpose = app_frame.groupby(["Loan Purpose", "Currency"], as_index=False).agg(Applications=("Application ID", "count"), Requested=("Requested Amount", lambda s: s.sum(min_count=1)), Average=("Requested Amount", "mean"))
        by_purpose.loc[by_purpose["Currency"] == "Not specified", ["Requested", "Average"]] = None
        decisions = app_frame[app_frame["Final Decision"].str.casefold() == "approved"].groupby(["Loan Purpose", "Currency"]).size()
        by_purpose["Approved applications"] = [int(decisions.get((purpose, currency), 0)) for purpose, currency in zip(by_purpose["Loan Purpose"], by_purpose["Currency"])]
        if not loan_frame.empty:
            actual_purpose = loan_frame.groupby(["Loan Purpose", "Currency"], as_index=False).agg(**{"Disbursed loans": ("Loan Account ID", "nunique"), "Disbursed amount": ("Disbursed Amount", "sum")})
            by_purpose = by_purpose.merge(actual_purpose, on=["Loan Purpose", "Currency"], how="left")
        st.dataframe(by_purpose, hide_index=True, width="stretch")
        with p1:
            st.markdown("#### Applications and requested amount by purpose")
            app_counts = app_frame.groupby("Loan Purpose", as_index=False).size().rename(columns={"size": "Applications"})
            _plot(px.bar(app_counts, x="Loan Purpose", y="Applications", color_discrete_sequence=[_BLUE]), "analysis-purpose-count", height=_CHART_PIE)
            requested = by_purpose[(by_purpose["Currency"] != "Not specified") & by_purpose["Requested"].notna()]
            if not requested.empty:
                _plot(px.bar(requested, x="Loan Purpose", y="Requested", color="Currency", barmode="group"), "analysis-purpose-amount", height=_CHART_PIE)
            else:
                _chart_empty("Requested amount by purpose is unavailable until application currency is recorded.", height=_CHART_SMALL)
        with p2:
            terms = app_frame.dropna(subset=["Term (months)"])
            st.markdown("#### Loan term distribution")
            if not terms.empty:
                st.caption(f"Mean term: {terms['Term (months)'].mean():.1f} months across {len(terms)} records with a term.")
                _plot(px.histogram(terms, x="Term (months)", color="Borrower Type", nbins=min(10, max(3, len(terms)))), "term-distribution", height=_CHART_PIE)
            else: _chart_empty("Loan term is not recorded on matching applications.", height=_CHART_PIE)
        st.markdown("#### Application statuses")
        st.dataframe(app_frame.groupby("Application Status", as_index=False).size().rename(columns={"size": "Applications"}), hide_index=True, width="stretch")
        known_currencies = set(app_frame.loc[app_frame["Requested Amount"].notna(), "Currency"])
        valid_amounts = app_frame["Requested Amount"].dropna()
        if len(valid_amounts) and len(known_currencies) == 1 and "Not specified" not in known_currencies:
            st.markdown("#### Requested amount summary and descriptive ranges")
            amount_summary = pd.DataFrame([{"Minimum": valid_amounts.min(), "Maximum": valid_amounts.max(), "Mean": valid_amounts.mean(), "Median": valid_amounts.median(), "Range basis": "Quantile groups, descriptive only (not official bank categories)"}])
            amount_summary["Currency"] = next(iter(known_currencies))
            st.dataframe(amount_summary, hide_index=True, width="stretch")
            try:
                ranges = pd.qcut(valid_amounts, q=min(4, len(valid_amounts)), duplicates="drop").astype(str).value_counts().sort_index().rename_axis("Requested amount range").reset_index(name="Applications")
                st.dataframe(ranges, hide_index=True, width="stretch")
            except ValueError:
                _chart_empty("Amount ranges cannot be divided because the available amounts do not vary.")
        elif len(valid_amounts):
            st.info("Minimum, maximum, average and median amounts are not combined because the currency is missing or mixed.")
        if not app_frame.dropna(subset=["Term (months)"]).empty:
            terms_by_group = app_frame.dropna(subset=["Term (months)"]).groupby(["Borrower Type", "Loan Purpose"], as_index=False).agg(Applications=("Application ID", "count"), **{"Average term (months)": ("Term (months)", "mean")})
            st.markdown("#### Term by borrower type and purpose")
            st.dataframe(terms_by_group, hide_index=True, width="stretch")
    else:
        st.info("No applications match the selected filters.")
    st.markdown("#### Disbursed accounts (separate from application figures)")
    if loan_frame.empty:
        st.info("No eligible disbursed accounts match these filters. Outstanding and actual disbursed amounts therefore remain unavailable.")
    else:
        st.dataframe(loan_frame, hide_index=True, width="stretch")
        st.markdown("#### Loan account status")
        _plot(px.pie(loan_frame, names="Loan Status", hole=.55), "loan-account-status", height=_CHART_PIE)
    st.markdown("#### Analytical application table")
    if app_frame.empty: st.info("No application records to display.")
    else:
        query = st.text_input("Search applications by ID or borrower", key="ba-table-search").casefold()
        shown = app_frame if not query else app_frame[app_frame.apply(lambda row: query in str(row["Application ID"]).casefold() or query in str(row["Borrower"]).casefold(), axis=1)]
        st.dataframe(shown, hide_index=True, width="stretch")


def _credit_risk_analytics(apps: list[dict[str, Any]], accounts: list[dict[str, Any]]) -> None:
    st.markdown("### Credit Risk Analytics")
    st.caption("Risk categories use a stored latest risk summary or the legacy application risk label. Credit Assessment currently tracks review progress but does not store a comparable analyst risk score/category; source labels are not ML predictions.")
    if not apps:
        st.info("No applications match the selected filters.")
        return
    frame = _app_frame(apps)
    distribution = frame.groupby("Credit Risk", as_index=False).agg(Applications=("Application ID", "count"))
    distribution = distribution.set_index("Credit Risk").reindex(_RISK, fill_value=0).rename_axis("Credit Risk").reset_index()
    total = len(frame)
    assessed = int(frame["Credit Risk"].isin(_RISK[:3]).sum())
    distribution["Share of assessed applications (%)"] = distribution.apply(lambda r: (r["Applications"] / assessed * 100) if r["Credit Risk"] != "Not Assessed" and assessed else None, axis=1)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Risk distribution")
        st.caption(f"Percentages use assessed applications only ({assessed}); not-assessed applications are excluded from the denominator. Total applications in cohort: {total}.")
        _plot(px.bar(distribution, x="Credit Risk", y="Applications", color="Credit Risk", color_discrete_map=_RISK_COLOR), "risk-distribution", height=_CHART_STANDARD)
        st.dataframe(distribution, hide_index=True, width="stretch")
        amount_by_risk = frame.groupby(["Credit Risk", "Currency"], as_index=False).agg(**{"Applications": ("Application ID", "count"), "Requested amount": ("Requested Amount", lambda s: s.sum(min_count=1))})
        amount_by_risk.loc[amount_by_risk["Currency"] == "Not specified", "Requested amount"] = None
        st.markdown("Requested amount by risk and currency (not combined across currencies)")
        st.dataframe(amount_by_risk, hide_index=True, width="stretch")
    with c2:
        st.markdown("#### Risk by borrower type and purpose")
        group = frame.groupby(["Borrower Type", "Credit Risk"], as_index=False).size()
        _plot(px.bar(group, x="Borrower Type", y="size", color="Credit Risk", barmode="group", color_discrete_map=_RISK_COLOR), "risk-by-type", height=_CHART_STANDARD)
        purpose = frame.groupby(["Loan Purpose", "Credit Risk"], as_index=False).size()
        _plot(px.bar(purpose, x="Loan Purpose", y="size", color="Credit Risk", barmode="stack", color_discrete_map=_RISK_COLOR), "risk-by-purpose", height=_CHART_STANDARD)
    indicators = []
    for r in apps:
        analysis = r.get("financial_analysis", {})
        capacity_root = analysis.get("repayment_capacity", {}) if isinstance(analysis, Mapping) else {}
        if not isinstance(capacity_root, Mapping): continue
        for kind in ("personal", "business"):
            metrics = capacity_root.get(kind, {})
            if not isinstance(metrics, Mapping): continue
            metric_names = {"personal": ["dti_percent", "dsti_percent"], "business": ["dscr"]}[kind]
            for name in metric_names:
                value = _num(metrics.get(name))
                if value is not None:
                    indicators.append({"Borrower Type": kind.title(), "Metric": name.upper().replace("_PERCENT", ""), "Value": value, "Risk": _risk(r)})
    st.markdown("#### Available financial-analysis indicators by stored risk classification")
    if indicators:
        indicator_frame = pd.DataFrame(indicators)
        st.caption("Associations are descriptive only and do not imply causation. Personal DTI/DSTI and business DSCR remain separate.")
        _plot(px.box(indicator_frame, x="Risk", y="Value", color="Risk", facet_col="Metric", color_discrete_map=_RISK_COLOR, points="all"), "financial-risk-indicators", height=_CHART_STANDARD)
    else:
        st.info("No saved Part 4 DTI, DSTI, or DSCR values match these applications. Missing financial metrics are not treated as zero.")
    outcome = []
    for r in accounts:
        monitoring = _monitor(r)
        schedule = monitoring.get("repayment_schedule", [])
        payments = monitoring.get("payments", [])
        if schedule and payments:
            overdue, complete = _overdue_rows(r, date.today())
            if complete:
                outcome.append({"Credit Risk": _risk(r), "Loan Account ID": monitoring.get("loan_account_id"), "Observed overdue": bool(overdue)})
    st.markdown("#### Assessed risk vs observed repayment outcomes")
    if outcome:
        outcome_frame = pd.DataFrame(outcome)
        st.caption(f"Observed account sample: {len(outcome_frame)} with schedule and payment history. This is not model validation or predictive accuracy.")
        st.dataframe(outcome_frame.groupby("Credit Risk", as_index=False).agg(Accounts=("Loan Account ID", "nunique"), Accounts_With_Observed_Overdue=("Observed overdue", "sum")), hide_index=True, width="stretch")
    else:
        st.info("Insufficient data: assessed risk must be linked to disbursed accounts with actual repayment schedules and payment history. Rejected applications are not defaults.")


def _repayment_analytics(accounts: list[dict[str, Any]], start: date | None, end: date | None) -> None:
    st.markdown("### Repayment & Delinquency Analytics")
    overview = build_loan_overview(accounts, date.today())
    total_installments = paid_installments = unpaid_installments = None
    schedule_rows, payment_rows, delinquency_rows = [], [], []
    schedules_complete = bool(accounts)
    for record in accounts:
        schedule = _monitor(record).get("repayment_schedule", [])
        if not isinstance(schedule, list) or not schedule:
            schedules_complete = False
            continue
        for row in schedule:
            if not isinstance(row, Mapping):
                schedules_complete = False; continue
            due_date, due, paid = _date(row.get("due_date")), _num(row.get("amount_due")), _num(row.get("amount_paid"))
            if due_date is None or due is None or paid is None or paid > due:
                schedules_complete = False; continue
            if not _in_period(due_date, start, end):
                continue
            state = "Paid" if paid >= due else "Unpaid"
            schedule_rows.append({"Due Date": due_date, "Amount Due": due, "Amount Paid": paid, "Status": state, "Currency": row.get("currency") or _disbursement(record).get("currency"), "Borrower Type": _borrower_type(record), "Purpose": record.get("loan_purpose") or record.get("purpose") or "Not specified"})
        for payment in _monitor(record).get("payments", []):
            if not isinstance(payment, Mapping): continue
            day, amount = _date(payment.get("payment_date")), _num(payment.get("amount_received"))
            if day and amount is not None and _in_period(day, start, end):
                due_day = _date(payment.get("due_date"))
                payment_rows.append({"Payment Date": day, "Amount": amount, "Currency": payment.get("currency") or _disbursement(record).get("currency"), "Timing": "On time" if due_day and day <= due_day else "Late" if due_day else "Unlinked", "Borrower Type": _borrower_type(record), "Purpose": record.get("loan_purpose") or record.get("purpose") or "Not specified"})
            overdue, complete = _overdue_rows(record, date.today())
        if not complete: schedules_complete = False
        for row in overdue:
            if not _in_period(row.get("due_date"), start, end):
                continue
            days = row["days_past_due"]
            delinquency_rows.append({"Loan Account ID": _monitor(record).get("loan_account_id"), "Aging": "1–30 Days" if days <= 30 else "31–60 Days" if days <= 60 else "61–90 Days" if days <= 90 else "More than 90 Days", "Overdue Amount": float(row["remaining_amount"]), "Outstanding Balance": _outstanding_principal(record), "Days Past Due": days, "Borrower Type": _borrower_type(record), "Purpose": record.get("loan_purpose") or record.get("purpose") or "Not specified", "Currency": _disbursement(record).get("currency")})
    if schedules_complete and schedule_rows:
        total_installments = len(schedule_rows)
        paid_installments = sum(r["Status"] == "Paid" for r in schedule_rows)
        unpaid_installments = total_installments - paid_installments
    on_time = [p for p in payment_rows if p["Timing"] in {"On time", "Late"}]
    on_time_rate = sum(p["Timing"] == "On time" for p in on_time) / len(on_time) * 100 if on_time else None
    late_rate = sum(p["Timing"] == "Late" for p in on_time) / len(on_time) * 100 if on_time else None
    overdue_currencies = {str(r["Currency"]).upper() for r in delinquency_rows if r["Currency"]}
    overdue_amount = sum(r["Overdue Amount"] for r in delinquency_rows) if delinquency_rows and len(overdue_currencies) == 1 and all(r["Currency"] for r in delinquency_rows) else 0 if schedules_complete else None
    _kpis([
        ("Scheduled installments", str(total_installments) if total_installments is not None else "Not available", "Schedule rows with due date, amount, payment, within selected due-date period"),
        ("Paid installments", str(paid_installments) if paid_installments is not None else "Not available", "Paid scheduled rows"),
        ("Unpaid installments", str(unpaid_installments) if unpaid_installments is not None else "Not available", "Includes future due dates; not all are overdue"),
        ("On-time payment rate", f"{on_time_rate:.1f}%" if on_time_rate is not None else "Not available", "Dated transactions linked to a due date"),
        ("Late payment rate", f"{late_rate:.1f}%" if late_rate is not None else "Not available", "Same linked transaction denominator as on-time rate"),
        ("Total overdue amount", _fmt(overdue_amount, next(iter(overdue_currencies)) if len(overdue_currencies) == 1 else None), "Unpaid installments due in the selected schedule period; DPD is calculated as of today"),
    ])
    if not accounts:
        st.info("No eligible disbursed loan accounts match these filters. Repayment, delinquency, and PAR metrics need records from Loan Monitoring.")
    elif not schedules_complete:
        st.info("Some loan schedules are missing or incomplete. Scheduled-installment and delinquency totals may be unavailable; add or reconcile schedules in Loan Monitoring.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Actual payments by date")
        if payment_rows:
            pf = pd.DataFrame(payment_rows)
            currencies = set(pf.Currency.dropna().astype(str).str.upper())
            if len(currencies) == 1: _plot(px.line(pf.groupby("Payment Date", as_index=False).Amount.sum(), x="Payment Date", y="Amount", markers=True, title=f"Recorded payments ({next(iter(currencies))})"), "payment-trend", height=_CHART_STANDARD)
            else: st.dataframe(pf.groupby(["Payment Date", "Currency"], as_index=False).Amount.sum(), hide_index=True, width="stretch")
        else: _chart_empty("No recorded payment transactions match the selected payment-date range.")
    with c2:
        st.markdown("#### On-time vs late transactions")
        if on_time: _plot(px.pie(pd.DataFrame(on_time).groupby("Timing", as_index=False).size(), names="Timing", values="size", hole=.55), "payment-timing", height=_CHART_STANDARD)
        else: _chart_empty("Payment timing requires actual transactions linked to installment due dates.", height=_CHART_STANDARD)
    if delinquency_rows:
        df = pd.DataFrame(delinquency_rows)
        st.markdown("#### Delinquency aging and portfolio at risk")
        if len({r["Currency"] for r in delinquency_rows if r["Currency"]}) == 1:
            aging_data = df.groupby("Aging", as_index=False).agg({"Loan Account ID": "nunique", "Overdue Amount": "sum"}).rename(columns={"Loan Account ID": "Accounts"})
            _plot(px.bar(aging_data, x="Aging", y="Accounts", color_discrete_sequence=[_BLUE]), "delinquency-aging", height=_CHART_STANDARD)
        else: st.dataframe(df.groupby(["Aging", "Currency"], as_index=False).agg(Accounts=("Loan Account ID", "nunique"), **{"Overdue Amount": ("Overdue Amount", "sum")}), hide_index=True, width="stretch")
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("No overdue installments are found for complete schedules. If schedules are missing, delinquency status is insufficient data rather than zero.")
    par_rows = []
    for threshold in (30, 60, 90):
        value = calculate_par(accounts, date.today(), threshold)
        par_rows.append({f"PAR{threshold}": f"{value:.2f}%" if value is not None else "Not available", "Required basis": "Unique loan principal with DPD > threshold / current filtered outstanding principal"})
    st.markdown("#### Current portfolio at risk")
    st.dataframe(pd.DataFrame(par_rows), hide_index=True, width="stretch")
    st.caption("PAR uses Loan Monitoring principal balances as of today for all accounts matching the non-date filters; historic PAR trends require dated portfolio snapshots and are not reconstructed from current balances. Overdue does not mean legal default.")
    if payment_rows:
        pf = pd.DataFrame(payment_rows)
        st.markdown("#### Payment performance segments")
        segment = pf[pf.Timing.isin(["On time", "Late"])].groupby(["Borrower Type", "Purpose", "Timing"], as_index=False).size()
        st.dataframe(segment, hide_index=True, width="stretch")
        segment_rates = pf[pf.Timing.isin(["On time", "Late"])].groupby(["Borrower Type", "Purpose"], as_index=False).agg(Linked_Transactions=("Timing", "count"), On_Time_Rate=("Timing", lambda values: (values == "On time").mean() * 100), Late_Rate=("Timing", lambda values: (values == "Late").mean() * 100))
        st.dataframe(segment_rates, hide_index=True, width="stretch")
    if schedule_rows:
        scheduled_currency = {str(row["Currency"] or "").upper() for row in schedule_rows}
        payment_currency = {str(row["Currency"] or "").upper() for row in payment_rows}
        combined_currency = scheduled_currency | payment_currency
        if len(combined_currency) == 1 and "" not in combined_currency and "NOT SPECIFIED" not in combined_currency:
            scheduled = pd.DataFrame(schedule_rows).assign(Month=lambda data: data["Due Date"].map(lambda value: value.strftime("%Y-%m"))).groupby("Month", as_index=False)["Amount Due"].sum().rename(columns={"Amount Due": "Scheduled"})
            actual = pd.DataFrame(payment_rows).assign(Month=lambda data: data["Payment Date"].map(lambda value: value.strftime("%Y-%m"))).groupby("Month", as_index=False)["Amount"].sum().rename(columns={"Amount": "Actual payments"}) if payment_rows else pd.DataFrame(columns=["Month", "Actual payments"])
            compare = scheduled.merge(actual, on="Month", how="outer").fillna(0).sort_values("Month")
            st.markdown("#### Scheduled installments vs actual received payments")
            _plot(px.line(compare, x="Month", y=["Scheduled", "Actual payments"], markers=True, color_discrete_sequence=[_BLUE, "#0F766E"], title=f"Schedule due dates vs transaction dates ({next(iter(combined_currency))})"), "scheduled-vs-actual", height=_CHART_STANDARD)
        else:
            st.caption("Scheduled and actual amount trends are kept separate by currency because currencies are missing or mixed.")
    st.info("Historical delinquency and PAR trend lines require dated portfolio balance snapshots. Current balances are not used to reconstruct historical values.")
    if overview["on_time_rate"] is not None:
        st.caption("Loan Monitoring remains the source for operational schedules, transactions, DPD, and overdue amounts; this tab only aggregates those records.")


def _customer_analytics(apps: list[dict[str, Any]], accounts: list[dict[str, Any]]) -> None:
    st.markdown("### Customer & Borrower Analytics")
    frame = _app_frame(apps)
    if frame.empty:
        st.info("No application records match the selected filters.")
        return
    explicit_personal = [r for r in apps if _borrower_type(r) == "Personal"]
    explicit_business = [r for r in apps if _borrower_type(r) == "Business"]
    def unique_count(rows: Sequence[Mapping[str, Any]]) -> int | None:
        ids = [str(r.get("applicant_id") or r.get("customer_id") or r.get("email") or "").strip().casefold() for r in rows]
        return len(set(i for i in ids if i)) if ids and all(ids) else None
    _kpis([
        ("Personal borrowers", str(unique_count(explicit_personal)) if unique_count(explicit_personal) is not None else "Not available", "Unique applicant/customer ID or email required"),
        ("Business borrowers", str(unique_count(explicit_business)) if unique_count(explicit_business) is not None else "Not available", "Unique applicant/customer ID or email required"),
        ("Applications · Personal", str(len(explicit_personal)), "Records explicitly classified Personal"),
        ("Applications · Business", str(len(explicit_business)), "Records explicitly classified Business"),
        ("Returning borrowers", "Not available", "Reliable customer identity and cross-application history are required"),
        ("Unclassified applications", str(int((frame["Borrower Type"] == "Not specified").sum())), "Borrower type is not inferred from loan purpose"),
    ])
    composition_col, summary_col = st.columns(2)
    with composition_col:
        st.markdown("#### Borrower composition")
        _plot(px.pie(frame, names="Borrower Type", hole=.55, color_discrete_sequence=[_BLUE, "#0F766E", "#94A3B8"]), "borrower-composition", height=_CHART_PIE)
    with summary_col:
        st.markdown("#### Descriptive segment summary")
        st.dataframe(frame.groupby(["Borrower Type", "Loan Purpose", "Credit Risk"], as_index=False).size().rename(columns={"size": "Applications"}), hide_index=True, width="stretch", height=_CHART_PIE)
    for borrower_type in ("Personal", "Business"):
        segment = [r for r in apps if _borrower_type(r) == borrower_type]
        st.markdown(f"#### {borrower_type} analysis")
        if not segment:
            st.info(f"No applications are explicitly classified as {borrower_type}; borrower type is not inferred from loan purpose.")
            continue
        items = []
        for r in segment:
            analysis = r.get("financial_analysis", {})
            cashflow = analysis.get("income_cash_flow", analysis) if isinstance(analysis, Mapping) else {}
            capacity_root = analysis.get("repayment_capacity", {}) if isinstance(analysis, Mapping) else {}
            capacity = capacity_root.get(borrower_type.casefold(), {}) if isinstance(capacity_root, Mapping) else {}
            if not isinstance(cashflow, Mapping): cashflow = {}
            if not isinstance(capacity, Mapping): capacity = {}
            source_key = "income_sources" if borrower_type == "Personal" else "revenue_sources"
            sources = [source for source in cashflow.get(source_key, []) if isinstance(source, Mapping)] if isinstance(cashflow.get(source_key, []), Sequence) else []
            if borrower_type == "Business":
                sources = [source for source in sources if source.get("type") == "Business revenue"]
            normalized = [normalize_monthly_amount(source.get("gross_amount"), str(source.get("frequency", ""))) for source in sources]
            currency = str(cashflow.get("currency") or r.get("currency") or "Not specified")
            currency_confirmed = bool(cashflow.get("currency_confirmed")) if "currency_confirmed" in cashflow else bool(r.get("currency"))
            amount = sum(normalized) if sources and all(value is not None for value in normalized) and currency_confirmed else None
            work_group = r.get("employment_status") if borrower_type == "Personal" else r.get("industry") or r.get("business_type")
            expense_key, debt_key, expense_categories, _ = OBLIGATION_COLLECTIONS[borrower_type]
            obligations_root = analysis.get("obligations", {}) if isinstance(analysis, Mapping) else {}
            obligations_root = obligations_root if isinstance(obligations_root, Mapping) else {}
            expenses = obligations_root.get(expense_key, [])
            debts = obligations_root.get(debt_key, [])
            expenses = [value for value in expenses if isinstance(value, Mapping)] if isinstance(expenses, list) else []
            debts = [value for value in debts if isinstance(value, Mapping)] if isinstance(debts, list) else []
            business_expenses = cashflow.get("business_expenses", []) if borrower_type == "Business" else []
            business_expenses = [value for value in business_expenses if isinstance(value, Mapping)] if isinstance(business_expenses, list) else []
            no_debts = bool(obligations_root.get(f"{borrower_type.casefold()}_no_debts_reported")) and not debts
            summary = calculate_obligations_summary(expenses, debts, expense_categories, currency_confirmed=currency_confirmed, no_debts_reported=no_debts, part_two_business_expenses=business_expenses)
            evidence = sources + expenses + debts + business_expenses
            verification_values = {str(item.get("verification_status") or "Unverified") for item in evidence}
            verification = "Not available" if not evidence else "Verified" if verification_values == {"Verified"} else "Needs Review" if "Needs Review" in verification_values else "Unverified / mixed"
            provenance_values = {str(item.get("entry_source")) for item in expenses + debts if item.get("entry_source")}
            provenance = ", ".join(sorted(provenance_values)) if provenance_values else "Source not specified"
            items.append({"Application ID": _application_id(r), "Purpose": r.get("loan_purpose") or "Not specified", "Requested amount": _num(r.get("loan_amount")), "Requested Currency": r.get("currency") or "Not specified", "Income or revenue": amount, "Analysis Currency": currency, "Employment / industry": work_group or "Not available", "Monthly expenses": summary.get("total_expenses"), "Existing monthly debt payments": summary.get("total_monthly_debt_payments"), "Outstanding debt balance": summary.get("total_outstanding_debt"), "Financial information complete": bool(summary.get("expense_complete") and summary.get("debt_information_complete")), "Verification": verification, "Obligation provenance": provenance, "Risk": _risk(r), "DTI": _num(capacity.get("dti_percent")) if borrower_type == "Personal" else None, "DSTI": _num(capacity.get("dsti_percent")) if borrower_type == "Personal" else None, "DSCR": _num(capacity.get("dscr")) if borrower_type == "Business" else None, "Affordability interpretation": capacity.get("interpretation", "Not available")})
        data = pd.DataFrame(items)
        st.caption("Figures below use stored applicant or staff analysis fields where present. Missing values remain blank; personal ratios and business DSCR are not mixed.")
        st.dataframe(data, hide_index=True, width="stretch")
        st.dataframe(data.groupby(["Purpose", "Risk"], as_index=False).agg(Applications=("Application ID", "count")), hide_index=True, width="stretch")
        if data["Income or revenue"].notna().any():
            _plot(px.histogram(data.dropna(subset=["Income or revenue"]), x="Income or revenue", color="Risk", facet_col="Analysis Currency", color_discrete_map=_RISK_COLOR, title=f"Recorded monthly {'gross income' if borrower_type == 'Personal' else 'revenue'} range · {borrower_type}"), f"borrower-financials-{borrower_type.casefold()}", height=_CHART_STANDARD)
        else:
            st.info(f"No saved monthly {'income' if borrower_type == 'Personal' else 'revenue'} values are available for this segment.")
    st.caption("Borrower names and direct contact details are not included in analytics tables. New/returning borrower and industry/DSCR analyses require reliable borrower identity and explicit business fields.")


def _period_metrics(apps: list[dict[str, Any]], accounts: list[dict[str, Any]], start: date | None, end: date | None) -> dict[str, Any]:
    app_amounts = [_num(r.get("loan_amount")) for r in apps]
    app_currencies = {str(r.get("currency") or "").upper() for r in apps}
    app_currency = next(iter(app_currencies)) if len(app_currencies) == 1 and "" not in app_currencies else None
    average_requested = (sum(x for x in app_amounts if x is not None) / len(app_amounts)) if apps and app_currency and all(x is not None for x in app_amounts) else None
    overview = build_loan_overview(accounts, date.today())
    disbursement_overview = build_loan_overview(_period_accounts(accounts, start, end), date.today())
    payments = []
    for r in accounts:
        for p in _monitor(r).get("payments", []):
            if not isinstance(p, Mapping) or not _in_period(p.get("payment_date"), start, end): continue
            payments.append((r, p))
    received_currencies = {str(p.get("currency") or _disbursement(r).get("currency") or "").upper() for r, p in payments}
    received = [_num(p.get("amount_received")) for r, p in payments]
    received_ok = bool(payments) and all(x is not None for x in received) and len(received_currencies) == 1 and "" not in received_currencies and all(str(p.get("currency") or _disbursement(r).get("currency") or "").upper() == str(_disbursement(r).get("currency") or "").upper() for r, p in payments)
    principal = [_num(p.get("principal_allocation")) for r, p in payments]
    interest = [_num(p.get("interest_allocation")) for r, p in payments]
    alloc_ok = bool(payments) and all(x is not None for x in principal + interest) and all(str(_disbursement(r).get("currency") or "").upper() == str(p.get("currency") or _disbursement(r).get("currency") or "").upper() for r, p in payments)
    interest_currency = {str(_disbursement(r).get("currency") or "").upper() for r, p in payments}
    return {"overview": overview, "disbursement_overview": disbursement_overview, "average_requested": average_requested, "application_currency": app_currency,
            "payments": payments, "received": sum(x for x in received if x is not None) if received_ok else None,
            "principal": sum(x for x in principal if x is not None) if alloc_ok else None,
            "interest": sum(x for x in interest if x is not None) if alloc_ok and len(interest_currency) == 1 and "" not in interest_currency else None,
            "interest_currency": next(iter(interest_currency)) if len(interest_currency) == 1 and "" not in interest_currency else None}


def _financial_reports(apps: list[dict[str, Any]], accounts: list[dict[str, Any]], start: date | None, end: date | None, filters: Mapping[str, str]) -> None:
    st.markdown("### Financial Performance & Reports")
    metrics = _period_metrics(apps, accounts, start, end)
    overview = metrics["overview"]
    disbursement_overview = metrics["disbursement_overview"]
    currency = disbursement_overview["disbursed_currency"]
    _kpis([
        ("Actual disbursed amount", _fmt(disbursement_overview["disbursed_total"], currency), "Actual disbursements in the selected disbursement-date period; one currency required"),
        ("Outstanding principal", _fmt(overview["outstanding_total"], overview["outstanding_currency"]), "Loan Monitoring balance calculation"),
        ("Principal repaid", _fmt(metrics["principal"], metrics["interest_currency"]), "Actual principal allocations in payment-date period"),
        ("Interest received", _fmt(metrics["interest"], metrics["interest_currency"]), "Recorded interest allocations only; not total repayments"),
        ("Overdue amount", _fmt(overview["overdue_total"], overview["overdue_currency"]), "Actual past-due schedule amounts"),
        ("Average requested loan", _fmt(metrics["average_requested"], metrics["application_currency"]), "Application level; shown only with a known consistent application currency"),
    ])
    trend = _disbursement_trend(_period_accounts(accounts, start, end), "Monthly")
    if trend.empty:
        st.info("No dated actual disbursements are available for the selected reporting period.")
    elif trend.Currency.nunique() == 1:
        st.markdown("#### Actual disbursement and payment trends")
        _plot(px.line(trend, x="Period", y="Disbursed Amount", markers=True, color_discrete_sequence=[_BLUE]), "financial-disbursement-trend", height=_CHART_STANDARD)
    if metrics["payments"]:
        if metrics["principal"] is not None and metrics["interest"] is not None:
            payment_data = []
            for r, p in metrics["payments"]:
                day = _date(p.get("payment_date"))
                if day:
                    payment_data.append({"Month": day.strftime("%Y-%m"), "Principal": _num(p.get("principal_allocation")), "Interest": _num(p.get("interest_allocation")), "Currency": p.get("currency") or _disbursement(r).get("currency")})
            if payment_data:
                pf = pd.DataFrame(payment_data).groupby(["Month", "Currency"], as_index=False).agg(Principal=("Principal", "sum"), Interest=("Interest", "sum"))
                if pf.Currency.nunique() == 1:
                    _plot(px.line(pf, x="Month", y=["Principal", "Interest"], markers=True, color_discrete_sequence=[_BLUE, "#0F766E"], title=f"Recorded principal and interest allocations ({pf.Currency.iloc[0]})"), "principal-interest-trends", height=_CHART_STANDARD)
                else:
                    st.dataframe(pf, hide_index=True, width="stretch")
    else:
            st.info("Principal and interest trends need complete, currency-consistent allocations on dated payment records. Repayment totals are not treated as interest income.")
    st.caption("Historical outstanding-balance and overdue-amount trends require dated account snapshots; current balances are not used to reconstruct historical values.")
    st.markdown("#### Period comparison")
    compare = st.selectbox("Compare", ["Current month vs previous month", "Current quarter vs previous quarter", "Current year vs previous year"], key="ba-period-compare")
    today = date.today()
    if compare.startswith("Current month"):
        current_start = today.replace(day=1); previous_end = current_start - timedelta(days=1); previous_start = previous_end.replace(day=1)
    elif compare.startswith("Current quarter"):
        quarter_month = ((today.month - 1) // 3) * 3 + 1; current_start = date(today.year, quarter_month, 1); previous_end = current_start - timedelta(days=1); prev_month = previous_end.month; previous_start = date(previous_end.year, ((prev_month - 1) // 3) * 3 + 1, 1)
    else:
        current_start = date(today.year, 1, 1); previous_start = date(today.year - 1, 1, 1); previous_end = date(today.year - 1, 12, 31)
    def disb_total(lo: date, hi: date) -> float | None:
        rows = [r for r in accounts if _in_period(_disbursement(r).get("disbursed_at"), lo, hi)]
        vals = [_num(_disbursement(r).get("disbursed_amount")) for r in rows]
        currencies = {str(_disbursement(r).get("currency") or "").upper() for r in rows}
        if rows and all(v is not None for v in vals) and len(currencies) == 1 and "" not in currencies:
            return sum(v for v in vals if v is not None)
        if not rows and accounts and _common_currency(accounts):
            return 0.0
        return None
    current, previous = disb_total(current_start, today), disb_total(previous_start, previous_end)
    difference = current - previous if current is not None and previous is not None else None
    percent = (difference / previous * 100) if difference is not None and previous else None
    _kpis([("Current period disbursements", _fmt(current, currency), current_start.isoformat() + " to " + today.isoformat()), ("Previous period disbursements", _fmt(previous, currency), previous_start.isoformat() + " to " + previous_end.isoformat()), ("Absolute difference", _fmt(difference, currency), "Current minus previous; percentage unavailable if prior amount is zero"), ("Percentage change", f"{percent:+.1f}%" if percent is not None else "Not available", "Calculated only with nonzero previous-period amount")])
    report_type = st.selectbox("Analytical report", ["Portfolio Overview Report", "Loan Portfolio Analysis Report", "Credit Risk Analysis Report", "Repayment & Delinquency Report", "Customer & Borrower Analysis Report", "Financial Performance Report"], key="ba-report-type")
    st.caption("Internal portfolio analysis · Not an official bank, audited, accounting, or lending-decision report.")
    if report_type in {"Portfolio Overview Report", "Financial Performance Report"}:
        export_frame = _loan_rows(_period_accounts(accounts, start, end))
        if export_frame.empty: export_frame = _app_frame(apps)
    elif report_type == "Loan Portfolio Analysis Report":
        application_export = _app_frame(apps).assign(**{"Record Type": "Application"})
        loan_export = _loan_rows(_period_accounts(accounts, start, end)).assign(**{"Record Type": "Disbursed Account"})
        export_frame = pd.concat([application_export, loan_export], ignore_index=True, sort=False)
    elif report_type == "Credit Risk Analysis Report":
        export_frame = _app_frame(apps)
        if not export_frame.empty: export_frame = export_frame[["Application ID", "Borrower Type", "Loan Purpose", "Requested Amount", "Credit Risk", "Final Decision"]]
    elif report_type == "Repayment & Delinquency Report":
        payment_data = []
        for record in accounts:
            for installment in _monitor(record).get("repayment_schedule", []):
                if not isinstance(installment, Mapping) or not _in_period(installment.get("due_date"), start, end): continue
                due, paid = _num(installment.get("amount_due")), _num(installment.get("amount_paid"))
                payment_data.append({"Record Type": "Scheduled Installment", "Application ID": _application_id(record), "Loan Account ID": _monitor(record).get("loan_account_id"), "Installment": installment.get("installment_number"), "Due Date": _date(installment.get("due_date")), "Payment Date": None, "Amount Due": due, "Amount Paid to Installment": paid, "Remaining Scheduled": due - paid if due is not None and paid is not None and paid <= due else None, "Amount Received": None, "Principal Allocation": None, "Interest Allocation": None, "Currency": installment.get("currency") or _disbursement(record).get("currency")})
            for payment in _monitor(record).get("payments", []):
                if not isinstance(payment, Mapping) or not _in_period(payment.get("payment_date"), start, end): continue
                payment_data.append({"Record Type": "Payment Transaction", "Application ID": _application_id(record), "Loan Account ID": _monitor(record).get("loan_account_id"), "Installment": None, "Due Date": _date(payment.get("due_date")), "Payment Date": _date(payment.get("payment_date")), "Amount Due": None, "Amount Paid to Installment": None, "Remaining Scheduled": None, "Amount Received": _num(payment.get("amount_received")), "Principal Allocation": _num(payment.get("principal_allocation")), "Interest Allocation": _num(payment.get("interest_allocation")), "Currency": payment.get("currency") or _disbursement(record).get("currency")})
        export_frame = pd.DataFrame(payment_data)
    else:
        export_frame = _app_frame(apps)
        if not export_frame.empty:
            export_frame = export_frame.groupby(["Borrower Type", "Loan Purpose", "Credit Risk"], as_index=False).size().rename(columns={"size": "Applications"})
    metadata = {"Report": report_type, "Generated": datetime.now().astimezone().isoformat(timespec="minutes"), "Period": f"{start or 'All time'} to {end or 'All time'}", **dict(filters)}
    if not export_frame.empty:
        export_frame = export_frame.copy()
        export_frame.insert(0, "Report", report_type)
        export_frame.insert(1, "Generated At", metadata["Generated"])
        export_frame.insert(2, "Selected Period", metadata["Period"])
        for key, value in filters.items(): export_frame[f"Filter · {key}"] = value
        st.caption("Exported rows use the selected global filters. Dates are ISO-formatted; amounts retain currency fields where available.")
    if export_frame.empty:
        st.info("No matching records are available for this report. Exports are disabled until filtered data exists.")
    else:
        st.dataframe(export_frame.head(100), hide_index=True, width="stretch")
        csv = export_frame.to_csv(index=False).encode("utf-8-sig")
        c1, c2, c3 = st.columns(3)
        with c1: st.download_button("Download filtered CSV", csv, "banking_analytics_report.csv", "text/csv", key="ba-report-csv")
        with c2:
            xlsx = io.BytesIO()
            with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
                export_frame.to_excel(writer, index=False, sheet_name="Analytics")
                pd.DataFrame([metadata]).to_excel(writer, index=False, sheet_name="Report Metadata")
            st.download_button("Download filtered Excel", xlsx.getvalue(), "banking_analytics_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ba-report-xlsx")
        with c3:
            pdf_lines = [f"{report_type} - Internal Analytics", f"Generated: {metadata['Generated']}", f"Period: {metadata['Period']}", f"Filters: {filters}", f"Application records in filtered cohort: {len(apps)}", f"Eligible disbursed accounts in current filtered portfolio: {len(accounts)}", f"Approved applications with explicit final decisions: {sum(isinstance(r.get('final_lending_decision'), Mapping) and str(r['final_lending_decision'].get('status', '')).casefold() == 'approved' for r in apps)}", f"Disbursed total for period: {_fmt(disbursement_overview['disbursed_total'], disbursement_overview['disbursed_currency'])}", f"Current outstanding principal: {_fmt(overview['outstanding_total'], overview['outstanding_currency'])}", f"Recorded interest allocations in payment period: {_fmt(metrics['interest'], metrics['interest_currency'])}", f"Rows in selected report table: {len(export_frame)}", "Limitations: derived from available shared application and loan monitoring records; not audited or an accounting report."]
            pdf_lines += [" | ".join(str(x) for x in row[:6]) for row in export_frame.head(35).itertuples(index=False, name=None)]
            st.download_button("Download filtered PDF", _pdf(pdf_lines), "banking_analytics_report.pdf", "application/pdf", key="ba-report-pdf")


def _pdf(lines: Sequence[str]) -> bytes:
    """Small dependency-free text PDF suitable for internal analytical exports."""
    import textwrap
    def esc(value: Any) -> str:
        ascii_value = str(value).encode("ascii", "replace").decode("ascii")
        return ascii_value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    wrapped = [part for line in lines for part in (textwrap.wrap(str(line), 92) or [""])]
    pages = [wrapped[i:i + 48] for i in range(0, max(1, len(wrapped)), 48)]
    objects = [b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"]
    page_refs = []
    for i, page in enumerate(pages):
        page_id, content_id = 3 + i * 2, 4 + i * 2
        page_refs.append(f"{page_id} 0 R")
        stream = "BT\n/F1 9 Tf\n45 795 Td\n12 TL\n" + "\n".join(f"({esc(line)}) Tj T*" for line in page) + "\nET"
        data = stream.encode("ascii")
        objects.append(f"{page_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 {3 + len(pages)*2} 0 R >> >> /Contents {content_id} 0 R >> endobj\n".encode())
        objects.append(f"{content_id} 0 obj << /Length {len(data)} >> stream\n".encode() + data + b"\nendstream endobj\n")
    pages_id, font_id = 2, 3 + len(pages) * 2
    objects.insert(1, f"2 0 obj << /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(pages)} >> endobj\n".encode())
    objects.append(f"{font_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n".encode())
    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for item in objects:
        offsets.append(len(body)); body.extend(item)
    xref = len(body)
    body.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: body.extend(f"{offset:010d} 00000 n \n".encode())
    body.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(body)


def render() -> None:
    records = _dedupe_applications(_records())
    st.markdown("<div style='font-size:.92rem;color:#64748B;margin:0 0 14px'>Analyze application activity, assessed risk, repayment behavior, and supported portfolio financial trends across the banking system.</div>", unsafe_allow_html=True)
    st.markdown(_ANALYTICS_CSS, unsafe_allow_html=True)
    with st.container(key="ba-analytics"):
        apps, accounts, start, end, filters = _global_filters(records)
        tabs = st.tabs(["Portfolio Overview", "Loan Portfolio Analysis", "Credit Risk Analytics", "Repayment & Delinquency Analytics", "Customer & Borrower Analytics", "Financial Performance & Reports"])
        with tabs[0]: _portfolio_overview(apps, accounts, start, end, filters)
        with tabs[1]: _loan_portfolio_analysis(apps, _period_accounts(accounts, start, end))
        with tabs[2]: _credit_risk_analytics(apps, _period_accounts(accounts, start, end))
        with tabs[3]: _repayment_analytics(accounts, start, end)
        with tabs[4]: _customer_analytics(apps, accounts)
        with tabs[5]: _financial_reports(apps, accounts, start, end, filters)
