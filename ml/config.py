"""
Project configuration – ONE place to change settings.

The notebooks, the training script, both backends, and the frontend ML bridge
all read from this file.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = ROOT_DIR / "data" / "raw" / "credit_risk_dataset.csv"
PROCESSED_DATA_PATH = ROOT_DIR / "data" / "processed" / "clean.csv"
MODEL_PATH = ROOT_DIR / "models" / "model.joblib"
METRICS_PATH = ROOT_DIR / "models" / "metrics.json"
MODEL_CARD_PATH = ROOT_DIR / "models" / "model_card.md"
FIGURES_DIR = ROOT_DIR / "reports" / "figures"

# ---------------------------------------------------------------------------
# Problem definition (FinGuard AI — Loan Default Prediction)
# ---------------------------------------------------------------------------
TASK_TYPE = "classification"

TARGET_COLUMN = "loan_status"
POSITIVE_CLASS = 1   # 1 = Default
NEGATIVE_CLASS = 0   # 0 = Non-Default

# Columns that must NOT be used as model inputs (IDs, dates, leakage)
DROP_COLUMNS: list[str] = []

# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
TEST_SIZE = 0.2
CV_FOLDS = 5
RANDOM_STATE = 42

# ROC-AUC is the banking standard for ranking borrower default probability
PRIMARY_METRIC = "roc_auc" if TASK_TYPE == "classification" else "neg_root_mean_squared_error"

# Number of random combinations tried when tuning the best model
TUNING_ITERATIONS = 5
