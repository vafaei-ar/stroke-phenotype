"""Linked validation against a stroke registry."""

from __future__ import annotations

import re

import pandas as pd

from .definitions import phenotype_masks


def _resolve_column(df: pd.DataFrame, requested: str, *, table: str) -> str:
    """Resolve a legacy column name allowing case/spacing/underscore variants."""
    if requested in df.columns:
        return requested

    def norm(value: object) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value).strip().casefold())

    target = norm(requested)
    matches = [col for col in df.columns if norm(col) == target]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise KeyError(
            f"{table} column {requested!r} is ambiguous; matches: {matches}"
        )

    raise KeyError(
        f"{table} column not found: {requested!r}. "
        f"Available columns: {list(df.columns)}"
    )


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


def registry_patient_ids_from_fin_crosswalk(
    registry: pd.DataFrame,
    conversion: pd.DataFrame,
    *,
    registry_fin_col: str = "FIN",
    conversion_fin_col: str = "FIN",
    conversion_patient_col: str = "PAT_ID",
    patient_prefix: str | None = "PSU",
) -> pd.Series:
    """Map registry FIN values to EHR patient identifiers using the legacy crosswalk.

    This reproduces the historical Center 1 linkage pattern: registry rows are
    merged to the FIN-to-PAT_ID conversion table, then unique mapped EHR patient
    identifiers are used as the linked registry truth set.
    """
    registry_fin_actual = _resolve_column(
        registry, registry_fin_col, table="registry"
    )
    conversion_fin_actual = _resolve_column(
        conversion, conversion_fin_col, table="conversion"
    )
    conversion_patient_actual = _resolve_column(
        conversion, conversion_patient_col, table="conversion"
    )

    reg = registry.copy()
    conv = conversion[
        [conversion_fin_actual, conversion_patient_actual]
    ].copy()

    if registry_fin_actual != registry_fin_col:
        reg = reg.rename(columns={registry_fin_actual: registry_fin_col})
    if conversion_fin_actual != conversion_fin_col:
        conv = conv.rename(columns={conversion_fin_actual: conversion_fin_col})
    if conversion_patient_actual != conversion_patient_col:
        conv = conv.rename(
            columns={conversion_patient_actual: conversion_patient_col}
        )

    reg[registry_fin_col] = (
        reg[registry_fin_col].astype("string").str.strip()
    )
    conv[conversion_fin_col] = (
        conv[conversion_fin_col].astype("string").str.strip()
    )
    conv[conversion_patient_col] = (
        conv[conversion_patient_col].astype("string").str.strip()
    )

    if patient_prefix:
        conv = conv[
            conv[conversion_patient_col]
            .fillna("")
            .str.startswith(patient_prefix)
        ]

    if conversion_fin_col != registry_fin_col:
        conv = conv.rename(columns={conversion_fin_col: registry_fin_col})

    merged = reg.merge(conv, on=registry_fin_col, how="left")

    return (
        merged[conversion_patient_col]
        .dropna()
        .astype("string")
        .str.strip()
        .drop_duplicates()
        .reset_index(drop=True)
    )


def linked_patient_precision(
    ehr: pd.DataFrame,
    registry_patient_ids: pd.Series,
    *,
    patient_col: str = "patient_id",
    include_exploratory: bool = False,
) -> pd.DataFrame:
    """Compute patient-level precision/PPV using registry-linked EHR patient IDs."""
    if patient_col not in ehr.columns:
        raise KeyError(f"EHR patient column not found: {patient_col!r}")

    truth = set(
        pd.Series(registry_patient_ids)
        .dropna()
        .astype("string")
        .str.strip()
    )
    ehr_ids = ehr[patient_col].astype("string").str.strip()
    masks = phenotype_masks(ehr, include_exploratory=include_exploratory)

    rows = []
    for definition, mask in masks.items():
        ids = ehr_ids[mask]
        n_positive = int(mask.sum())
        n_matched = int(ids.isin(truth).sum())
        precision = n_matched / n_positive if n_positive else float("nan")
        rows.append({
            "definition": definition,
            "definition_positive": n_positive,
            "matched_registry": n_matched,
            "precision": precision,
            "PPV": precision,
        })
    return pd.DataFrame(rows)


def linked_precision(
    ehr: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    encounter_col: str = "encounter_id",
    registry_encounter_col: str | None = None,
    include_exploratory: bool = False,
) -> pd.DataFrame:
    """Compute direct encounter-level precision/PPV.

    Retained for non-legacy use. Historical Center 1 validation used the
    FIN-to-PAT_ID crosswalk and patient-level membership instead.
    """
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
