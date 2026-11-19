"""Common financial calculations."""


def debt_to_income_ratio(monthly_debt: float, monthly_income: float) -> float:
    """Calculate debt-to-income ratio as a decimal."""
    if monthly_income <= 0:
        raise ValueError("Monthly income must be greater than zero.")
    if monthly_debt < 0:
        raise ValueError("Monthly debt cannot be negative.")
    return monthly_debt / monthly_income


def monthly_loan_payment(principal: float, annual_rate: float, months: int) -> float:
    """Calculate a fixed monthly loan payment."""
    if principal < 0 or annual_rate < 0 or months <= 0:
        raise ValueError("Principal/rate must be non-negative and months positive.")
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return principal / months
    return principal * monthly_rate / (1 - (1 + monthly_rate) ** -months)
