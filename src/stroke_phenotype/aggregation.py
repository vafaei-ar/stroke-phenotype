"""Monthly aggregation for count-based validation."""

from __future__ import annotations

import pandas as pd

from .cohort import select_first_qualifying_encounter
from .definitions import phenotype_masks


def build_monthly_definition_counts(
    features: pd.DataFrame,
    *,
    patient_col: str = "patient_id",
    date_col: str = "admit_date",
    include_exploratory: bool = False,
    first_event_only: bool = True,
) -> pd.DataFrame:
    """Aggregate phenotype-positive first events to calendar-month counts."""
    df = features.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="raise")
    if first_event_only:
        df = select_first_qualifying_encounter(df, patient_col=patient_col, date_col=date_col)

    df["month"] = df[date_col].dt.to_period("M")
    masks = phenotype_masks(df, include_exploratory=include_exploratory)

    series = []
    for definition, mask in masks.items():
        counts = df.loc[mask].groupby("month", observed=True)[patient_col].nunique().rename(definition)
        series.append(counts)

    if not series:
        return pd.DataFrame(index=pd.PeriodIndex([], freq="M"))
    return pd.concat(series, axis=1).fillna(0).astype(int).sort_index()
