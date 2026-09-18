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
    """Restrict registry records to primary ischemic stroke."""
    missing = [
        c for c in (diagnosis_col, stroke_type_col)
        if c not in registry.columns
    ]
    if missing:
        raise KeyError(f"Registry is missing required columns: {missing}")

    out = registry.copy()
    out = out[
        out[diagnosis_col].astype(str).str.strip().str.casefold() == "primary"
    ]
    out = out[
        out[stroke_type_col].astype(str).str.strip().str.casefold() == "ischemic"
    ]
    return out.copy()


def linked_precision(
    ehr: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    encounter_col: str = "encounter_id",
    registry_encounter_col: str | None = None,
    include_exploratory: bool = False,
) -> pd.DataFrame:
    """Compute encounter-level precision/PPV for each phenotype definition."""
    registry_encounter_col = registry_encounter_col or encounter_col

    if encounter_col not in ehr.columns:
        raise KeyError(f"EHR encounter column not found: {encounter_col!r}")
    if registry_encounter_col not in registry.columns:
        raise KeyError(
            f"Registry encounter column not found: {registry_encounter_col!r}"
        )

    registry_ids = set(
        registry[registry_encounter_col]
        .dropna()
        .astype("string")
        .str.strip()
    )
    ehr_ids = ehr[encounter_col].astype("string").str.strip()
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
