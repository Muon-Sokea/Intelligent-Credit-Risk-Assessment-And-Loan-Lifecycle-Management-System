"""Financial, repayment, and risk calculation helpers for FinGuard AI."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def monthly_loan_payment(principal: float, annual_rate_pct: float, months: int) -> float:
    """Calculate fixed monthly installment for an amortizing loan."""
    if principal < 0 or annual_rate_pct < 0 or months <= 0:
        raise ValueError("Principal and rate must be non-negative and months positive.")
    if principal == 0:
        return 0.0
    monthly_rate = (annual_rate_pct / 100.0) / 12.0
    if monthly_rate == 0:
        return round(principal / months, 2)
    payment = principal * monthly_rate / (1.0 - (1.0 + monthly_rate) ** (-months))
    return round(payment, 2)


def debt_to_income_ratio(monthly_debt: float, monthly_income: float) -> float:
    """Return debt-to-income ratio as a percentage (0-100+)."""
    if monthly_income <= 0:
        return 0.0
    return round((max(monthly_debt, 0.0) / monthly_income) * 100.0, 2)


def debt_service_coverage_ratio(
    net_operating_income: float, total_debt_service: float
) -> float | None:
    """Return DSCR (NOI / total debt service) for business borrowers."""
    if total_debt_service <= 0:
        return None
    return round(net_operating_income / total_debt_service, 2)


def build_amortization_schedule(
    principal: float,
    annual_rate_pct: float,
    months: int,
    first_due_date: date,
    paid_installments: int = 0,
    partial_payment: float = 0.0,
) -> list[dict[str, Any]]:
    """Generate a fixed-rate monthly amortization schedule."""
    if principal <= 0 or months <= 0:
        return []
    monthly_rate = (annual_rate_pct / 100.0) / 12.0
    installment = monthly_loan_payment(principal, annual_rate_pct, months)
    balance = round(principal, 2)
    schedule: list[dict[str, Any]] = []

    for idx in range(1, months + 1):
        due = first_due_date + timedelta(days=30 * (idx - 1))
        interest = round(balance * monthly_rate, 2)
        if idx == months:
            sched_principal = round(balance, 2)
            total_due = round(sched_principal + interest, 2)
        else:
            sched_principal = round(min(balance, max(installment - interest, 0.0)), 2)
            total_due = round(sched_principal + interest, 2)

        opening = balance
        balance = round(max(balance - sched_principal, 0.0), 2)

        if idx <= paid_installments:
            paid = total_due
            status = "Paid"
        elif idx == paid_installments + 1 and partial_payment > 0:
            paid = round(min(partial_payment, total_due), 2)
            status = "Paid" if paid >= total_due else "Partial"
        else:
            paid = 0.0
            status = "Unpaid"

        schedule.append(
            {
                "installment_no": idx,
                "due_date": due,
                "opening_balance": opening,
                "scheduled_principal": sched_principal,
                "scheduled_interest": interest,
                "total_due": total_due,
                "amount_paid": paid,
                "remaining_due": round(max(total_due - paid, 0.0), 2),
                "closing_balance": balance,
                "status": status,
            }
        )
    return schedule


def calculate_dpd_and_bucket(
    schedule: list[dict[str, Any]], as_of: date | None = None
) -> tuple[int, str, float]:
    """Return (days_past_due, aging_bucket, overdue_amount) from a schedule."""
    today = as_of or date.today()
    max_dpd = 0
    overdue_amount = 0.0

    for row in schedule:
        remaining = float(row.get("remaining_due", 0.0))
        due = row.get("due_date")
        if remaining > 0.01 and isinstance(due, date) and due < today:
            dpd = (today - due).days
            if dpd > max_dpd:
                max_dpd = dpd
            overdue_amount += remaining

    overdue_amount = round(overdue_amount, 2)
    if max_dpd == 0:
        bucket = "Current"
    elif max_dpd <= 30:
        bucket = "1-30 DPD"
    elif max_dpd <= 60:
        bucket = "31-60 DPD"
    elif max_dpd <= 90:
        bucket = "61-90 DPD"
    else:
        bucket = "90+ DPD"
    return max_dpd, bucket, overdue_amount


def illustrative_risk_assessment(record: dict[str, Any]) -> dict[str, Any]:
    """Compute transparent, illustrative rule-based risk indicators (decision support only).

    Avoids penalizing thin-file applicants solely for missing traditional credit history.
    """
    income = max(float(record.get("monthly_income", 0.0)), 1.0)
    expenses = float(record.get("monthly_expenses", 0.0))
    existing_debt_payment = float(record.get("monthly_debt_payment", 0.0))
    loan_amount = float(record.get("loan_amount", 0.0))
    term_months = max(int(record.get("loan_term_months", 24)), 1)
    rate = float(record.get("interest_rate", 11.5))

    est_installment = monthly_loan_payment(loan_amount, rate, term_months)
    dti = debt_to_income_ratio(existing_debt_payment + est_installment, income)
    expense_ratio = round((expenses / income) * 100.0, 1)
    net_surplus = round(income - expenses - existing_debt_payment - est_installment, 2)
    work_years = float(record.get("work_experience_years", 0.0))
    thin_file = bool(record.get("thin_file", False))
    alt_score_verified = bool(record.get("alt_data_verified", False))

    # Base illustrative probability of default (0-100)
    score = 12.0
    factors: list[tuple[str, str, str]] = []

    if dti > 50:
        score += 34.0
        factors.append(("High debt-to-income", f"Projected DTI {dti:.1f}% exceeds 50%", "high"))
    elif dti > 38:
        score += 18.0
        factors.append(("Moderate debt-to-income", f"Projected DTI {dti:.1f}% (38%-50% range)", "medium"))
    else:
        score -= 4.0
        factors.append(("Healthy debt-to-income", f"Projected DTI {dti:.1f}% within comfortable range", "low"))

    if net_surplus < 0:
        score += 24.0
        factors.append(("Negative monthly surplus", f"Estimated deficit of ${abs(net_surplus):,.0f}/mo", "high"))
    elif net_surplus < income * 0.15:
        score += 10.0
        factors.append(("Tight cash buffer", f"Remaining surplus ${net_surplus:,.0f}/mo", "medium"))
    else:
        score -= 3.0
        factors.append(("Adequate cash buffer", f"Estimated surplus ${net_surplus:,.0f}/mo", "low"))

    if work_years < 1:
        score += 10.0
        factors.append(("Short tenure", f"{work_years:.1f} years in current employment/business", "medium"))
    elif work_years >= 5:
        score -= 5.0
        factors.append(("Stable employment tenure", f"{work_years:.0f} years verified tenure", "low"))

    if thin_file:
        if alt_score_verified:
            factors.append(
                (
                    "Thin credit file (supported)",
                    "Alternative utility, mobile-money, and cash-flow records verified — not penalized",
                    "low",
                )
            )
        else:
            factors.append(
                (
                    "Thin credit file (review needed)",
                    "Limited bureau history — collect alternative financial records before deciding",
                    "medium",
                )
            )

    pd_pct = round(max(4.0, min(score, 88.0)), 1)
    if pd_pct < 20:
        tier = "Low Risk"
    elif pd_pct < 42:
        tier = "Medium Risk"
    else:
        tier = "High Risk"

    return {
        "pd_pct": pd_pct,
        "tier": tier,
        "estimated_installment": est_installment,
        "projected_dti": dti,
        "expense_ratio": expense_ratio,
        "net_surplus": net_surplus,
        "factors": factors,
    }
