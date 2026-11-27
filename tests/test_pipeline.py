"""
Automated tests for the FinGuard AI ML pipeline.  Run from the project root:

    pytest tests/test_pipeline.py
"""
import pandas as pd
import pytest

from ml import config, service, train
from ml.data.make_dataset import clean, load_raw
from ml.features import add_features


@pytest.fixture(scope="session")
def raw():
    return load_raw()


@pytest.fixture(scope="session")
def cleaned(raw):
    return clean(raw, verbose=False)


@pytest.fixture(scope="session")
def trained_model():
    if not config.MODEL_PATH.exists():
        train.run(verbose=False)
    return config.MODEL_PATH


# --- Data cleaning -----------------------------------------------------------
def test_no_duplicates(cleaned):
    assert cleaned.duplicated().sum() == 0


def test_target_has_only_valid_labels(cleaned):
    assert set(cleaned[config.TARGET_COLUMN].unique()) <= {config.POSITIVE_CLASS, config.NEGATIVE_CLASS}


def test_no_impossible_ages_or_emp_length(cleaned):
    assert cleaned["person_age"].dropna().between(18, 100).all()
    assert cleaned["person_emp_length"].dropna().between(0, 60).all()


def test_numbers_are_numeric(cleaned):
    assert pd.api.types.is_numeric_dtype(cleaned["loan_amnt"])
    assert pd.api.types.is_numeric_dtype(cleaned["loan_int_rate"])


def test_clean_does_not_change_raw(raw):
    before = raw.copy()
    clean(raw, verbose=False)
    pd.testing.assert_frame_equal(raw, before)


# --- Features ----------------------------------------------------------------
def test_add_features_creates_columns(cleaned):
    out = add_features(cleaned)
    assert {
        "income_to_loan_ratio",
        "cred_hist_to_age_ratio",
        "emp_to_age_ratio",
        "high_burden_flag",
    } <= set(out.columns)
    assert len(out) == len(cleaned)


# --- Prediction service ------------------------------------------------------
def _example_input():
    return {f["name"]: f["default"] for f in service.get_schema()["features"]}


def test_prediction_returns_valid_label(trained_model):
    result = service.make_prediction(_example_input())
    assert result["prediction"] in {config.POSITIVE_CLASS, config.NEGATIVE_CLASS}
    assert sum(result["probabilities"].values()) == pytest.approx(1, abs=1e-3)


def test_missing_feature_raises_error(trained_model):
    data = _example_input()
    data.pop(next(iter(data)))
    with pytest.raises(ValueError):
        service.make_prediction(data)


def test_model_beats_minimum_quality(trained_model):
    """Ensure the credit-risk model achieves strong ROC-AUC on held-out test data."""
    metrics = service.get_metrics()["test_metrics"]
    assert metrics["roc_auc"] > 0.85
