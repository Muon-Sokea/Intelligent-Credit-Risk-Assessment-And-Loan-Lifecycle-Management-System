"""Integrated post-disbursement loan monitoring over shared application records."""
from __future__ import annotations

import html
import io
import re
import textwrap
import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping, Sequence

import pandas as pd
import plotly.express as px
import streamlit as st
from data.loan_applications_demo import create_loan_application_demo_data

APPLICATIONS_KEY = "loan_application_records"
CENT = Decimal("0.01")
FREQUENCIES = {"Monthly": 1, "Quarterly": 3}
_MONITORING_EVENTS = {
    "Payment recorded", "Loan disbursed", "Follow-up completed",
    "Overdue status updated", "Collection activity recorded", "Promise recorded",
    "Loan status updated", "Repayment schedule generated",
}
_AGING = ("Current / Not Overdue", "1–30 Days", "31–60 Days", "61–90 Days", "More Than 90 Days")


def _decimal(value: Any, *, allow_zero: bool = True) -> Decimal | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        return None
    return amount


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def _iso(value: date | datetime) -> str:
    return value.isoformat()


def _money(value: Any, currency: str | None = None) -> str:
    amount = _decimal(value)
    return f"{currency} {amount:,.2f}" if amount is not None and currency else f"{amount:,.2f}" if amount is not None else "Not available"


def _monitor(record: Mapping[str, Any]) -> dict[str, Any]:
    data = record.get("loan_monitoring")
    return data if isinstance(data, dict) else {}


def _disbursement(record: Mapping[str, Any]) -> dict[str, Any]:
    value = _monitor(record).get("disbursement")
    return value if isinstance(value, dict) else {}


def is_disbursed_monitoring_account(record: Mapping[str, Any]) -> bool:
    """Require a recorded disbursement and an explicit monitored account state."""
    disbursement = _disbursement(record)
    monitoring = record.get("loan_monitoring", {})
    status = str(monitoring.get("account_status", "")).strip().casefold() if isinstance(monitoring, Mapping) else ""
    return (
        str(disbursement.get("status", "")).strip().casefold() == "disbursed"
        and _date(disbursement.get("disbursed_at")) is not None
        and status in {"active", "fully repaid"}
        and bool(str(_monitor(record).get("loan_account_id") or "").strip())
        and bool(str(record.get("application_id") or "").strip())
        and _decimal(disbursement.get("disbursed_amount"), allow_zero=False) is not None
        and bool(str(disbursement.get("currency") or "").strip())
    )


def _account_id(record: Mapping[str, Any]) -> str:
    return str(_monitor(record).get("loan_account_id") or "Not assigned")


def _repaid_status_matches_balance(record: Mapping[str, Any]) -> bool:
    return (
        _allocation_schedule_complete(record)
        and _outstanding_principal(record) == 0
        and _remaining_obligation(record) == 0
    )


def _borrower(record: Mapping[str, Any]) -> str:
    return str(record.get("applicant_name") or record.get("business_name") or "Applicant not specified")


def _all_records() -> list[dict[str, Any]]:
    if APPLICATIONS_KEY not in st.session_state:
        st.session_state[APPLICATIONS_KEY] = create_loan_application_demo_data()
    value = st.session_state.get(APPLICATIONS_KEY, [])
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def _eligible(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates = [r for r in records if isinstance(r, dict) and is_disbursed_monitoring_account(r)]
    account_counts = Counter(_account_id(r).casefold() for r in candidates)
    application_counts = Counter(str(r.get("application_id", "")).casefold() for r in candidates)
    return [r for r in candidates if account_counts[_account_id(r).casefold()] == 1 and application_counts[str(r.get("application_id", "")).casefold()] == 1]


def _duplicate_monitoring_ids(records: Sequence[Mapping[str, Any]]) -> list[str]:
    candidates = [r for r in records if isinstance(r, Mapping) and is_disbursed_monitoring_account(r)]
    account_counts = Counter(_account_id(r).casefold() for r in candidates)
    application_counts = Counter(str(r.get("application_id", "")).casefold() for r in candidates)
    duplicate_ids = {_account_id(r) for r in candidates if account_counts[_account_id(r).casefold()] > 1 or application_counts[str(r.get("application_id", "")).casefold()] > 1}
    return sorted(duplicate_ids)


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _add_months(day: date, months: int) -> date:
    month0 = day.month - 1 + months
    year, month = day.year + month0 // 12, month0 % 12 + 1
    # Clamp to the final day in the destination month.
    import calendar
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def generate_repayment_schedule(
    principal: Any, annual_rate: Any, term_months: int, frequency: str,
    first_due_date: date, currency: str,
) -> list[dict[str, Any]]:
    """Fixed nominal-rate amortization; rounded cents and final principal adjustment."""
    p = _decimal(principal, allow_zero=False)
    rate = _decimal(annual_rate)
    months_per_period = FREQUENCIES.get(frequency)
    if p is None or rate is None or not isinstance(term_months, int) or term_months <= 0:
        raise ValueError("Enter a positive principal, nonnegative interest rate, and positive term.")
    if months_per_period is None or term_months % months_per_period:
        raise ValueError("Term must be a positive number of months divisible by the selected repayment frequency.")
    count = term_months // months_per_period
    period_rate = rate / Decimal(100) * Decimal(months_per_period) / Decimal(12)
    payment = p / count if period_rate == 0 else p * period_rate / (1 - (1 + period_rate) ** (-count))
    payment = _round_money(payment)
    balance = p
    rows = []
    for number in range(1, count + 1):
        interest = _round_money(balance * period_rate)
        principal_due = balance if number == count else min(balance, _round_money(payment - interest))
        installment = _round_money(principal_due + interest)
        balance = max(Decimal(0), balance - principal_due)
        rows.append({
            "installment_number": number,
            "due_date": _iso(_add_months(first_due_date, months_per_period * (number - 1))),
            "opening_principal": str(_round_money(balance + principal_due)),
            "principal_due": str(_round_money(principal_due)),
            "interest_due": str(interest),
            "amount_due": str(installment),
            "amount_paid": "0.00",
            "principal_paid": "0.00",
            "interest_paid": "0.00",
            "currency": currency.upper(),
        })
    return rows


def schedule_status(row: Mapping[str, Any], today: date) -> str:
    due, paid, due_date = _decimal(row.get("amount_due")), _decimal(row.get("amount_paid")), _date(row.get("due_date"))
    if due is None or paid is None or due_date is None:
        return "Data incomplete"
    if paid >= due:
        return "Paid"
    if paid > 0:
        return "Partially Paid" if due_date >= today else "Overdue"
    if due_date < today:
        return "Missed"
    if due_date == today:
        return "Due Today"
    return "Upcoming"


def _scheduled_amount_total(record: Mapping[str, Any]) -> Decimal | None:
    rows = _monitor(record).get("repayment_schedule", [])
    if not isinstance(rows, list) or not rows:
        return None
    total = Decimal(0)
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        due = _decimal(row.get("amount_due"))
        if due is None:
            return None
        total += due
    return _round_money(total)


def _remaining_obligation(record: Mapping[str, Any]) -> Decimal | None:
    rows = _monitor(record).get("repayment_schedule", [])
    if not isinstance(rows, list) or not rows:
        return None
    total = Decimal(0)
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        due, paid = _decimal(row.get("amount_due")), _decimal(row.get("amount_paid"))
        if due is None or paid is None or paid > due:
            return None
        total += due - paid
    return _round_money(total)


def _allocation_schedule_complete(record: Mapping[str, Any]) -> bool:
    rows = _monitor(record).get("repayment_schedule", [])
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, Mapping):
            return False
        due_date = _date(row.get("due_date"))
        due, paid = _decimal(row.get("amount_due")), _decimal(row.get("amount_paid"))
        principal, interest = _decimal(row.get("principal_due")), _decimal(row.get("interest_due"))
        if due_date is None or due is None or paid is None or principal is None or interest is None or paid > due:
            return False
        if abs(_round_money(principal + interest) - due) > CENT:
            return False
    return True


def _outstanding_principal(record: Mapping[str, Any]) -> Decimal | None:
    disbursed = _decimal(_disbursement(record).get("disbursed_amount"))
    if disbursed is None:
        return None
    principal_paid = Decimal(0)
    for payment in _monitor(record).get("payments", []):
        if isinstance(payment, Mapping):
            payment_currency = str(payment.get("currency") or _disbursement(record).get("currency") or "").upper()
            if payment_currency != str(_disbursement(record).get("currency") or "").upper():
                return None
            value = _decimal(payment.get("principal_allocation"))
            if value is None:
                return None
            principal_paid += value
        else:
            return None
    if principal_paid > disbursed:
        return None
    return _round_money(disbursed - principal_paid)


def _payment_received_total(record: Mapping[str, Any]) -> Decimal | None:
    currency = str(_disbursement(record).get("currency") or "").upper()
    payments = _monitor(record).get("payments", [])
    if not isinstance(payments, list) or not currency:
        return None
    total = Decimal(0)
    for payment in payments:
        if not isinstance(payment, Mapping):
            return None
        amount = _decimal(payment.get("amount_received"), allow_zero=False)
        payment_currency = str(payment.get("currency") or currency).upper()
        if amount is None or payment_currency != currency:
            return None
        total += amount
    return _round_money(total)


def _payment_allocation_total(record: Mapping[str, Any], field: str) -> Decimal | None:
    payments = _monitor(record).get("payments", [])
    if not isinstance(payments, list):
        return None
    total = Decimal(0)
    for payment in payments:
        if not isinstance(payment, Mapping):
            return None
        amount = _decimal(payment.get(field))
        if amount is None:
            return None
        total += amount
    return _round_money(total)


def _overdue_rows(record: Mapping[str, Any], today: date) -> tuple[list[dict[str, Any]], bool]:
    rows = _monitor(record).get("repayment_schedule", [])
    if not isinstance(rows, list) or not rows:
        return [], False
    overdue = []
    for row in rows:
        if not isinstance(row, Mapping):
            return [], False
        due_date, due, paid = _date(row.get("due_date")), _decimal(row.get("amount_due")), _decimal(row.get("amount_paid"))
        if due_date is None or due is None or paid is None or paid > due:
            return [], False
        remaining = max(Decimal(0), due - paid)
        if due_date < today and remaining > 0:
            overdue.append({**row, "remaining_amount": _round_money(remaining), "days_past_due": (today - due_date).days})
    return overdue, True


def aging_bucket(days_past_due: int) -> str:
    if days_past_due <= 0:
        return _AGING[0]
    if days_past_due <= 30:
        return _AGING[1]
    if days_past_due <= 60:
        return _AGING[2]
    if days_past_due <= 90:
        return _AGING[3]
    return _AGING[4]


