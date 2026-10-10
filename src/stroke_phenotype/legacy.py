"""Compatibility helpers for reproducing the original notebook analysis.

These functions translate the protected intermediate table created by the legacy
Center 1 notebook into the public repository's standardized feature schema.
They intentionally preserve the original analysis order so current manuscript
results can be reproduced before the raw-EHR extraction code is refactored.
"""

from __future__ import annotations

import pandas as pd


LEGACY_REQUIRED_COLUMNS = (
    "PATID",
    "ENCOUNTERID",
    "ADMIT_DATE",
    "FACILITYID",
    "MRI-2",
    "MRI-ENC",
    "CT-2",
    "CT-ENC",
    "lip",
    "phy",
)


def _coerce_bool(series: pd.Series) -> pd.Series:
    """Convert common CSV boolean encodings to a strict boolean series."""
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)

    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float).ne(0)

    normalized = series.astype("string").str.strip().str.casefold()
    true_values = {"true", "t", "1", "yes", "y"}
    false_values = {"false", "f", "0", "no", "n", "", "nan", "none", "<na>"}
    unexpected = set(normalized.dropna().unique()) - true_values - false_values
    if unexpected:
        sample = sorted(unexpected)[:5]
        raise ValueError(f"Unexpected boolean values: {sample}")
    return normalized.isin(true_values)


def _legacy_first_event(df: pd.DataFrame) -> pd.DataFrame:
    """Reproduce the notebook's historical first-event selection exactly.

    The manuscript-generating notebook used::

        df.sort_values("ADMIT_DATE").drop_duplicates("PATID", keep="first")

    It did not include a secondary encounter-id tie breaker. Therefore two
    encounters for the same patient on the same admission date can be resolved
    according to pandas' quicksort ordering. This helper is compatibility code,
    not the preferred rule for future analyses. New analyses should use the
    deterministic selector in :mod:`stroke_phenotype.cohort`.
    """
    return (
        df.sort_values("admit_date", kind="quicksort")
        .drop_duplicates(subset="patient_id", keep="first")
        .reset_index(drop=True)
    )


def standardize_legacy_center1_features(
    df: pd.DataFrame,
    *,
    facility_contains: str | None = None,
    first_event_only: bool = True,
) -> pd.DataFrame:
    """Translate legacy ``df_phen_details.csv`` into the canonical feature table.

    The original manuscript count pipeline used ``MRI-2-ENC`` and ``CT-2-ENC``,
    defined as the union of the 2-day window flag and the same-encounter flag.
    It then selected the first qualifying encounter per patient *before* applying
    the Center 1 facility restriction. This function preserves that order and,
    for compatibility, preserves the notebook's original tie handling.

    Parameters
    ----------
    df:
        Legacy patient-encounter feature table.
    facility_contains:
        Optional local facility substring. Keep this value in local scripts/config;
        do not commit institution-identifying values to the public repository.
    first_event_only:
        Preserve the original first-qualifying-encounter rule when True.
    """
    missing = [column for column in LEGACY_REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise KeyError(f"Legacy feature table is missing required columns: {missing}")

    out = pd.DataFrame(
        {
            "patient_id": df["PATID"].astype("string"),
            "encounter_id": df["ENCOUNTERID"].astype("string"),
            "admit_date": pd.to_datetime(df["ADMIT_DATE"], errors="raise"),
            "facility_id": df["FACILITYID"].astype("string"),
            "mri": _coerce_bool(df["MRI-2"]) | _coerce_bool(df["MRI-ENC"]),
            "ct": _coerce_bool(df["CT-2"]) | _coerce_bool(df["CT-ENC"]),
            "lipid": _coerce_bool(df["lip"]),
            "rehab": _coerce_bool(df["phy"]),
        }
    )

    if first_event_only:
        out = _legacy_first_event(out)

    if facility_contains is not None:
        keep = out["facility_id"].str.contains(
            facility_contains,
            case=False,
            regex=False,
            na=False,
        )
        out = out.loc[keep].copy()

    return out.reset_index(drop=True)
