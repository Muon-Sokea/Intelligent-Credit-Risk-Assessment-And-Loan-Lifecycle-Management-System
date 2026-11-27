"""Bridge between FinGuard AI Streamlit frontend and the trained ml/ model."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "model.joblib"
METRICS_PATH = PROJECT_ROOT / "models" / "metrics.json"

_PURPOSE_TO_INTENT = {
    "Business": "VENTURE",
    "Agriculture": "VENTURE",
    "Home": "HOMEIMPROVEMENT",
    "Education": "EDUCATION",
    "Personal": "PERSONAL",
    "Vehicle": "PERSONAL",
}


def _ensure_project_root_on_path() -> None:
    root_str = str(PROJECT_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


@st.cache_resource(show_spinner=False)
def load_model_bundle() -> dict[str, Any] | None:
    """Load the trained joblib pipeline bundle if present."""
    if not MODEL_PATH.exists():
        return None
    _ensure_project_root_on_path()
    return joblib.load(MODEL_PATH)


@st.cache_data(ttl=300, show_spinner=False)
def load_model_metrics() -> dict[str, Any] | None:
    """Load saved evaluation metrics JSON if present."""
    if not METRICS_PATH.exists():
        return None
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


def _infer_grade(rate_pct: float) -> str:
    if rate_pct < 8.5:
        return "A"
    if rate_pct < 10.5:
        return "B"
    if rate_pct < 12.5:
        return "C"
    if rate_pct < 14.5:
        return "D"
    return "E"


def record_to_model_features(record: dict[str, Any]) -> dict[str, Any]:
    """Map a FinGuard AI borrower record into credit_risk_dataset model columns."""
    monthly_income = max(float(record.get("monthly_income", 1000.0)), 100.0)
    annual_income = round(monthly_income * 12.0, 2)
    loan_amnt = float(record.get("loan_amount", 5000.0))
    rate = float(record.get("interest_rate", 11.5))
    emp_years = float(record.get("work_experience_years", 3.0))
    purpose = str(record.get("loan_purpose", "Personal"))
    borrower_type = str(record.get("borrower_type", "Personal"))
    thin_file = bool(record.get("thin_file", False))

    if purpose == "Home":
        home_ownership = "MORTGAGE"
    elif borrower_type == "Business":
        home_ownership = "OWN"
    else:
        home_ownership = "RENT"

    return {
        "person_age": int(record.get("age", 34)),
        "person_income": annual_income,
        "person_home_ownership": home_ownership,
        "person_emp_length": min(max(emp_years, 0.0), 60.0),
        "loan_intent": _PURPOSE_TO_INTENT.get(purpose, "PERSONAL"),
        "loan_grade": _infer_grade(rate),
        "loan_amnt": loan_amnt,
        "loan_int_rate": rate,
        "loan_percent_income": round(min(loan_amnt / max(annual_income, 1.0), 0.99), 2),
        "cb_person_default_on_file": "N",
        "cb_person_cred_hist_length": 2 if thin_file else max(int(emp_years) + 2, 4),
    }


def predict_default_risk(record: dict[str, Any]) -> dict[str, Any] | None:
    """Run the trained credit-risk ML model on a FinGuard AI borrower record."""
    bundle = load_model_bundle()
    if bundle is None:
        return None

    cols = bundle["input_columns"]
    feats = record_to_model_features(record)
    if not set(cols).issubset(feats.keys()):
        return None

    X = pd.DataFrame([{c: feats[c] for c in cols}])
    prob_default = float(bundle["pipeline"].predict_proba(X)[0, 1])
    pd_pct = round(prob_default * 100.0, 1)

    if pd_pct < 20.0:
        tier = "Low Risk"
    elif pd_pct < 42.0:
        tier = "Medium Risk"
    else:
        tier = "High Risk"

    metrics = load_model_metrics() or {}
    test_m = metrics.get("test_metrics", {})
    return {
        "pd_pct": pd_pct,
        "tier": tier,
        "model_name": metrics.get("best_model", "Trained ML Model"),
        "test_roc_auc": test_m.get("roc_auc"),
        "test_f1": test_m.get("f1"),
        "test_recall": test_m.get("recall"),
        "features_used": feats,
    }