def account_monitoring_row(record: Mapping[str, Any], today: date) -> dict[str, Any]:
    monitoring = _monitor(record)
    disbursement = _disbursement(record)
    overdue, complete = _overdue_rows(record, today)
    oldest = min((_date(r.get("due_date")) for r in overdue), default=None)
    dpd = (today - oldest).days if oldest else 0
    payment_dates = [_date(p.get("payment_date") or p.get("paid_at")) for p in monitoring.get("payments", []) if isinstance(p, Mapping)]
    last_payment = max((d for d in payment_dates if d), default=None)
    last_activity = max((_date(a.get("contact_date") or a.get("timestamp") or a.get("created_at")) for a in monitoring.get("collection_activities", []) if isinstance(a, Mapping)), default=None)
    purpose = record.get("loan_purpose") or record.get("purpose") or "Not specified"
    return {
        "Loan Account ID": _account_id(record), "Application ID": record.get("application_id", "Not specified"),
        "Applicant / Business": _borrower(record), "Loan Type": monitoring.get("loan_type") or record.get("loan_product") or "Not specified",
        "Loan Purpose": purpose, "Disbursed Amount": _decimal(disbursement.get("disbursed_amount")),
        "Outstanding Balance": _outstanding_principal(record), "Annual Rate (%)": _decimal(disbursement.get("annual_interest_rate")),
        "Term (months)": disbursement.get("term_months"), "Disbursement Date": _date(disbursement.get("disbursed_at")),
        "Next Payment Date": min((_date(r.get("due_date")) for r in monitoring.get("repayment_schedule", []) if isinstance(r, Mapping) and _date(r.get("due_date")) and schedule_status(r, today) in {"Upcoming", "Due Today", "Partially Paid"}), default=None),
        "Loan Status": monitoring.get("account_status", "Not specified"), "Overdue Status": f"{dpd} days past due" if overdue else "Current" if complete else "Not available",
        "Overdue Amount": sum((r["remaining_amount"] for r in overdue), Decimal(0)) if complete else None,
        "Oldest Due Date": oldest, "Days Past Due": dpd if complete else None, "Unpaid Installments": len(overdue) if complete else None,
        "Last Payment Date": last_payment, "Collection Status": monitoring.get("collection_status", "Not assigned"),
        "Monitoring Data Source": disbursement.get("source_status", "Not specified"),
        "Status Reconciliation": "Consistent" if str(monitoring.get("account_status", "")).casefold() != "fully repaid" or _repaid_status_matches_balance(record) else "Review: balance does not reconcile",
        "Action": "Review account details",
        "Follow-up Required": bool(monitoring.get("follow_up_required")), "Last Contact Date": last_activity,
        "Currency": str(disbursement.get("currency") or "").upper(), "_record": record,
        "_overdue": overdue, "_schedule_complete": complete,
    }


def build_loan_overview(records: Sequence[Mapping[str, Any]], today: date | None = None) -> dict[str, Any]:
    """Summarize explicit disbursed-account data; unknown or mixed-currency totals remain unavailable."""
    as_of = today or date.today()
    accounts = _eligible(records)
    rows = [account_monitoring_row(r, as_of) for r in accounts]
    active = [r for r in accounts if str(_monitor(r).get("account_status", "")).casefold() == "active"]
    repaid = [
        r for r in accounts
        if str(_monitor(r).get("account_status", "")).casefold() == "fully repaid"
        and _repaid_status_matches_balance(r)
    ]
    def aggregate(key: str, subset: Sequence[dict[str, Any]]) -> tuple[Decimal | None, str | None]:
        values = [(_decimal(_disbursement(r).get(key) if key == "disbursed_amount" else _monitor(r).get(key)), str(_disbursement(r).get("currency") or "").upper()) for r in subset]
        currencies = {c for _, c in values}
        if not values or len(currencies) != 1 or "" in currencies or any(v is None for v, _ in values):
            return None, None
        return sum((v for v, _ in values if v is not None), Decimal(0)), next(iter(currencies))
    disbursed, disbursed_currency = aggregate("disbursed_amount", accounts)
    outstanding_values = [(_outstanding_principal(r), str(_disbursement(r).get("currency") or "").upper()) for r in accounts]
    outstanding_currencies = {c for _, c in outstanding_values}
    outstanding = sum((v for v, _ in outstanding_values if v is not None), Decimal(0)) if outstanding_values and len(outstanding_currencies) == 1 and "" not in outstanding_currencies and all(v is not None for v, _ in outstanding_values) else None
    overdue_rows, schedule_complete = [], True
    for record in active:
        rows_for_account, complete = _overdue_rows(record, as_of)
        schedule_complete &= complete
        overdue_rows.extend({**row, "_record": record, "_account_id": _account_id(record)} for row in rows_for_account)
    overdue_ids = sorted({_account_id(row["_record"]) for row in overdue_rows}) if schedule_complete else None
    overdue_currency_set = {str(row.get("currency") or _disbursement(row["_record"]).get("currency") or "").upper() for row in overdue_rows}
    overdue_total = sum((row["remaining_amount"] for row in overdue_rows), Decimal(0)) if schedule_complete and (not overdue_rows or (len(overdue_currency_set) == 1 and "" not in overdue_currency_set)) else None
    overdue_currency = next(iter(overdue_currency_set)) if overdue_rows and len(overdue_currency_set) == 1 else (disbursed_currency if not overdue_rows else None)
    payment_rows, payment_amounts, payment_currencies = [], [], set()
    payment_amounts_complete, any_payment = True, False
    principal_repaid = Decimal(0)
    interest_received = Decimal(0)
    allocation_complete = True
    for record in accounts:
        currency = str(_disbursement(record).get("currency") or "").upper()
        for payment in _monitor(record).get("payments", []):
            if not isinstance(payment, Mapping):
                payment_complete = False
                continue
            any_payment = True
            amount, pdate = _decimal(payment.get("amount_received"), allow_zero=False), _date(payment.get("payment_date"))
            payment_currency_value = str(payment.get("currency") or currency).upper()
            if amount is None or not currency or payment_currency_value != currency:
                payment_amounts_complete = False
            else:
                payment_amounts.append(amount); payment_currencies.add(payment_currency_value)
            principal_allocation = _decimal(payment.get("principal_allocation"))
            interest_allocation = _decimal(payment.get("interest_allocation"))
            if principal_allocation is None or interest_allocation is None:
                allocation_complete = False
            else:
                principal_repaid += principal_allocation
                interest_received += interest_allocation
            due_date = _date(payment.get("due_date"))
            if amount is not None and pdate and due_date:
                payment_rows.append((pdate, due_date))
    on_time_count = sum(p <= d for p, d in payment_rows)
    late_count = sum(p > d for p, d in payment_rows)
    total_received = sum(payment_amounts, Decimal(0)) if any_payment and payment_amounts_complete and len(payment_currencies) == 1 else None
    payment_currency = next(iter(payment_currencies)) if total_received is not None else None
    activities = []
    for record in accounts:
        data = _monitor(record)
        for event in data.get("activities", []):
            if isinstance(event, Mapping) and (event.get("event") or event.get("type")) in _MONITORING_EVENTS and (event.get("timestamp") or event.get("created_at")):
                activities.append({"Loan Account ID": _account_id(record), "Application ID": record.get("application_id", "Not specified"), "Activity": event.get("event") or event.get("type"), "Detail": event.get("detail") or event.get("notes") or "", "Time": event.get("timestamp") or event.get("created_at"), "_sort": _date(event.get("timestamp") or event.get("created_at")) or date.min})
    activities.sort(key=lambda a: a["_sort"], reverse=True)
    for event in activities:
        event.pop("_sort", None)
    return {
        "accounts": accounts, "active": active, "repaid": repaid, "rows": rows,
        "followups": [str(r.get("application_id", _account_id(r))) for r in active if _monitor(r).get("follow_up_required") is True],
        "disbursed_total": disbursed, "disbursed_currency": disbursed_currency,
        "outstanding_total": outstanding, "outstanding_currency": next(iter(outstanding_currencies)) if outstanding is not None else None,
        "overdue_accounts": overdue_ids, "overdue_rows": overdue_rows if schedule_complete else None,
        "overdue_total": overdue_total, "overdue_currency": overdue_currency,
        "max_dpd": max((int((as_of - _date(r["due_date"])).days) for r in overdue_rows), default=0) if schedule_complete else None,
        "missed_installments": sum((_decimal(row.get("amount_paid")) or Decimal(0)) == 0 for row in overdue_rows) if schedule_complete else None,
        "on_time_rate": on_time_count / len(payment_rows) * 100 if payment_rows else None,
        "late_rate": late_count / len(payment_rows) * 100 if payment_rows else None,
        "payment_count": len(payment_rows), "total_received": total_received, "payment_currency": payment_currency,
        "principal_repaid": principal_repaid if any_payment and allocation_complete else None,
        "interest_received": interest_received if any_payment and allocation_complete else None,
        "activities": activities, "as_of": as_of,
    }


def _new_event(record: dict[str, Any], event: str, detail: str = "") -> None:
    data = _monitor(record)
    data.setdefault("activities", [])
    data["activities"].append({"event": event, "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"), "detail": detail})


def _page_styles(dark: bool) -> str:
    surface, text, muted, border, soft = ("#172338", "#F1F5F9", "#A7B4C5", "#33445C", "#1A2940") if dark else ("#FFFFFF", "#1E293B", "#64748B", "#E2E8F0", "#F8FAFC")
    return f"""<style>
    .st-key-loan-monitoring-page {{ color:{text}; }}
    .st-key-loan-monitoring-page .lm-header {{ margin:0 0 18px; }}
    .st-key-loan-monitoring-page .lm-title {{ color:{text}; font-size:1.62rem; font-weight:750; letter-spacing:-.02em; line-height:1.2; margin:0; }}
    .st-key-loan-monitoring-page .lm-subtitle {{ color:{muted}; font-size:.9rem; margin:5px 0 0; }}
    .st-key-loan-monitoring-page .lm-kpi {{ height:100%; min-height:118px; box-sizing:border-box; background:{surface}; border:1px solid {border}; border-radius:12px; padding:15px; box-shadow:0 2px 8px rgba(15,23,42,.04); }}
    .st-key-loan-monitoring-page .lm-label {{ color:{muted}; font-size:.74rem; font-weight:650; line-height:1.35; min-height:32px; }}
    .st-key-loan-monitoring-page .lm-value {{ color:{text}; font-size:1.2rem; font-weight:750; line-height:1.25; margin-top:8px; overflow-wrap:anywhere; }}
    .st-key-loan-monitoring-page .lm-help {{ color:{muted}; font-size:.68rem; line-height:1.35; margin-top:4px; }}
    .st-key-loan-monitoring-page .lm-empty {{ border:1px dashed {border}; border-radius:11px; background:{soft}; color:{muted}; line-height:1.55; padding:18px; margin:8px 0 16px; }}
    .st-key-loan-monitoring-page .stTabs [data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid {border}; }}
    .st-key-loan-monitoring-page .stTabs [data-baseweb="tab"] {{ color:{muted}; font-weight:650; }}
    .st-key-loan-monitoring-page .stTabs [aria-selected="true"] {{ color:#2563EB; }}
    @media(max-width:950px) {{ .st-key-loan-monitoring-page .lm-kpi {{ min-height:100px; padding:12px; }} }}
    @media print {{ .st-key-loan-monitoring-page .stTabs, .st-key-loan-monitoring-page .stButton, .st-key-loan-monitoring-page .stDownloadButton {{ display:none!important; }} }}
    </style>"""


def _card(label: str, value: str, detail: str = "") -> None:
    st.markdown(f'<div class="lm-kpi"><div class="lm-label">{html.escape(label)}</div><div class="lm-value">{html.escape(value)}</div><div class="lm-help">{html.escape(detail)}</div></div>', unsafe_allow_html=True)


def _tab_kpis(items: Sequence[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items), gap="small")
    for col, (label, value, detail) in zip(cols, items):
        with col:
            _card(label, value, detail)


