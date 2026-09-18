"""Cross-center validation helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from .io import read_table
from .metrics import compute_count_metrics
from .registry import standardize_month_column


def _month_filter(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    """Normalize a monthly table and restrict it to the configured window."""
    has_month_like_column = (
        "month" in df.columns
        or "date" in df.columns
        or any(str(c).startswith("Unnamed") for c in df.columns)
    )

    if has_month_like_column:
        out = standardize_month_column(df)
        out.index = pd.PeriodIndex(out["month"], freq="M")
    elif isinstance(df.index, pd.PeriodIndex):
        out = df.copy()
    else:
        out = df.copy()
        out.index = pd.PeriodIndex(out.index, freq="M")

    if start:
        out = out.loc[pd.Period(start, freq="M") :]
    if end:
        out = out.loc[: pd.Period(end, freq="M")]
    return out


def load_center_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or "centers" not in config:
        raise ValueError("Configuration must contain a top-level 'centers' mapping")
    return config


def validate_centers(config_path: str | Path) -> pd.DataFrame:
    """Compute count metrics for every configured center."""
    config = load_center_config(config_path)
    outputs = []

    for center, spec in config["centers"].items():
        df = read_table(spec["monthly_counts"])
        df = _month_filter(df, spec.get("start_month"), spec.get("end_month"))

        unavailable = set(spec.get("unavailable_definitions", []) or [])
        for definition in unavailable:
            if definition in df.columns:
                df[definition] = pd.NA

        metrics = compute_count_metrics(df)
        metrics.insert(0, "center", center)
        outputs.append(metrics)

    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()
