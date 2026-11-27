"""
Step 1 – Data cleaning:  data/raw/credit_risk_dataset.csv  ➜  data/processed/clean.csv

Run from the project root:

    python -m ml.data.make_dataset
"""
import numpy as np
import pandas as pd

from ml import config

# Valid ranges – impossible values become NaN and are imputed inside the ML pipeline
VALID_RANGES = {
    "person_age": (18, 100),
    "person_emp_length": (0, 60),
    "person_income": (1, 10_000_000),
    "loan_amnt": (100, 1_000_000),
    "loan_int_rate": (0.0, 40.0),
    "loan_percent_income": (0.0, 1.0),
    "cb_person_cred_hist_length": (0, 60),
}


def load_raw(path=config.RAW_DATA_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def clean(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Return a cleaned copy of the raw credit-risk dataset."""
    log = []
    df = df.copy()

    # 1. Remove exact duplicate rows
    before = len(df)
    df = df.drop_duplicates()
    log.append(f"Removed {before - len(df)} duplicate rows")

    # 2. Strip spaces and normalize categorical text columns
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip().str.upper()

    # 3. Ensure numeric columns are numeric
    for col in VALID_RANGES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 4. Impossible values ➜ NaN (imputed later inside the training pipeline)
    for col, (lo, hi) in VALID_RANGES.items():
        if col in df.columns:
            bad = ~df[col].between(lo, hi) & df[col].notna()
            if bad.any():
                df.loc[bad, col] = np.nan
            log.append(f"Set {int(bad.sum())} out-of-range values in '{col}' to missing")

    # 5. Drop rows with missing target and ensure integer binary labels (0/1)
    before = len(df)
    df = df.dropna(subset=[config.TARGET_COLUMN])
    df[config.TARGET_COLUMN] = pd.to_numeric(df[config.TARGET_COLUMN], errors="coerce")
    df = df.dropna(subset=[config.TARGET_COLUMN])
    df[config.TARGET_COLUMN] = df[config.TARGET_COLUMN].astype(int)
    log.append(f"Dropped {before - len(df)} rows with missing/invalid target")

    if verbose:
        print("\n".join("  - " + line for line in log))
        print(f"  Clean shape: {df.shape}")
    return df.reset_index(drop=True)


def main():
    raw = load_raw()
    print(f"Raw shape: {raw.shape}")
    df = clean(raw)
    config.PROCESSED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.PROCESSED_DATA_PATH, index=False)
    print(f"Saved ➜ {config.PROCESSED_DATA_PATH.relative_to(config.ROOT_DIR)}")


if __name__ == "__main__":
    main()
