"""
Step 2 – Feature engineering and preprocessing for FinGuard AI credit risk.

Everything here runs INSIDE the model pipeline, so the API and frontend send
clean borrower/loan columns and the pipeline creates derived features itself.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from ml import config


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create credit-risk domain features from borrower and loan columns."""
    df = df.copy()
    if {"person_income", "loan_amnt"} <= set(df.columns):
        df["income_to_loan_ratio"] = df["person_income"] / df["loan_amnt"].replace(0, np.nan)
    if {"cb_person_cred_hist_length", "person_age"} <= set(df.columns):
        df["cred_hist_to_age_ratio"] = df["cb_person_cred_hist_length"] / df["person_age"].replace(0, np.nan)
    if {"person_emp_length", "person_age"} <= set(df.columns):
        df["emp_to_age_ratio"] = df["person_emp_length"] / df["person_age"].replace(0, np.nan)
    if "loan_percent_income" in df.columns:
        df["high_burden_flag"] = (df["loan_percent_income"] >= 0.35).astype(int)
    return df


def get_input_columns(df: pd.DataFrame) -> list[str]:
    """Columns the user/API must provide (before feature engineering)."""
    skip = {config.TARGET_COLUMN, *config.DROP_COLUMNS}
    return [c for c in df.columns if c not in skip]


def split_types(df: pd.DataFrame):
    """Numeric and categorical columns AFTER feature engineering."""
    numeric = df.select_dtypes(include="number").columns.tolist()
    categorical = [c for c in df.columns if c not in numeric]
    return numeric, categorical


def build_preprocessor(X_sample: pd.DataFrame) -> Pipeline:
    """add_features ➜ impute ➜ scale / one-hot encode."""
    numeric, categorical = split_types(add_features(X_sample))
    columns = ColumnTransformer([
        ("num", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), numeric),
        ("cat", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]), categorical),
    ])
    return Pipeline([
        ("add_features", FunctionTransformer(add_features)),
        ("columns", columns),
    ])
