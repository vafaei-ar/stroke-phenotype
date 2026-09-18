"""Input/output helpers with explicit schema handling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_table(
    path: str | Path,
    *,
    dtype: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Read CSV or Parquet based on file suffix.

    The optional dtype mapping is applied to CSV input so identifier columns can
    be preserved as strings, including leading zeros. Parquet schemas are used
    as stored.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=dtype, low_memory=False)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported table type: {path}")


def write_table(df: pd.DataFrame, path: str | Path) -> None:
    """Write CSV or Parquet based on file suffix."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path, index=False)
        return
    if suffix in {".parquet", ".pq"}:
        df.to_parquet(path, index=False)
        return
    raise ValueError(f"Unsupported table type: {path}")
