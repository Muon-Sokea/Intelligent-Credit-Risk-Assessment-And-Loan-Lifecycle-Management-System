# Model Card

- **Trained:** 2026-11-26T06:35:55
- **Task:** classification – predict `loan_status`
- **Model:** Gradient Boosting
- **Best parameters:** {'n_estimators': 300, 'max_depth': 4, 'learning_rate': 0.03}
- **Data:** 25932 training rows, 6484 test rows
- **Selection metric:** roc_auc (5-fold CV)

## Test-set performance

| Metric | Value |
|---|---|
| accuracy | 0.9343 |
| precision | 0.9688 |
| recall | 0.7228 |
| f1 | 0.8279 |
| roc_auc | 0.9315 |

## Model comparison (cross-validation)

| Model | roc_auc (mean ± std) |
|---|---|
| Gradient Boosting | 0.9284 ± 0.0032 |
| Random Forest | 0.9282 ± 0.0025 |
| Logistic Regression | 0.8722 ± 0.0046 |
| Decision Tree | 0.8395 ± 0.0047 |

## Limitations

- Trained on a public credit-risk dataset (`credit_risk_dataset.csv`), not live Cambodian bank records.
- Model outputs are decision support for human review—never automated lending decisions.
- Requires local validation, fairness auditing, and regulatory review before production banking use.