def _activity_table(accounts: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in accounts:
        data = _monitor(record)
        for event in data.get("collection_activities", []):
            if isinstance(event, Mapping):
                rows.append({"Loan Account ID": _account_id(record), "Application ID": record.get("application_id"), "Date": event.get("contact_date"), "Method": event.get("method"), "Outcome": event.get("outcome"), "Response / Notes": event.get("response") or event.get("notes"), "Next Follow-up": event.get("next_follow_up_date"), "Assigned Staff": event.get("assigned_staff")})
    rows.sort(key=lambda r: str(r.get("Date") or ""), reverse=True)
    return pd.DataFrame(rows)


def _account_selector(accounts: Sequence[dict[str, Any]], widget_key: str) -> dict[str, Any] | None:
    if not accounts:
        return None
    by_id = {_account_id(r): r for r in accounts}
    ids = list(by_id)
    shared = st.session_state.get("loan_monitoring_selected_account")
    if widget_key not in st.session_state or st.session_state.get(widget_key) not in ids or shared in ids:
        st.session_state[widget_key] = shared if shared in ids else ids[0]
    selected_id = st.selectbox(
        "Select loan account", ids,
        format_func=lambda x: f"{x} · {_borrower(by_id[x])}", key=widget_key,
        on_change=_sync_selected_account, args=(widget_key,),
    )
    return by_id[selected_id]


def _sync_selected_account(widget_key: str) -> None:
    selected = st.session_state.get(widget_key)
    if selected:
        st.session_state["loan_monitoring_selected_account"] = selected


def _render_overview(records: Sequence[dict[str, Any]], dark: bool) -> None:
    today = date.today()
    duplicate_ids = _duplicate_monitoring_ids(records)
    if duplicate_ids:
        st.warning(f"{len(duplicate_ids)} duplicate or conflicting loan account identifier(s) were excluded from portfolio totals. Resolve IDs before relying on these summaries.")
    summary = build_loan_overview(records, today)
    accounts = summary["accounts"]
    all_types = sorted({str(_monitor(r).get("loan_type") or r.get("loan_product") or "Not specified") for r in accounts})
    all_purposes = sorted({str(r.get("loan_purpose") or r.get("purpose") or "Not specified") for r in accounts})
    f1, f2, f3, f4 = st.columns([1.3, 1, 1, 1])
    with f1:
        selected_dates = st.date_input("Disbursement date range", value=(), key="lm-overview-dates", help="Filters accounts by recorded disbursement date.")
    with f2:
        selected_types = st.multiselect("Loan type", all_types, key="lm-overview-types")
    with f3:
        selected_purposes = st.multiselect("Loan purpose", all_purposes, key="lm-overview-purposes")
    with f4:
        selected_statuses = st.multiselect("Loan status", sorted({str(_monitor(r).get("account_status")) for r in accounts}), key="lm-overview-statuses")
    start, end = (selected_dates[0], selected_dates[-1]) if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2 else (None, None)
    filtered = []
    for record in accounts:
        d = _date(_disbursement(record).get("disbursed_at"))
        typ = str(_monitor(record).get("loan_type") or record.get("loan_product") or "Not specified")
        purpose = str(record.get("loan_purpose") or record.get("purpose") or "Not specified")
        status = str(_monitor(record).get("account_status"))
        if start and d and d < start or end and d and d > end:
            continue
        if selected_types and typ not in selected_types or selected_purposes and purpose not in selected_purposes or selected_statuses and status not in selected_statuses:
            continue
        filtered.append(record)
    summary = build_loan_overview(filtered, today)
    active, repaid = summary["active"], summary["repaid"]
    overdue_count = len(summary["overdue_accounts"]) if summary["overdue_accounts"] is not None else None
    _tab_kpis([
        ("Total Active Loans", str(len(active)), "Disbursed accounts with Active lifecycle status"),
        ("Total Disbursed Amount", _money(summary["disbursed_total"], summary["disbursed_currency"]), "Selected accounts; currency must be consistent"),
        ("Outstanding Loan Balance", _money(summary["outstanding_total"], summary["outstanding_currency"]), "Calculated from principal allocations"),
        ("Overdue Loans", str(overdue_count) if overdue_count is not None else "Not available", "Accounts with at least one unpaid past-due installment"),
        ("Fully Repaid Loans", str(len(repaid)), "Explicit lifecycle status; see repayment balance detail"),
    ])
    if not accounts:
        st.markdown('<div class="lm-empty"><strong>No disbursed loan accounts are available.</strong><br>Shared records contain applications and assessment information, but no explicit authorized disbursement records. Approved applications and analyst recommendations do not qualify.</div>', unsafe_allow_html=True)
    elif not filtered:
        st.info("No disbursed accounts match the selected overview filters.")
    st.markdown("#### Loan Portfolio Summary")
    if filtered:
        by_type = pd.DataFrame([{"Loan type": str(_monitor(r).get("loan_type") or r.get("loan_product") or "Not specified"), "Account status": str(_monitor(r).get("account_status")), "Loan Account ID": _account_id(r), "Outstanding Balance": float(_outstanding_principal(r) or 0), "Currency": _disbursement(r).get("currency")} for r in filtered])
        left, right = st.columns(2)
        with left:
            st.markdown("**Active disbursed loans by type**")
            active_types = by_type[by_type["Account status"].str.casefold() == "active"].groupby("Loan type", as_index=False).size()
            if not active_types.empty:
                fig = px.bar(active_types, x="Loan type", y="size", color_discrete_sequence=["#2563EB"], labels={"size": "Accounts"})
                fig.update_layout(template="plotly_dark" if dark else "plotly_white", height=270, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
                st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            else:
                st.info("No active disbursed loan types match these filters.")
        with right:
            st.markdown("**Portfolio by lifecycle status**")
            status_counts = by_type.groupby("Account status", as_index=False).size()
            fig = px.pie(status_counts, names="Account status", values="size", hole=.6, color_discrete_sequence=["#2563EB", "#94A3B8", "#F59E0B", "#EF4444"])
            fig.update_layout(template="plotly_dark" if dark else "plotly_white", height=270, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.markdown("**Outstanding principal by loan purpose**")
        purpose_rows = []
        for record in filtered:
            amount, currency = _outstanding_principal(record), str(_disbursement(record).get("currency") or "").upper()
            if amount is not None and currency:
                purpose_rows.append({"Loan purpose": record.get("loan_purpose") or record.get("purpose") or "Not specified", "Outstanding principal": float(amount), "Currency": currency})
        if purpose_rows and len({r["Currency"] for r in purpose_rows}) == 1:
            frame = pd.DataFrame(purpose_rows).groupby("Loan purpose", as_index=False)["Outstanding principal"].sum()
            fig = px.bar(frame, x="Loan purpose", y="Outstanding principal", color_discrete_sequence=["#2563EB"])
            fig.update_layout(template="plotly_dark" if dark else "plotly_white", height=260, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Consistent currency and outstanding-balance data are needed for purpose totals.")
        schedule_counts: dict[str, int] = {}
        for record in active:
            for row in _monitor(record).get("repayment_schedule", []):
                if isinstance(row, Mapping):
                    status = schedule_status(row, today)
                    schedule_counts[status] = schedule_counts.get(status, 0) + 1
        st.markdown("**Repayment status distribution**")
        if schedule_counts:
            fig = px.bar(pd.DataFrame({"Payment status": list(schedule_counts), "Installments": list(schedule_counts.values())}), x="Payment status", y="Installments", color_discrete_sequence=["#2563EB"])
            fig.update_layout(template="plotly_dark" if dark else "plotly_white", height=250, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("No repayment schedule information is recorded.")
        risk_rows = []
        for r in filtered:
            assessment = r.get("latest_assessment_summary")
            if not isinstance(assessment, Mapping):
                continue
            risk = assessment.get("risk_category")
            source = str(assessment.get("risk_category_source") or "").casefold()
            if risk and source in {"verified", "validated", "staff-verified", "staff verified"}:
                risk_rows.append({"Risk category": str(risk), "Application ID": r.get("application_id")})
        st.markdown("**Recorded validated assessment risk category**")
        if risk_rows:
            risk_counts = pd.DataFrame(risk_rows).groupby("Risk category", as_index=False).size()
            fig = px.bar(risk_counts, x="Risk category", y="size", labels={"size": "Accounts"}, color_discrete_sequence=["#2563EB"])
            fig.update_layout(template="plotly_dark" if dark else "plotly_white", height=240, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("No validated assessment risk category is recorded for these disbursed accounts; demo source labels and analyst recommendations are not charted as validated risk results.")
        disbursement_history = []
        for r in filtered:
            when = _date(_disbursement(r).get("disbursed_at"))
            currency = str(_disbursement(r).get("currency") or "").upper()
            amount = _decimal(_disbursement(r).get("disbursed_amount"))
            if when and amount is not None and currency:
                disbursement_history.append({"Month": when.strftime("%Y-%m"), "Amount": float(amount), "Currency": currency})
        st.markdown("**Monthly disbursement trend**")
        trend_currencies = {r["Currency"] for r in disbursement_history}
        if disbursement_history and len(trend_currencies) == 1:
            trend = pd.DataFrame(disbursement_history).groupby("Month", as_index=False)["Amount"].sum()
            fig = px.line(trend, x="Month", y="Amount", markers=True, color_discrete_sequence=["#2563EB"])
            fig.update_layout(template="plotly_dark" if dark else "plotly_white", height=250, margin=dict(l=10, r=10, t=10, b=10), yaxis_title=f"Amount ({next(iter(trend_currencies))})")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("No dated disbursement history in one known currency is available for a monthly trend.")
    else:
        st.info("Portfolio charts will appear when eligible disbursed accounts match the selected filters.")
    st.markdown("#### Repayment Performance")
    total_received = summary["total_received"]
    _tab_kpis([
        ("On-time repayment rate", f"{summary['on_time_rate']:.1f}%" if summary["on_time_rate"] is not None else "Not available", "Payments dated on or before their installment due date"),
        ("Late repayment rate", f"{summary['late_rate']:.1f}%" if summary["late_rate"] is not None else "Not available", "Payments dated after their installment due date"),
        ("Missed installments", str(summary["missed_installments"]) if summary["missed_installments"] is not None else "Not available", "Unpaid scheduled installments past due"),
        ("Total payments received", _money(total_received, summary["payment_currency"]), "Sum of recorded transactions only"),
        ("Principal repaid", _money(summary["principal_repaid"], summary["payment_currency"]), "Stored principal allocations"),
        ("Interest received", _money(summary["interest_received"], summary["payment_currency"]), "Stored interest allocations"),
    ])
    if summary["payment_count"]:
        st.caption(f"Payment rate denominator: {summary['payment_count']} recorded transactions with both a payment date and a linked scheduled due date. Interest received is tracked separately when allocations are available.")
    else:
        st.info("No payment transactions with recorded dates are available; repayment rates are not calculated.")
    st.markdown("#### Overdue Summary")
    overdue_total_value = _money(summary["overdue_total"], summary["overdue_currency"])
    max_dpd = f"{summary['max_dpd']} days" if summary["max_dpd"] is not None else "Not available"
    _tab_kpis([
        ("Overdue accounts", str(overdue_count) if overdue_count is not None else "Not available", "Distinct accounts with unpaid past-due installments"),
        ("Total overdue amount", overdue_total_value, "Remaining scheduled installment amounts"),
        ("Maximum Days Past Due", max_dpd, "Oldest unpaid installment across filtered accounts"),
        ("Accounts requiring follow-up", str(sum(_monitor(r).get("follow_up_required") is True for r in active)), "Explicit staff-marked follow-up flag"),
    ])
    st.caption("DPD is calendar days after each installment due date. Multiple overdue installments are counted separately; an account’s DPD uses its oldest unpaid installment. No legal delinquency or default label is inferred.")
    if summary["overdue_rows"] is None and active:
        st.warning("Some active accounts lack complete schedule rows. Aggregate overdue counts and amounts are withheld until schedules are recorded.")
    st.markdown("#### Recent Monitoring Activities")
    if summary["activities"]:
        st.dataframe(pd.DataFrame(summary["activities"]), width="stretch", hide_index=True)
    else:
        st.markdown('<div class="lm-empty">No monitoring activity history has been recorded for these accounts.</div>', unsafe_allow_html=True)


def _render_disbursement_form(records: Sequence[dict[str, Any]]) -> None:
    candidates = []
    for r in records:
        decision = r.get("final_lending_decision")
        if str(r.get("status", "")).casefold() != "approved" or is_disbursed_monitoring_account(r):
            continue
        if isinstance(decision, Mapping) and str(decision.get("status", "")).casefold() != "approved":
            continue
        candidates.append(r)
    if not candidates:
        st.info("No Approved application records are available for recording a documented existing disbursement. This form does not approve loans.")
        return
    st.markdown("#### Record an existing authorized disbursement")
    st.warning("This form records an externally authorized lending decision and actual disbursement supplied by staff. It does not create or approve a lending decision. The existing Approved application status alone is not proof of authorization; enter the formal decision reference.", icon=":material/info:")
    ids = {str(r.get("application_id")): r for r in candidates}
    app_id = st.selectbox("Approved application", list(ids), format_func=lambda x: f"{x} · {_borrower(ids[x])}", key="lm-disburse-application")
    record = ids[app_id]
    decision_data = record.get("final_lending_decision")
    decision_data = decision_data if isinstance(decision_data, Mapping) else {}
    decision_frequency = decision_data.get("repayment_frequency")
    frequency_options = ["Select frequency", *FREQUENCIES]
    frequency_index = frequency_options.index(decision_frequency) if decision_frequency in FREQUENCIES else 0
    existing = _monitor(record)
    if existing.get("disbursement"):
        st.info("Monitoring data already exists for this application. Use account details to review it.")
        return
    if any(existing.get(key) for key in ("repayment_schedule", "payments", "activities", "collection_activities", "promises")):
        st.warning("Existing monitoring history is present without a complete disbursement record. This form is disabled to avoid overwriting that history.")
        return
    with st.form("lm-disbursement-form"):
        st.caption("Staff-entered and unverified until independently checked. Do not record an analyst recommendation as the approval reference.")
        c1, c2, c3 = st.columns(3)
        with c1:
            account_id = st.text_input("Loan Account ID", value=f"LN-{app_id}", key="lm-disbursement-account-id")
            decision_ref = st.text_input("Formal approval decision reference *", value=str(decision_data.get("decision_reference") or ""), key="lm-disbursement-decision-ref")
            approved_amount = st.number_input("Approved loan amount", min_value=0.0, value=float(decision_data.get("approved_amount") or 0), step=500.0, key="lm-disbursement-approved-amount", help="Enter the authorized amount from the formal decision reference; the application request is not used as an approved amount.")
            disbursed_amount = st.number_input("Actual disbursed amount", min_value=0.0, value=0.0, step=500.0, key="lm-disbursement-actual-amount", help="Enter the actual amount released; it is not inferred from the requested amount.")
        with c2:
            currency = st.text_input("Currency code *", value=str(decision_data.get("currency") or ""), max_chars=3, key="lm-disbursement-currency")
            stored_rate = decision_data.get("annual_interest_rate")
            rate = st.number_input("Annual interest rate (%)", min_value=0.0, max_value=100.0, value=float(stored_rate) if stored_rate is not None else None, step=0.25, key="lm-disbursement-rate", help="Enter the rate in the externally authorized loan terms. Zero is accepted when it is the actual approved rate.")
            stored_term = decision_data.get("term_months")
            term = st.number_input("Loan term (months)", min_value=1, max_value=600, value=int(stored_term) if stored_term is not None else None, step=1, key="lm-disbursement-term")
            frequency = st.selectbox("Repayment frequency", frequency_options, index=frequency_index, key="lm-disbursement-frequency")
        with c3:
            disbursed_on = st.date_input("Disbursement date", value=None, key="lm-disbursement-date")
            decision_on = st.date_input("Formal decision date", value=_date(decision_data.get("decision_date")), key="lm-formal-decision-date")
            first_due = st.date_input("First repayment date", value=_date(decision_data.get("first_repayment_date")), key="lm-first-repayment-date")
            recorded_by = st.text_input("Recorded by (optional)", key="lm-disbursement-recorder")
            confirmed = st.checkbox("I confirm these are existing authorized loan terms and an actual disbursement, not an assessment recommendation.", key="lm-disbursement-confirmation")
        submitted = st.form_submit_button("Record disbursement and generate schedule", type="primary")
    if submitted:
        normalized_currency = currency.strip().upper()
        if not confirmed:
            st.error("Confirm the source of the existing authorization and disbursement.")
        elif not decision_ref.strip() or not re.fullmatch(r"[A-Z]{3}", normalized_currency):
            st.error("A formal approval reference and three-letter currency code are required.")
        elif rate is None or term is None or frequency not in FREQUENCIES or disbursed_on is None or decision_on is None or first_due is None:
            st.error("Enter the authorized annual rate (including an explicit 0% if applicable), term, frequency, formal decision date, actual disbursement date, and first repayment date.")
        elif not account_id.strip() or any(r is not record and str(_monitor(r).get("loan_account_id") or "").casefold() == account_id.strip().casefold() for r in records):
            st.error("Loan Account ID is required and must be unique.")
        elif _decimal(disbursed_amount, allow_zero=False) is None or _decimal(approved_amount, allow_zero=False) is None or Decimal(str(disbursed_amount)) > Decimal(str(approved_amount)):
            st.error("Actual disbursed amount must be positive and no greater than the recorded approved amount.")
        elif decision_on > disbursed_on:
            st.error("Formal lending decision date must be on or before the disbursement date.")
        elif first_due <= disbursed_on:
            st.error("First repayment date must be after disbursement.")
        else:
            try:
                schedule = generate_repayment_schedule(disbursed_amount, rate, int(term), frequency, first_due, normalized_currency)
            except ValueError as error:
                st.error(str(error))
            else:
                record["final_lending_decision"] = {
                    **dict(decision_data),
                    "status": "Approved", "decision_reference": decision_ref.strip(),
                    "decision_date": _iso(decision_on), "approved_amount": str(_round_money(Decimal(str(approved_amount)))),
                    "currency": normalized_currency,
                    "source": "Staff-entered reference to an externally authorized decision; verification not recorded",
                }
                record["loan_monitoring"] = {
                    **existing,
                    "loan_account_id": account_id.strip(), "applicant_id": record.get("applicant_id"), "account_status": "Active", "loan_type": record.get("loan_product") or "Not specified",
                    "disbursement": {"status": "Disbursed", "disbursed_at": _iso(disbursed_on), "disbursed_amount": str(_round_money(Decimal(str(disbursed_amount)))), "approved_amount": str(_round_money(Decimal(str(approved_amount)))), "annual_interest_rate": str(Decimal(str(rate))), "term_months": int(term), "repayment_frequency": frequency, "first_repayment_date": _iso(first_due), "maturity_date": schedule[-1]["due_date"], "currency": normalized_currency, "final_decision_reference": decision_ref.strip(), "decision_source": "Staff-entered external authorization reference", "recorded_by": recorded_by.strip() or "Not specified", "source_status": "Staff-entered; verification not recorded"},
                    "outstanding_balance": str(_round_money(Decimal(str(disbursed_amount)))), "repayment_schedule": schedule,
                    "payments": [], "activities": [], "collection_activities": [], "promises": [], "follow_up_required": False,
                }
                _new_event(record, "Loan disbursed", f"Account {account_id.strip()}; reference {decision_ref.strip()}; staff-entered and unverified")
                _new_event(record, "Repayment schedule generated", f"{len(schedule)} {frequency.lower()} installments; fixed-rate amortization")
                st.success("Existing disbursement details recorded on the shared application record and schedule generated.")
                st.rerun()


def _render_accounts(records: Sequence[dict[str, Any]]) -> None:
    accounts = _eligible(records)
    duplicate_ids = _duplicate_monitoring_ids(records)
    if duplicate_ids:
        st.warning(f"Conflicting account/application identifiers were excluded: {', '.join(duplicate_ids)}")
    _render_disbursement_form(records)
    st.divider()
    st.markdown("#### Loan Account Register")
    if not accounts:
        st.info("No explicitly disbursed loan accounts are available. Account tables and actions appear after an existing authorized disbursement is recorded.")
        return
    search = st.text_input("Search account, application ID, or borrower", key="lm-account-search")
    t1, t2, t3 = st.columns(3)
    loan_types = sorted({str(_monitor(r).get("loan_type") or r.get("loan_product") or "Not specified") for r in accounts})
    purposes = sorted({str(r.get("loan_purpose") or r.get("purpose") or "Not specified") for r in accounts})
    statuses = sorted({str(_monitor(r).get("account_status")) for r in accounts})
    with t1: selected_type = st.selectbox("Loan type filter", ["All"] + loan_types, key="lm-account-type-filter")
    with t2: selected_status = st.selectbox("Lifecycle status", ["All"] + statuses, key="lm-account-status-filter")
    with t3: selected_purpose = st.selectbox("Purpose filter", ["All"] + purposes, key="lm-account-purpose-filter")
    filtered = []
    for r in accounts:
        haystack = " ".join([_account_id(r), str(r.get("application_id", "")), _borrower(r)]).casefold()
        if search.casefold() in haystack and (selected_type == "All" or str(_monitor(r).get("loan_type") or r.get("loan_product") or "Not specified") == selected_type) and (selected_status == "All" or str(_monitor(r).get("account_status")) == selected_status) and (selected_purpose == "All" or str(r.get("loan_purpose") or r.get("purpose") or "Not specified") == selected_purpose):
            filtered.append(r)
    if not filtered:
        st.info("No accounts match these filters.")
        return
    rows = [account_monitoring_row(r, date.today()) for r in filtered]
    display = [{k: (str(v) if isinstance(v, Decimal) else _iso(v) if isinstance(v, date) else v) for k, v in row.items() if not k.startswith("_")} for row in rows]
    st.dataframe(pd.DataFrame(display), width="stretch", hide_index=True)
    st.download_button("Export filtered loan accounts (CSV)", pd.DataFrame(display).to_csv(index=False).encode("utf-8-sig"), file_name="loan_accounts.csv", mime="text/csv", key="lm-account-export")
    selected = _account_selector(filtered, "lm-account-detail-selector")
    if selected:
        _render_account_detail(selected)


def _render_account_detail(record: dict[str, Any]) -> None:
    monitoring, disbursement = _monitor(record), _disbursement(record)
    st.markdown(f"#### Account details · {_account_id(record)}")
    st.caption("Internal monitoring view · application data and staff-entered monitoring data remain on the same shared application record.")
    if str(monitoring.get("account_status", "")).casefold() == "fully repaid" and not _repaid_status_matches_balance(record):
        st.warning("The stored Fully Repaid lifecycle status does not reconcile with the calculated principal or scheduled balance. Review the payment records before relying on the status.")
    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown("**Borrower information**")
        st.write({"Borrower": _borrower(record), "Applicant ID": record.get("applicant_id", "Not available"), "Application ID": record.get("application_id"), "Phone": record.get("phone", "Not available"), "Email": record.get("email", "Not available"), "Borrower type": record.get("borrower_type", "Not specified"), "Employment status": record.get("employment_status", "Not available"), "Occupation / employer": record.get("occupation") or record.get("employer", "Not available"), "Business name": record.get("business_name", "Not available"), "Business type": record.get("business_type", "Not available"), "Industry": record.get("industry", "Not available")})
    with b2:
        st.markdown("**Loan information**")
        st.write({"Account ID": _account_id(record), "Approved amount": _money(disbursement.get("approved_amount"), disbursement.get("currency")), "Disbursed amount": _money(disbursement.get("disbursed_amount"), disbursement.get("currency")), "Rate": f"{disbursement.get('annual_interest_rate')}%" if disbursement.get("annual_interest_rate") is not None else "Not available", "Term": f"{disbursement.get('term_months')} months" if disbursement.get("term_months") else "Not available", "Frequency": disbursement.get("repayment_frequency", "Not available"), "Disbursed": disbursement.get("disbursed_at"), "First repayment": disbursement.get("first_repayment_date"), "Maturity": disbursement.get("maturity_date"), "Lifecycle status": monitoring.get("account_status")})
    with b3:
        st.markdown("**Repayment summary**")
        payments = [p for p in monitoring.get("payments", []) if isinstance(p, Mapping)]
        schedule = [s for s in monitoring.get("repayment_schedule", []) if isinstance(s, Mapping)]
        principal_paid = _payment_allocation_total(record, "principal_allocation")
        interest_paid = _payment_allocation_total(record, "interest_allocation")
        overdue, complete = _overdue_rows(record, date.today())
        amount_due = _scheduled_amount_total(record)
        remaining_schedule = _remaining_obligation(record)
        st.write({"Scheduled installments": len(schedule), "Total scheduled amount": _money(amount_due, disbursement.get("currency")), "Payment transactions": len(payments), "Total amount received": _money(_payment_received_total(record), disbursement.get("currency")), "Principal repaid": _money(principal_paid, disbursement.get("currency")), "Interest received": _money(interest_paid, disbursement.get("currency")), "Outstanding principal": _money(_outstanding_principal(record), disbursement.get("currency")), "Remaining scheduled amount": _money(remaining_schedule, disbursement.get("currency")), "Overdue amount": _money(sum((r["remaining_amount"] for r in overdue), Decimal(0)), disbursement.get("currency")) if complete else "Not available", "Next installment": next((s.get("due_date") for s in schedule if _decimal(s.get("amount_paid")) is not None and (_decimal(s.get("amount_due")) or 0) > (_decimal(s.get("amount_paid")) or 0)), "None")})
        st.write({"Outstanding interest": "Not separately accrued in this prototype", "Loan purpose": record.get("loan_purpose") or record.get("purpose") or "Not specified"})
    if schedule and amount_due is not None and remaining_schedule is not None:
        completion = float((amount_due - remaining_schedule) / amount_due) if amount_due else 1.0
        st.markdown("**Repayment progress by scheduled installment value**")
        st.progress(min(1.0, max(0.0, completion)), text=f"{completion:.1%} of scheduled installment value recorded as paid")
    elif schedule:
        st.info("Repayment progress is unavailable because scheduled or paid installment amounts are incomplete.")
    st.caption(f"Authorization reference: {disbursement.get('final_decision_reference', 'Not recorded')} · Source: {disbursement.get('source_status', 'Not specified')}")
    st.markdown("**Recorded account history**")
    events = monitoring.get("activities", [])
    if events:
        st.dataframe(pd.DataFrame(sorted(events, key=lambda e: str(e.get("timestamp", "")), reverse=True)), width="stretch", hide_index=True)
    else:
        st.caption("No account activity has been recorded.")
    st.markdown("**Payment history**")
    payment_rows = monitoring.get("payments", [])
    if payment_rows:
        st.dataframe(pd.DataFrame([{"Transaction ID": p.get("transaction_id"), "Date": p.get("payment_date"), "Received": p.get("amount_received"), "Principal": p.get("principal_allocation"), "Interest": p.get("interest_allocation"), "Reference": p.get("transaction_reference"), "Status": p.get("status")} for p in payment_rows if isinstance(p, Mapping)]), width="stretch", hide_index=True)
    else:
        st.caption("No payments are recorded.")
    st.markdown("**Collection activity history**")
    collection_rows = monitoring.get("collection_activities", [])
    if collection_rows:
        st.dataframe(pd.DataFrame(sorted(collection_rows, key=lambda e: str(e.get("contact_date", "")), reverse=True)), width="stretch", hide_index=True)
    else:
        st.caption("No collection activities are recorded.")


def _payment_id(record: Mapping[str, Any]) -> str:
    return f"PAY-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def allocate_payment(
    record: dict[str, Any], amount: Any, payment_date: date, *,
    method: str = "Not specified", reference: str = "", notes: str = "", recorded_by: str = "Not specified",
) -> dict[str, Any]:
    """Apply a payment to oldest unpaid installments, interest first, without overpayment."""
    value = _decimal(amount, allow_zero=False)
    if value is None:
        raise ValueError("Payment amount must be positive.")
    if payment_date > date.today():
        raise ValueError("Payment date cannot be in the future.")
    monitoring = _monitor(record)
    schedule = monitoring.get("repayment_schedule", [])
    if not _allocation_schedule_complete(record):
        raise ValueError("Payment entry requires a complete schedule with principal, interest, due, and paid amounts for each installment.")
    remaining_obligation = _remaining_obligation(record)
    if value > remaining_obligation:
        raise ValueError("Payment exceeds the remaining scheduled obligation.")
    outstanding_payment = value
    interest_allocated = Decimal(0)
    principal_allocated = Decimal(0)
    linked_due_date = None
    allocations = []
    for installment in schedule:
        due = _decimal(installment.get("amount_due")) or Decimal(0)
        paid = _decimal(installment.get("amount_paid")) or Decimal(0)
        remaining = due - paid
        if remaining <= 0 or outstanding_payment <= 0:
            continue
        applied = min(remaining, outstanding_payment)
        interest_due = _decimal(installment.get("interest_due")) or Decimal(0)
        interest_paid = _decimal(installment.get("interest_paid")) or Decimal(0)
        principal_due = _decimal(installment.get("principal_due")) or Decimal(0)
        principal_paid = _decimal(installment.get("principal_paid")) or Decimal(0)
        to_interest = min(applied, max(Decimal(0), interest_due - interest_paid))
        to_principal = min(applied - to_interest, max(Decimal(0), principal_due - principal_paid))
        installment["interest_paid"] = str(_round_money(interest_paid + to_interest))
        installment["principal_paid"] = str(_round_money(principal_paid + to_principal))
        installment["amount_paid"] = str(_round_money(paid + applied))
        interest_allocated += to_interest
        principal_allocated += to_principal
        outstanding_payment -= applied
        due_date = _date(installment.get("due_date"))
        if due_date and (linked_due_date is None or due_date < linked_due_date):
            linked_due_date = due_date
        allocations.append({"installment_number": installment.get("installment_number"), "due_date": _iso(due_date) if due_date else None, "interest": str(to_interest), "principal": str(to_principal)})
    if outstanding_payment > 0:
        raise ValueError("The repayment schedule could not accept the complete payment.")
    currency = str(_disbursement(record).get("currency") or "").upper()
    payment = {
        "transaction_id": _payment_id(record), "payment_date": _iso(payment_date), "amount_received": str(_round_money(value)),
        "principal_allocation": str(_round_money(principal_allocated)), "interest_allocation": str(_round_money(interest_allocated)),
        "payment_method": method, "transaction_reference": reference.strip(), "notes": notes.strip(),
        "recorded_by": recorded_by.strip() or "Not specified", "status": "Recorded", "due_date": _iso(linked_due_date) if linked_due_date else None,
        "currency": currency, "allocations": allocations,
    }
    monitoring.setdefault("payments", []).append(payment)
    outstanding_principal = _outstanding_principal(record)
    monitoring["outstanding_balance"] = str(outstanding_principal) if outstanding_principal is not None else None
    previous_status = monitoring.get("account_status")
    if outstanding_principal == 0 and _remaining_obligation(record) == 0:
        monitoring["account_status"] = "Fully Repaid"
    _new_event(record, "Payment recorded", f"{payment['transaction_id']} · {currency} {payment['amount_received']} · interest {payment['interest_allocation']}; principal {payment['principal_allocation']}")
    if previous_status != monitoring.get("account_status"):
        _new_event(record, "Loan status updated", "Account marked Fully Repaid after scheduled principal and obligations reached zero")
    return payment


def _schedule_missing_fields(record: Mapping[str, Any], *, allocations: bool = False) -> list[str]:
    schedule = _monitor(record).get("repayment_schedule")
    if not isinstance(schedule, list) or not schedule:
        return ["repayment_schedule"]
    needed = ["due_date", "amount_due", "amount_paid"]
    if allocations:
        needed.extend(["principal_due", "interest_due"])
    missing = []
    for index, row in enumerate(schedule, start=1):
        if not isinstance(row, Mapping):
            missing.append(f"installment {index}: invalid row")
            continue
        missing_fields = [field for field in needed if row.get(field) in (None, "")]
        if missing_fields:
            missing.append(f"installment {index}: {', '.join(missing_fields)}")
    return missing


def _render_existing_schedule_generator(record: dict[str, Any]) -> None:
    monitoring, disbursement = _monitor(record), _disbursement(record)
    account_id = _account_id(record)
    if str(monitoring.get("account_status", "")).casefold() != "active":
        st.info("This account has no schedule and is not Active. A historical schedule must be supplied from the loan record; the app will not reconstruct a Fully Repaid account history.")
        return
    payments = monitoring.get("payments", [])
    if payments:
        st.warning("Payment transactions already exist but no schedule is linked. Import or reconcile the actual historical schedule before recording more payments; a new schedule would change their meaning.")
        return
    missing = []
    stored_rate = _decimal(disbursement.get("annual_interest_rate"))
    stored_term = disbursement.get("term_months")
    stored_frequency = disbursement.get("repayment_frequency")
    first_date = _date(disbursement.get("first_repayment_date"))
    currency = str(disbursement.get("currency") or "").strip().upper()
    if stored_rate is None: missing.append("disbursement.annual_interest_rate")
    if not isinstance(stored_term, int) or stored_term <= 0: missing.append("disbursement.term_months")
    if stored_frequency not in FREQUENCIES: missing.append("disbursement.repayment_frequency")
    if first_date is None: missing.append("disbursement.first_repayment_date")
    if not currency: missing.append("disbursement.currency")
    st.warning("No schedule is linked to this existing disbursed account. Generate one only from the approved loan agreement terms. This will not create a second account or alter the application request.")
    if missing:
        st.info("Missing fields to generate the schedule: " + ", ".join(missing))
    frequency_options = ["Select frequency", *FREQUENCIES]
    frequency_index = frequency_options.index(stored_frequency) if stored_frequency in FREQUENCIES else 0
    with st.form(f"lm-existing-schedule-form-{account_id}"):
        st.caption("Check every term against the authorized loan agreement. Missing values are not inferred from the application request or analyst recommendation.")
        c1, c2, c3 = st.columns(3)
        with c1:
            rate = st.number_input("Authorized annual interest rate (%)", min_value=0.0, max_value=100.0, value=float(stored_rate) if stored_rate is not None else None, step=0.25, key=f"lm-existing-rate-{account_id}")
            term = st.number_input("Authorized term (months)", min_value=1, max_value=600, value=stored_term if isinstance(stored_term, int) and stored_term > 0 else None, step=1, key=f"lm-existing-term-{account_id}")
        with c2:
            frequency = st.selectbox("Authorized repayment frequency", frequency_options, index=frequency_index, key=f"lm-existing-frequency-{account_id}")
            first_due = st.date_input("First repayment date", value=first_date, key=f"lm-existing-first-due-{account_id}")
        with c3:
            confirmed = st.checkbox("I checked these terms against the existing authorized loan documents.", key=f"lm-existing-confirm-{account_id}")
            submit = st.form_submit_button("Generate repayment schedule", type="primary")
    if submit:
        if not confirmed:
            st.error("Confirm that these are the authorized terms for this existing disbursed account.")
        elif rate is None or term is None or frequency not in FREQUENCIES or first_due is None:
            st.error("Annual rate, term, repayment frequency, and first repayment date are required. Enter zero only if the authorized rate is 0%.")
        elif first_due <= (_date(disbursement.get("disbursed_at")) or date.max):
            st.error("First repayment date must be after the recorded disbursement date.")
        elif not currency:
            st.error("Currency is missing from the disbursement record and cannot be inferred. Correct the account currency before generating a schedule.")
        else:
            try:
                generated = generate_repayment_schedule(disbursement.get("disbursed_amount"), rate, int(term), frequency, first_due, currency)
            except (ValueError, TypeError) as error:
                st.error(str(error))
            else:
                disbursement.update({
                    "annual_interest_rate": str(Decimal(str(rate))), "term_months": int(term),
                    "repayment_frequency": frequency, "first_repayment_date": _iso(first_due),
                    "maturity_date": generated[-1]["due_date"],
                    "terms_source": "Staff-confirmed from existing loan documents; independent verification not recorded",
                })
                monitoring["repayment_schedule"] = generated
                _new_event(record, "Repayment schedule generated", f"{len(generated)} {frequency.lower()} installments from confirmed existing disbursement terms")
                st.success("Repayment schedule generated on the existing loan account.")
                st.rerun()


def _render_schedule(records: Sequence[dict[str, Any]]) -> None:
    accounts = _eligible(records)
    st.markdown("#### Repayment Schedule & Payment Tracking")
    if not accounts:
        st.info("No eligible disbursed loan accounts are available. Approved applications are not treated as accounts. Record an existing authorized disbursement in Loan Accounts before scheduling repayments.")
        return
    record = _account_selector(accounts, "lm-schedule-account-selector")
    if not record:
        return
    monitoring, currency = _monitor(record), str(_disbursement(record).get("currency") or "").upper()
    schedule = monitoring.get("repayment_schedule", [])
    if not isinstance(schedule, list):
        st.error("The repayment schedule field is not a list. Preserve the original record and correct/import the schedule before payment entry.")
        schedule = []
    if not schedule:
        _render_existing_schedule_generator(record)
    else:
        rows = []
        for row in schedule:
            if not isinstance(row, Mapping):
                rows.append({"#": "Not available", "Due Date": "Not available", "Opening Principal": "Not available", "Principal Due": "Not available", "Interest Due": "Not available", "Scheduled Installment": "Not available", "Amount Paid": "Not available", "Remaining": "Not available", "Status": "Data incomplete"})
                continue
            due, paid = _decimal(row.get("amount_due")), _decimal(row.get("amount_paid"))
            remaining_amount = max(Decimal(0), due - paid) if due is not None and paid is not None else None
            rows.append({"#": row.get("installment_number", "Not available"), "Due Date": row.get("due_date", "Not available"), "Opening Principal": row.get("opening_principal", "Not available"), "Principal Due": row.get("principal_due", "Not available"), "Interest Due": row.get("interest_due", "Not available"), "Scheduled Installment": str(due) if due is not None else "Not available", "Amount Paid": str(paid) if paid is not None else "Not available", "Remaining": str(remaining_amount) if remaining_amount is not None else "Not available", "Status": schedule_status(row, date.today())})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        total_due = _scheduled_amount_total(record)
        remaining = _remaining_obligation(record)
        paid_total = total_due - remaining if total_due is not None and remaining is not None else None
        principal_paid = _payment_allocation_total(record, "principal_allocation")
        interest_paid = _payment_allocation_total(record, "interest_allocation")
        upcoming = next((r for r in schedule if isinstance(r, Mapping) and _decimal(r.get("amount_due")) is not None and _decimal(r.get("amount_paid")) is not None and _decimal(r.get("amount_due")) > _decimal(r.get("amount_paid"))), None)
        _tab_kpis([
            ("Total Scheduled", _money(total_due, currency), "Recorded schedule total"),
            ("Amount Received", _money(_payment_received_total(record), currency), "Sum of actual recorded payment transactions"),
            ("Principal Repaid", _money(principal_paid, currency), "Interest-first allocation"),
            ("Interest Paid", _money(interest_paid, currency), "Tracked separately from principal"),
            ("Remaining Scheduled", _money(remaining, currency), "No fees or penalties included"),
            ("Payment Completion", f"{float(paid_total / total_due * 100):.1f}%" if paid_total is not None and total_due else "Not available", "Scheduled value marked paid / total scheduled value"),
        ])
        st.caption(f"Next unpaid installment: {upcoming.get('due_date')} · {currency} {upcoming.get('amount_due')}" if upcoming else "No unpaid installment with complete scheduled amounts was found.")
        missing_schedule_fields = _schedule_missing_fields(record, allocations=True)
        if missing_schedule_fields:
            st.warning("Payment entry is disabled because schedule allocation data is incomplete: " + "; ".join(missing_schedule_fields))
    st.markdown("#### Record Payment")
    remaining_total = _remaining_obligation(record)
    if not schedule:
        st.info("No schedule is available yet; generate it from confirmed terms above before recording payments.")
    elif remaining_total is None:
        st.info("Remaining scheduled obligation is unavailable because due or paid amounts are missing or invalid.")
    elif remaining_total == 0:
        st.success("No scheduled obligation remains. Additional payments are not accepted by this prototype.")
    elif not _allocation_schedule_complete(record):
        st.info("A complete schedule with principal and interest allocation fields is required before payment entry. Existing rows are preserved.")
    else:
        refs = {str(p.get("transaction_reference", "")).casefold() for p in monitoring.get("payments", []) if isinstance(p, Mapping) and p.get("transaction_reference")}
        with st.form(f"lm-payment-form-{_account_id(record)}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                pay_date = st.date_input("Payment date", value=date.today(), key=f"lm-pay-date-{_account_id(record)}")
                amount = st.number_input(f"Amount received ({currency})", min_value=0.01, max_value=float(remaining_total), value=min(float(remaining_total), 100.0), step=10.0, key=f"lm-pay-amount-{_account_id(record)}")
            with c2:
                method = st.selectbox("Payment method", ["Not specified", "Bank transfer", "Cash", "Standing instruction", "Other"], key=f"lm-pay-method-{_account_id(record)}")
                reference = st.text_input("Transaction reference (optional)", key=f"lm-pay-ref-{_account_id(record)}")
            with c3:
                notes = st.text_input("Payment notes", key=f"lm-pay-notes-{_account_id(record)}")
                staff = st.text_input("Recorded by", key=f"lm-pay-staff-{_account_id(record)}")
            submit = st.form_submit_button("Record payment", type="primary")
        if submit:
            payment_amount = _decimal(amount, allow_zero=False)
            if pay_date > date.today():
                st.error("Payment date cannot be in the future.")
            elif payment_amount is None or payment_amount > remaining_total:
                st.error(f"Payment must be positive and cannot exceed the remaining scheduled amount ({_money(remaining_total, currency)}).")
            elif reference.strip() and reference.strip().casefold() in refs:
                st.error("This transaction reference already exists for this account.")
            else:
                try:
                    payment = allocate_payment(record, payment_amount, pay_date, method=method, reference=reference, notes=notes, recorded_by=staff)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.success(f"Payment recorded. Allocated {currency} {payment['interest_allocation']} to interest and {currency} {payment['principal_allocation']} to principal.")
                    st.rerun()
    st.markdown("#### Payment History")
    payments = monitoring.get("payments", [])
    if isinstance(payments, list) and payments:
        history = [{"Transaction ID": p.get("transaction_id"), "Payment Date": p.get("payment_date"), "Amount Received": p.get("amount_received"), "Principal Allocation": p.get("principal_allocation"), "Interest Allocation": p.get("interest_allocation"), "Method": p.get("payment_method"), "Reference": p.get("transaction_reference"), "Status": p.get("status"), "Recorded By": p.get("recorded_by")} for p in sorted((x for x in payments if isinstance(x, Mapping)), key=lambda x: str(x.get("payment_date", "")), reverse=True)]
        st.dataframe(pd.DataFrame(history), width="stretch", hide_index=True)
    elif not payments:
        st.info("No payment transactions are recorded for this account.")
    else:
        st.warning("Payment records are malformed and could not be displayed as a transaction history.")
    st.caption("Schedule method: fixed nominal-rate amortization using annual rate × repayment interval / 12; cent-rounded payments with a final principal adjustment. Monthly and quarterly frequencies are supported. Allocation rule: oldest unpaid scheduled installment first; each payment covers remaining scheduled interest before principal. Partial payments are supported. Overpayments, fees, penalties, and reversals are not supported. Payments never imply collection promises are fulfilled.")


def _render_overdue(records: Sequence[dict[str, Any]]) -> None:
    accounts = _eligible(records)
    today = date.today()
    rows = [account_monitoring_row(r, today) for r in accounts if str(_monitor(r).get("account_status")).casefold() == "active"]
    complete_rows = [r for r in rows if r["_schedule_complete"]]
    overdue = [r for r in complete_rows if r["_overdue"]]
    incomplete = [r for r in rows if not r["_schedule_complete"]]
    if incomplete:
        st.warning(f"Overdue totals are withheld for {len(incomplete)} active account(s) with incomplete schedule data.")
    buckets = {name: 0 for name in _AGING}
    for row in overdue:
        buckets[aging_bucket(row["Days Past Due"])] += 1
    overdue_accounts = len(overdue) if len(incomplete) == 0 else None
    overdue_currency = _single_currency([r["_record"] for r in overdue]) if overdue else _single_currency(accounts)
    overdue_amount = sum((sum((x["remaining_amount"] for x in r["_overdue"]), Decimal(0)) for r in overdue), Decimal(0))
    overdue_value = _money(overdue_amount, overdue_currency) if overdue_currency else "Not available" if overdue else "0"
    _tab_kpis([
        ("Total overdue accounts", str(overdue_accounts) if overdue_accounts is not None else "Incomplete data", "Complete schedules only"),
        ("Total overdue amount", overdue_value, "Unpaid installment amounts"),
        ("1–30 Days Past Due", str(buckets[_AGING[1]]), "Oldest unpaid installment per account"),
        ("31–60 Days Past Due", str(buckets[_AGING[2]]), "Oldest unpaid installment per account"),
        ("61–90 Days Past Due", str(buckets[_AGING[3]]), "Oldest unpaid installment per account"),
        ("More Than 90 Days Past Due", str(buckets[_AGING[4]]), "Oldest unpaid installment per account"),
    ])
    st.caption("Aging uses the oldest installment that still has an unpaid scheduled amount. DPD is today minus that due date in calendar days. This is not a legal delinquency or default classification.")
    selected_bucket = st.selectbox("Filter by aging category", ["All"] + list(_AGING), key="lm-overdue-aging")
    filtered = [r for r in overdue if selected_bucket == "All" or aging_bucket(r["Days Past Due"]) == selected_bucket]
    st.markdown("#### Overdue Accounts")
    if filtered:
        table = [{k: v for k, v in r.items() if not k.startswith("_")} for r in filtered]
        st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)
        st.markdown("#### Overdue Account Details")
        selected = _account_selector([r["_record"] for r in filtered], "lm-overdue-account-selector")
        if selected:
            _render_account_detail(selected)
            st.markdown("**Unpaid installments**")
            arrears, _ = _overdue_rows(selected, today)
            st.dataframe(pd.DataFrame([{ "Installment": r.get("installment_number"), "Due date": r.get("due_date"), "Amount due": r.get("amount_due"), "Amount paid": r.get("amount_paid"), "Remaining overdue": str(r["remaining_amount"]), "DPD": r["days_past_due"]} for r in arrears]), width="stretch", hide_index=True)
            st.markdown("**Monitoring alert**")
            if _monitor(selected).get("follow_up_required") is True:
                st.warning("Staff has marked this account as requiring follow-up.")
            else:
                st.info("No follow-up flag is recorded. No automatic policy threshold is configured.")
    elif not accounts:
        st.info("No disbursed accounts are available to monitor.")
    elif incomplete:
        st.info("Complete repayment schedules are needed to identify and age overdue installments reliably.")
    else:
        st.success("No overdue installments match the selected aging filter.")
    st.markdown("#### Accounts Without Follow-up")
    without = [r for r in overdue if not _monitor(r["_record"]).get("follow_up_required")]
    st.dataframe(pd.DataFrame([{"Loan Account ID": r["Loan Account ID"], "Borrower": r["Applicant / Business"], "Overdue Amount": str(sum((x["remaining_amount"] for x in r["_overdue"]), Decimal(0))), "DPD": r["Days Past Due"]} for r in without]) if without else pd.DataFrame(columns=["Loan Account ID", "Borrower", "Overdue Amount", "DPD"]), width="stretch", hide_index=True)


def _single_currency(records: Sequence[Mapping[str, Any]]) -> str | None:
    currencies = {str(_disbursement(r).get("currency") or "").upper() for r in records}
    return next(iter(currencies)) if len(currencies) == 1 and "" not in currencies else None


def _render_collection(records: Sequence[dict[str, Any]]) -> None:
    accounts = _eligible(records)
    today = date.today()
    activities = _activity_table(accounts)
    followup_records = [r for r in accounts if _monitor(r).get("follow_up_required") is True]
    overdue_records = []
    for record in accounts:
        rows, complete = _overdue_rows(record, today)
        if complete and rows:
            overdue_records.append(record)
    overdue_without = [r for r in overdue_records if _monitor(r).get("follow_up_required") is not True]
    all_promises = [(r, p) for r in accounts for p in _monitor(r).get("promises", []) if isinstance(p, Mapping)]
    upcoming = [a for a in activities.to_dict("records") if _date(a.get("Next Follow-up")) and _date(a.get("Next Follow-up")) >= today]
    due_today = [a for a in activities.to_dict("records") if _date(a.get("Next Follow-up")) == today]
    completed = [a for a in activities.to_dict("records") if _date(a.get("Date")) is not None and bool(a.get("Outcome"))]
    _tab_kpis([
        ("Accounts Requiring Follow-up", str(len(followup_records)), "Explicit staff follow-up flag"),
        ("Upcoming Follow-ups", str(len(upcoming)), "Recorded next contact date today or later"),
        ("Overdue Without Follow-up", str(len(overdue_without)), "Overdue accounts without explicit follow-up flag"),
        ("Completed Follow-ups", str(len(completed)), "Activities with successful-contact outcome"),
        ("Promise-to-Pay Records", str(len(all_promises)), "Promises are not recorded payments"),
        ("Follow-ups Due Today", str(len(due_today)), "Recorded next contact date is today"),
    ])
    st.markdown("#### Collection Case List")
    if activities.empty and not followup_records:
        st.info("No collection cases or follow-up activities have been recorded.")
    case_rows = []
    for record in accounts:
        over, complete = _overdue_rows(record, today)
        if over or _monitor(record).get("follow_up_required") is True or _monitor(record).get("collection_activities"):
            detail = account_monitoring_row(record, today)
            case_rows.append({"Loan Account ID": _account_id(record), "Borrower": _borrower(record), "Overdue Amount": str(sum((r["remaining_amount"] for r in over), Decimal(0))) if complete else "Not available", "Currency": _disbursement(record).get("currency", "Not specified"), "DPD": detail["Days Past Due"], "Last Contact Date": max((str(a.get("contact_date")) for a in _monitor(record).get("collection_activities", []) if isinstance(a, Mapping)), default="Not recorded"), "Next Follow-up Date": max((str(a.get("next_follow_up_date")) for a in _monitor(record).get("collection_activities", []) if isinstance(a, Mapping) and a.get("next_follow_up_date")), default="Not recorded"), "Collection Status": _monitor(record).get("collection_status", "Not assigned"), "Assigned Staff": max((str(a.get("assigned_staff")) for a in _monitor(record).get("collection_activities", []) if isinstance(a, Mapping) and a.get("assigned_staff")), default="Not assigned")})
    if case_rows:
        cf1, cf2 = st.columns(2)
        with cf1:
            case_query = st.text_input("Search collection cases", key="lm-collection-case-search").casefold()
        case_statuses = sorted({str(r["Collection Status"]) for r in case_rows})
        with cf2:
            case_status = st.selectbox("Collection status filter", ["All"] + case_statuses, key="lm-collection-case-filter")
        visible_cases = [r for r in case_rows if case_query in " ".join(str(r.get(k, "")) for k in ("Loan Account ID", "Borrower", "Assigned Staff")).casefold() and (case_status == "All" or r["Collection Status"] == case_status)]
        st.dataframe(pd.DataFrame(visible_cases), width="stretch", hide_index=True)
    if accounts:
        record = _account_selector(accounts, "lm-collection-account-selector")
        monitoring = _monitor(record)
        st.markdown("#### Record Collection Activity")
        with st.form(f"lm-collection-form-{_account_id(record)}"):
            c1, c2 = st.columns(2)
            with c1:
                contact_date = st.date_input("Contact date", value=today, key=f"lm-contact-date-{_account_id(record)}")
                method = st.selectbox("Contact method", ["Phone", "Email", "In-person", "Other"], key=f"lm-contact-method-{_account_id(record)}")
                outcome = st.selectbox("Contact outcome", ["Successfully Contacted", "No Response", "Borrower Requested More Time", "Payment Promise Received", "Payment Arrangement Discussed", "Unable to Contact", "Other"], key=f"lm-contact-outcome-{_account_id(record)}")
            with c2:
                response = st.text_area("Borrower response", key=f"lm-contact-response-{_account_id(record)}")
                notes = st.text_area("Follow-up notes", key=f"lm-contact-notes-{_account_id(record)}")
                next_date = st.date_input("Next follow-up date (optional)", value=None, key=f"lm-next-contact-{_account_id(record)}")
                assigned = st.text_input("Assigned staff (optional)", key=f"lm-assigned-{_account_id(record)}")
            record_activity = st.form_submit_button("Save collection activity", type="primary")
        if record_activity:
            if contact_date > today or (next_date and next_date < contact_date):
                st.error("Contact date cannot be in the future and next follow-up cannot precede contact date.")
            elif not response.strip() and not notes.strip():
                st.error("Enter a borrower response or follow-up note to preserve a useful history record.")
            else:
                item = {"activity_id": f"COL-{uuid.uuid4().hex[:10].upper()}", "contact_date": _iso(contact_date), "method": method, "outcome": outcome, "response": response.strip(), "notes": notes.strip(), "next_follow_up_date": _iso(next_date) if next_date else None, "assigned_staff": assigned.strip() or None, "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds")}
                monitoring.setdefault("collection_activities", []).append(item)
                monitoring["follow_up_required"] = bool(next_date or outcome in {"Payment Promise Received", "Borrower Requested More Time", "Payment Arrangement Discussed"})
                monitoring["collection_status"] = "Follow-up scheduled" if next_date else "Contact recorded"
                _new_event(record, "Collection activity recorded", f"{method} · {outcome}")
                st.success("Collection activity saved. It does not alter payment or balance records.")
                st.rerun()
        st.markdown("#### Record Promise to Pay")
        with st.form(f"lm-promise-form-{_account_id(record)}"):
            c1, c2 = st.columns(2)
            with c1:
                promised_amount = st.number_input(f"Promised amount ({_disbursement(record).get('currency', '')})", min_value=0.01, step=10.0, key=f"lm-promise-amount-{_account_id(record)}")
                promised_date = st.date_input("Promised payment date", value=today + timedelta(days=7), key=f"lm-promise-date-{_account_id(record)}")
            with c2:
                promise_notes = st.text_input("Promise notes", key=f"lm-promise-notes-{_account_id(record)}")
                promise_status = st.selectbox("Initial promise status", ["Pending", "Cancelled"], key=f"lm-promise-status-{_account_id(record)}")
            save_promise = st.form_submit_button("Save promise record")
        if save_promise:
            value = _decimal(promised_amount, allow_zero=False)
            if value is None:
                st.error("Promised payment amount must be positive.")
            elif promised_date < today:
                st.error("Promised payment date cannot be in the past when creating a promise.")
            else:
                promise = {"promise_id": f"PTP-{uuid.uuid4().hex[:10].upper()}", "amount": str(_round_money(value)), "currency": _disbursement(record).get("currency"), "promised_date": _iso(promised_date), "status": promise_status, "notes": promise_notes.strip(), "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds")}
                monitoring.setdefault("promises", []).append(promise)
                _new_event(record, "Promise recorded", f"{promise['currency']} {promise['amount']} due {promise['promised_date']}; not a payment")
                st.success("Promise recorded separately from payment transactions.")
                st.rerun()
        st.markdown("#### Promise Status Updates")
        promises = monitoring.get("promises", [])
        if promises:
            for index, promise in enumerate(promises):
                with st.form(f"lm-promise-update-{_account_id(record)}-{index}"):
                    st.write(f"{promise.get('promise_id')} · {_money(promise.get('amount'), promise.get('currency'))} · due {promise.get('promised_date')} · current: {promise.get('status')}")
                    new_status = st.selectbox("Update status", ["Pending", "Fulfilled", "Partially Fulfilled", "Broken", "Cancelled"], index=["Pending", "Fulfilled", "Partially Fulfilled", "Broken", "Cancelled"].index(promise.get("status", "Pending")) if promise.get("status") in ["Pending", "Fulfilled", "Partially Fulfilled", "Broken", "Cancelled"] else 0, key=f"lm-promise-state-{_account_id(record)}-{index}")
                    save = st.form_submit_button("Update promise status")
                if save:
                    promise["status"] = new_status
                    promise["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
                    _new_event(record, "Loan status updated", f"Promise {promise.get('promise_id')} set to {new_status} by staff action")
                    st.success("Promise status updated. This does not change payment totals.")
                    st.rerun()
        else:
            st.info("No promise-to-pay records exist for this account.")
    else:
        st.info("Collection entry requires an explicitly disbursed account.")
    st.markdown("#### Collection History")
    if not activities.empty:
        st.dataframe(activities, width="stretch", hide_index=True)
    else:
        st.info("No collection activity history is available.")


def _report_pdf(lines: Sequence[str]) -> bytes:
    """Generate a small standard-font PDF report using only the Python standard library."""
    def esc(text: str) -> str:
        ascii_text = text.encode("ascii", "replace").decode("ascii")
        return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    wrapped = []
    for line in lines:
        wrapped.extend(textwrap.wrap(str(line), width=92) or [""])
    chunks = [wrapped[i:i + 48] for i in range(0, max(1, len(wrapped)), 48)]
    objects: list[bytes] = []
    page_ids = []
    font_id = 3
    for idx, chunk in enumerate(chunks):
        page_id, content_id = 4 + idx * 2, 5 + idx * 2
        page_ids.append(page_id)
        stream = "BT\n/F1 10 Tf\n50 790 Td\n14 TL\n" + "\n".join(f"({esc(line)}) Tj T*" for line in chunk) + "\nET"
        stream_bytes = stream.encode("ascii")
        objects.extend([
            f"{page_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >> endobj\n".encode(),
            f"{content_id} 0 obj << /Length {len(stream_bytes)} >> stream\n".encode() + stream_bytes + b"\nendstream endobj\n",
        ])
    base = [b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n", f"2 0 obj << /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] /Count {len(page_ids)} >> endobj\n".encode(), b"3 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"]
    body = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in base + objects:
        offsets.append(len(body)); body.extend(obj)
    xref = len(body)
    body.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode())
    body.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(body)


def _report_rows(records: Sequence[dict[str, Any]], today: date, start: date | None, end: date | None, loan_type: str, purpose: str, status: str, aging: str, collection_status: str) -> list[dict[str, Any]]:
    rows = []
    for record in _eligible(records):
        row = account_monitoring_row(record, today)
        disb_date = row["Disbursement Date"]
        if start and (disb_date is None or disb_date < start) or end and (disb_date is None or disb_date > end):
            continue
        if loan_type != "All" and row["Loan Type"] != loan_type or purpose != "All" and row["Loan Purpose"] != purpose or status != "All" and row["Loan Status"] != status or collection_status != "All" and row["Collection Status"] != collection_status:
            continue
        bucket = aging_bucket(row["Days Past Due"] or 0) if row["_schedule_complete"] else "Not available"
        if aging != "All" and bucket != aging:
            continue
        rows.append(row)
    return rows


def _render_reports(records: Sequence[dict[str, Any]], dark: bool) -> None:
    st.markdown("#### Internal Loan Monitoring Report")
    st.caption("Internal Monitoring Report — For Review Purposes Only · Not an official bank statement or final lending decision.")
    accounts = _eligible(records)
    types = sorted({str(_monitor(r).get("loan_type") or r.get("loan_product") or "Not specified") for r in accounts})
    purposes = sorted({str(r.get("loan_purpose") or r.get("purpose") or "Not specified") for r in accounts})
    statuses = sorted({str(_monitor(r).get("account_status")) for r in accounts})
    c1, c2, c3 = st.columns(3)
    with c1: period = st.date_input("Reporting disbursement period", value=(), key="lm-report-period")
    with c2: loan_type = st.selectbox("Report loan type", ["All"] + types, key="lm-report-type")
    with c3: purpose = st.selectbox("Report loan purpose", ["All"] + purposes, key="lm-report-purpose")
    c4, c5, c6 = st.columns(3)
    with c4: status = st.selectbox("Report lifecycle status", ["All"] + statuses, key="lm-report-status")
    with c5: aging = st.selectbox("Report aging", ["All"] + list(_AGING) + ["Not available"], key="lm-report-aging")
    collection_options = sorted({str(_monitor(r).get("collection_status", "Not assigned")) for r in accounts})
    with c6: collection = st.selectbox("Report collection status", ["All"] + collection_options, key="lm-report-collection")
    start, end = (period[0], period[-1]) if isinstance(period, (tuple, list)) and len(period) == 2 else (None, None)
    rows = _report_rows(records, date.today(), start, end, loan_type, purpose, status, aging, collection)
    filtered_records = [r["_record"] for r in rows]
    summary = build_loan_overview(filtered_records, date.today())
    disbursed_text = _money(summary["disbursed_total"], summary["disbursed_currency"])
    outstanding_text = _money(summary["outstanding_total"], summary["outstanding_currency"])
    _tab_kpis([
        ("Disbursed portfolio", disbursed_text, "Filtered accounts"),
        ("Outstanding principal", outstanding_text, "From actual principal allocations"),
        ("Active / repaid", f"{len(summary['active'])} / {len(summary['repaid'])}", "Lifecycle status counts"),
        ("Payments received", _money(summary["total_received"], summary["payment_currency"]), "Transactions only"),
        ("Principal / interest repaid", f"{_money(summary['principal_repaid'], summary['payment_currency'])} / {_money(summary['interest_received'], summary['payment_currency'])}", "Tracked allocations"),
        ("Overdue accounts / amount", f"{len(summary['overdue_accounts']) if summary['overdue_accounts'] is not None else 'N/A'} / {_money(summary['overdue_total'], summary['overdue_currency'])}", "Unpaid past-due schedule values"),
    ])
    if not rows and not accounts:
        st.info("No eligible disbursed loan accounts are available for reporting. Applications and analyst recommendations are not monitored loans; record an authorized disbursement in Loan Accounts first.")
    elif not rows:
        st.info("No disbursed accounts match the selected report filters. Clear or widen the reporting period and other filters to include eligible accounts.")
    else:
        st.markdown("**Portfolio by loan type, purpose, and lifecycle status**")
        portfolio = pd.DataFrame([{"Loan Account ID": r["Loan Account ID"], "Application ID": r["Application ID"], "Borrower": r["Applicant / Business"], "Loan Type": r["Loan Type"], "Purpose": r["Loan Purpose"], "Status": r["Loan Status"], "Currency": r["Currency"], "Disbursed Amount": str(r["Disbursed Amount"]), "Outstanding Principal": str(r["Outstanding Balance"]), "Overdue Amount": str(r["Overdue Amount"]) if r["Overdue Amount"] is not None else "Not available", "DPD": r["Days Past Due"], "Follow-up": r["Follow-up Required"]} for r in rows])
        st.dataframe(portfolio, width="stretch", hide_index=True)
        left, right = st.columns(2)
        with left:
            st.markdown("**Loan type distribution**")
            chart_data = portfolio.groupby("Loan Type", as_index=False).size()
            fig = px.bar(chart_data, x="Loan Type", y="size", labels={"size": "Accounts"}, color_discrete_sequence=["#2563EB"])
            fig.update_layout(template="plotly_dark" if dark else "plotly_white", height=260, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        with right:
            st.markdown("**Lifecycle status distribution**")
            chart_data = portfolio.groupby("Status", as_index=False).size()
            fig = px.pie(chart_data, names="Status", values="size", hole=.6)
            fig.update_layout(template="plotly_dark" if dark else "plotly_white", height=260, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        aging_counts = {bucket: 0 for bucket in _AGING}
        for row in rows:
            if row["_schedule_complete"]:
                aging_counts[aging_bucket(row["Days Past Due"] or 0)] += 1
        st.markdown("**Overdue aging distribution**")
        st.dataframe(pd.DataFrame([{"Aging bucket": k, "Accounts": v} for k, v in aging_counts.items()]), width="stretch", hide_index=True)
        overdue_type_rows = []
        for row in rows:
            amount = row["Overdue Amount"]
            if amount is not None and amount > 0:
                overdue_type_rows.append({"Loan Type": row["Loan Type"], "Currency": row["Currency"], "Overdue Amount": float(amount)})
        st.markdown("**Overdue amount by loan type and currency**")
        if overdue_type_rows:
            overdue_type = pd.DataFrame(overdue_type_rows).groupby(["Loan Type", "Currency"], as_index=False)["Overdue Amount"].sum()
            st.dataframe(overdue_type, width="stretch", hide_index=True)
        else:
            st.info("No overdue installment amounts are available in the filtered portfolio.")
        payment_lines = [(r, p) for r in filtered_records for p in _monitor(r).get("payments", []) if isinstance(p, Mapping)]
        dated_payments = []
        for payment_record, payment in payment_lines:
            payment_date = _date(payment.get("payment_date"))
            amount = _decimal(payment.get("amount_received"))
            # Older transaction rows may omit currency; the owning disbursed account is authoritative.
            currency_value = str(payment.get("currency") or _disbursement(payment_record).get("currency") or "").upper()
            if payment_date and amount is not None and currency_value:
                dated_payments.append({"Month": payment_date.strftime("%Y-%m"), "Amount": float(amount), "Currency": currency_value})
        st.markdown("**Recorded payment trend for selected accounts**")
        payment_currencies = {p["Currency"] for p in dated_payments}
        if dated_payments and len(payment_currencies) == 1:
            trend = pd.DataFrame(dated_payments).groupby("Month", as_index=False)["Amount"].sum()
            fig = px.line(trend, x="Month", y="Amount", markers=True, color_discrete_sequence=["#2563EB"])
            fig.update_layout(template="plotly_dark" if dark else "plotly_white", height=250, margin=dict(l=10, r=10, t=10, b=10), yaxis_title=f"Received ({next(iter(payment_currencies))})")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("No dated payment transactions in one known currency are available for a trend.")
        st.caption(f"Payment counts and totals use recorded payment transactions. On-time and late rates compare each transaction date with its linked installment due date; rate denominators exclude transactions without both dates. Successful contact rate is successfully contacted activities divided by all recorded collection activities. Promise fulfillment is not inferred from collection notes.")
        contact_records = [(r, a) for r in filtered_records for a in _monitor(r).get("collection_activities", []) if isinstance(a, Mapping)]
        success_rate = (sum(str(a.get("outcome", "")).casefold() == "successfully contacted" for _, a in contact_records) / len(contact_records) * 100) if contact_records else None
        promise_records = [p for r in filtered_records for p in _monitor(r).get("promises", []) if isinstance(p, Mapping)]
        fulfilled_rate = (sum(p.get("status") == "Fulfilled" for p in promise_records) / len(promise_records) * 100) if promise_records else None
        _tab_kpis([
            ("On-time / late rate", f"{summary['on_time_rate']:.1f}% / {summary['late_rate']:.1f}%" if summary["on_time_rate"] is not None else "Not available", "Dated linked transactions"),
            ("Missed installments", str(summary["missed_installments"]) if summary["missed_installments"] is not None else "Not available", "Complete schedules only"),
            ("Collection activities", str(len(contact_records)), "Staff-entered history"),
            ("Successful contact rate", f"{success_rate:.1f}%" if success_rate is not None else "Not available", "Successful / recorded contacts"),
            ("Contact activities completed / scheduled follow-ups", f"{sum(bool(a.get('contact_date')) and bool(a.get('outcome')) for _, a in contact_records)} / {sum(bool(a.get('next_follow_up_date')) and (_date(a.get('next_follow_up_date')) or date.min) >= date.today() for _, a in contact_records)}", "Saved contact attempts / future or due dates"),
            ("Promise fulfillment rate", f"{fulfilled_rate:.1f}%" if fulfilled_rate is not None else "Not available", "Fulfilled status / all promises"),
        ])
    report_contacts = [(r, a) for r in filtered_records for a in _monitor(r).get("collection_activities", []) if isinstance(a, Mapping)]
    report_promises = [p for r in filtered_records for p in _monitor(r).get("promises", []) if isinstance(p, Mapping)]
    report_contact_rate = (sum(str(a.get("outcome", "")).casefold() == "successfully contacted" for _, a in report_contacts) / len(report_contacts) * 100) if report_contacts else None
    report_promise_rate = (sum(p.get("status") == "Fulfilled" for p in report_promises) / len(report_promises) * 100) if report_promises else None
    overdue_total_text = _money(summary["overdue_total"], summary["overdue_currency"])
    report_lines = [
        "Internal Monitoring Report - For Review Purposes Only",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='minutes')}",
        f"Filters: Period {start or 'all'} to {end or 'all'}; Type {loan_type}; Purpose {purpose}; Status {status}; Aging {aging}; Collection {collection}",
        f"Disbursed portfolio: {disbursed_text}", f"Outstanding principal: {outstanding_text}",
        f"Active accounts: {len(summary['active'])}; fully repaid: {len(summary['repaid'])}",
        f"Payments received: {_money(summary['total_received'], summary['payment_currency'])}",
        f"Principal repaid: {_money(summary['principal_repaid'], summary['payment_currency'])}",
        f"Interest received: {_money(summary['interest_received'], summary['payment_currency'])}",
        f"On-time repayment rate: {summary['on_time_rate']:.1f}%" if summary["on_time_rate"] is not None else "On-time repayment rate: Not available",
        f"Late repayment rate: {summary['late_rate']:.1f}%" if summary["late_rate"] is not None else "Late repayment rate: Not available",
        f"Missed installments: {summary['missed_installments']}" if summary["missed_installments"] is not None else "Missed installments: Not available",
        f"Overdue accounts: {len(summary['overdue_accounts'])}" if summary["overdue_accounts"] is not None else "Overdue accounts: Not available",
        f"Overdue scheduled amount: {overdue_total_text}",
        f"Maximum DPD: {summary['max_dpd']} days" if summary["max_dpd"] is not None else "Maximum DPD: Not available",
        f"Collection activities: {len(report_contacts)}",
        f"Successful contact rate: {report_contact_rate:.1f}%" if report_contact_rate is not None else "Successful contact rate: Not available",
        f"Promise fulfillment rate: {report_promise_rate:.1f}%" if report_promise_rate is not None else "Promise fulfillment rate: Not available",
        "Accounts:",
    ]
    for r in rows:
        report_lines.append(f"{r['Loan Account ID']} | {r['Application ID']} | {r['Applicant / Business']} | {r['Loan Type']} | {r['Loan Status']} | Disbursed {_money(r['Disbursed Amount'], r['Currency'])} | Outstanding {_money(r['Outstanding Balance'], r['Currency'])} | Overdue {_money(r['Overdue Amount'], r['Currency'])}")
    st.markdown("#### Export filtered report")
    export_rows = [{k: (float(v) if isinstance(v, Decimal) else _iso(v) if isinstance(v, date) else v) for k, v in r.items() if not k.startswith("_")} for r in rows]
    csv = pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8-sig") if export_rows else b""
    e1, e2, e3 = st.columns(3)
    with e1:
        st.download_button("Download filtered CSV", csv, file_name="loan_monitoring_report.csv", mime="text/csv", disabled=not export_rows, key="lm-report-csv")
    with e2:
        excel = io.BytesIO()
        if export_rows:
            with pd.ExcelWriter(excel, engine="openpyxl") as writer:
                pd.DataFrame(export_rows).to_excel(writer, index=False, sheet_name="Loan Portfolio")
                pd.DataFrame(report_lines, columns=["Internal Report Summary"]).to_excel(writer, index=False, sheet_name="Summary")
        st.download_button("Download filtered Excel", excel.getvalue(), file_name="loan_monitoring_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", disabled=not export_rows, key="lm-report-xlsx")
    with e3:
        st.download_button("Download filtered PDF", _report_pdf(report_lines), file_name="loan_monitoring_report.pdf", mime="application/pdf", disabled=not export_rows, key="lm-report-pdf")


def render() -> None:
    dark = bool(st.session_state.get("dark_mode", False))
    st.markdown(_page_styles(dark), unsafe_allow_html=True)
    with st.container(key="loan-monitoring-page"):
        st.markdown('<div class="lm-header"><h1 class="lm-title">Loan Portfolio Monitoring</h1><p class="lm-subtitle">Monitor disbursed loans, repayment performance, outstanding balances, and borrower follow-up activities.</p></div>', unsafe_allow_html=True)
        records = _all_records()
        overview, accounts, schedule, overdue, follow_up, reports = st.tabs(["Loan Overview", "Loan Accounts", "Repayment Schedule", "Overdue Monitoring", "Collection & Follow-up", "Monitoring Reports"])
        with overview:
            _render_overview(records, dark)
        with accounts:
            _render_accounts(records)
        with schedule:
            _render_schedule(records)
        with overdue:
            _render_overdue(records)
        with follow_up:
            _render_collection(records)
        with reports:
            _render_reports(records, dark)
