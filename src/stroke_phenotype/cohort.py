"""Cohort selection utilities."""

from __future__ import annotations

import pandas as pd


def select_first_qualifying_encounter(
    df: pd.DataFrame,
    *,
    patient_col: str = "patient_id",
    date_col: str = "admit_date",
) -> pd.DataFrame:
    """Keep each patient's first qualifying encounter in the analytic period."""
    missing = [c for c in (patient_col, date_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="raise")
    out = out.sort_values([patient_col, date_col], kind="stable")
    return out.drop_duplicates(subset=patient_col, keep="first").reset_index(drop=True)
