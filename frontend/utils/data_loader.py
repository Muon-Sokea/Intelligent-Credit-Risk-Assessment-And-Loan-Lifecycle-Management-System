"""Helpers for reading project datasets."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load a CSV from an absolute path or a path relative to the project."""
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = PROJECT_ROOT / file_path
    return pd.read_csv(file_path)
