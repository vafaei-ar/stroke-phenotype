"""Canonical rule-based ischemic stroke phenotype definitions."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

PRIMARY_DEFINITIONS = tuple(f"D{i}" for i in range(9))
EXPLORATORY_DEFINITIONS = ("D9",)


def _bool_column(df: pd.DataFrame, column: str) -> pd.Series:
    """Return a boolean feature column, treating missing values as False."""
    if column not in df.columns:
        raise KeyError(f"Required feature column is missing: {column}")
    return df[column].fillna(False).astype(bool)


def phenotype_masks(
    df: pd.DataFrame,
    *,
    ct_col: str = "ct",
    mri_col: str = "mri",
    lipid_col: str = "lipid",
    rehab_col: str = "rehab",
    include_exploratory: bool = False,
) -> Mapping[str, pd.Series]:
    """Return canonical D0-D8 masks for an already ICD-eligible candidate cohort."""
    ct = _bool_column(df, ct_col)
    mri = _bool_column(df, mri_col)
    lipid = _bool_column(df, lipid_col)
    rehab = _bool_column(df, rehab_col)
    any_imaging = ct | mri

    masks: dict[str, pd.Series] = {
        "D0": pd.Series(True, index=df.index, dtype=bool),
        "D1": any_imaging & lipid,
        "D2": any_imaging & (lipid | rehab),
        "D3": mri & lipid,
        "D4": mri & (lipid | rehab),
        "D5": any_imaging,
        "D6": mri & lipid & rehab,
        "D7": mri,
        "D8": ct & lipid,
    }
    if include_exploratory:
        masks["D9"] = any_imaging & lipid & rehab
    return masks
