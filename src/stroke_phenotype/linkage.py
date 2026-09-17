"""Encounter-linked validation against a stroke registry."""

from __future__ import annotations

import pandas as pd

from .definitions import phenotype_masks


def filter_primary_ischemic_registry(
    registry: pd.DataFrame,
    *,
    diagnosis_col: str = "diagnosis",
    stroke_type_col: str = "stroke_type",
) -> pd.DataFrame:
    """Restrict registry records to primary ischemic stroke when fields exist."""
    out = registry.copy()
    if diagnosis_col in out.columns:
        out = out[out[diagnosis_col].astype(str).str.casefold() == "primary"]
    if stroke_type_col in out.columns:
        out = out[out[stroke_type_col].astype(str).str.casefold() == "ischemic"]
    return out.copy()


def linked_precision(
    ehr: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    encounter_col: str = "encounter_id",
    include_exploratory: bool = False,
) -> pd.DataFrame:
    """Compute encounter-level precision/PPV for each phenotype definition."""
    if encounter_col not in ehr.columns or encounter_col not in registry.columns:
        raise KeyError(f"Both tables must contain encounter column {encounter_col!r}")

    registry_ids = set(registry[encounter_col].dropna().astype(str))
    ehr_ids = ehr[encounter_col].astype(str)
    masks = phenotype_masks(ehr, include_exploratory=include_exploratory)

    rows = []
    for definition, mask in masks.items():
        ids = ehr_ids[mask]
        n_positive = int(mask.sum())
        n_matched = int(ids.isin(registry_ids).sum())
        precision = n_matched / n_positive if n_positive else float("nan")
        rows.append({
            "definition": definition,
            "definition_positive": n_positive,
            "matched_registry": n_matched,
            "precision": precision,
            "PPV": precision,
        })
    return pd.DataFrame(rows)
