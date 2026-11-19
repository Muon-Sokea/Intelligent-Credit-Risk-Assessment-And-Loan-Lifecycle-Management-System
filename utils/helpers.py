"""General application helpers."""

from pathlib import Path


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if needed and return its resolved path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()
