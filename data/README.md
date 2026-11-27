# Data Dictionary — FinGuard AI

## Raw dataset: `raw/credit_risk_dataset.csv`

Public credit-risk dataset (`32,581` raw rows, `12` columns; `32,416` rows after removing exact duplicates).
Used to train and evaluate FinGuard AI's **Loan Default Prediction** model (`loan_status`).

| Column | Type | Description | Known data-quality issues |
|---|---|---|---|
| `person_age` | int | Borrower age in years | Impossible outliers up to `144` (cleaned: > 100 set to missing) |
| `person_income` | int | Annual borrower income (USD) | Wide range (`$4,000`–`$6,000,000`) |
| `person_home_ownership` | category | `RENT`, `MORTGAGE`, `OWN`, `OTHER` | Clean |
| `person_emp_length` | float | Employment length in years | `895` missing; outliers up to `123` (cleaned: > 60 set to missing) |
| `loan_intent` | category | `EDUCATION`, `MEDICAL`, `VENTURE`, `PERSONAL`, `DEBTCONSOLIDATION`, `HOMEIMPROVEMENT` | Clean |
| `loan_grade` | category | Internal credit grade (`A`–`G`) | Clean |
| `loan_amnt` | int | Requested loan amount (USD) | Clean (`$500`–`$35,000`) |
| `loan_int_rate` | float | Annual interest rate (%) | `3,116` missing (imputed inside pipeline) |
| `loan_status` | int (target) | **`0` = Non-Default** (`78.2%`), **`1` = Default** (`21.8%`) | Imbalanced binary target |
| `loan_percent_income` | float | Loan amount divided by annual income (`0.0`–`0.83`) | Clean |
| `cb_person_default_on_file` | category | Historical credit bureau default (`Y` / `N`) | Clean |
| `cb_person_cred_hist_length` | int | Credit history length in years (`2`–`30`) | Clean |

> **Responsible-use note:** This dataset supports prototype model training and evaluation, but does not prove validity for Cambodian banks without local data validation and fairness review.
