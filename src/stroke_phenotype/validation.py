"""Cross-center validation helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from .io import read_table
from .metrics import compute_count_metrics


def _month_filter(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if "month" in df.columns:
        month = pd.PeriodIndex(pd.to_datetime(df["month"]), freq="M")
        df = df.copy()
        df.index = month
    elif not isinstance(df.index, pd.PeriodIndex):
        df = df.copy()
        df.index = pd.PeriodIndex(df.index, freq="M")

    if start:
        df = df.loc[pd.Period(start, freq="M") :]
    if end:
        df = df.loc[: pd.Period(end, freq="M")]
    return df


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
