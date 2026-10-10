#!/usr/bin/env python
"""Audit historical Center 1 registry truth-set definition.

This script prints only aggregate counts. It compares plausible registry
Diagnosis/Type restrictions within the likely manuscript validation window
against the historical linked-validation targets.
"""

from __future__ import annotations

import argparse
from itertools import product

import pandas as pd

from stroke_phenotype.io import read_table
from stroke_phenotype.linkage import (
    linked_patient_precision,
    registry_patient_ids_from_fin_crosswalk,
)


HISTORICAL = {
    "registry_truth": 701,
    "D0_positive": 918,
    "D0_matched": 636,
    "D1_positive": 720,
    "D1_matched": 573,
}


def _resolve_column(df: pd.DataFrame, requested: str) -> str:
    if requested in df.columns:
        return requested

    def norm(value: object) -> str:
        return "".join(ch for ch in str(value).casefold() if ch.isalnum())

    target = norm(requested)
    matches = [c for c in df.columns if norm(c) == target]
    if len(matches) == 1:
        return matches[0]
    raise KeyError(
        f"Column {requested!r} not found uniquely. Available: {list(df.columns)}"
    )


def _norm_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.casefold()


def _distance(row: dict[str, object]) -> int:
    return sum(abs(int(row[k]) - int(v)) for k, v in HISTORICAL.items())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ehr", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-conversion", required=True)
    parser.add_argument("--registry-fin-col", default="FIN")
    parser.add_argument("--conversion-fin-col", default="FIN")
    parser.add_argument("--conversion-patient-col", default="PAT_ID")
    parser.add_argument("--registry-diagnosis-col", default="Diagnosis")
    parser.add_argument("--registry-type-col", default="Type")
    parser.add_argument("--registry-date-col", default="Admit Date")
    parser.add_argument("--patient-prefix", default="PSU")
    parser.add_argument("--start-date", default="2018-02-01")
    parser.add_argument("--end-date", default="2019-01-31")
    args = parser.parse_args()

    start = pd.Timestamp(args.start_date)
    end = pd.Timestamp(args.end_date)

    ehr = read_table(
        args.ehr,
        dtype={"patient_id": "string", "encounter_id": "string"},
    ).copy()
    ehr["admit_date"] = pd.to_datetime(ehr["admit_date"], errors="raise")
    ehr = ehr[(ehr["admit_date"] >= start) & (ehr["admit_date"] <= end)].copy()

    registry = read_table(
        args.registry,
        dtype={args.registry_fin_col: "string"},
    ).copy()
    conversion = read_table(
        args.registry_conversion,
        dtype={
            args.conversion_fin_col: "string",
            args.conversion_patient_col: "string",
        },
    )

    date_col = _resolve_column(registry, args.registry_date_col)
    diagnosis_col = _resolve_column(registry, args.registry_diagnosis_col)
    type_col = _resolve_column(registry, args.registry_type_col)

    registry[date_col] = pd.to_datetime(
        registry[date_col].astype("string").str.split().str[0],
        errors="coerce",
    )
    registry = registry[
        (registry[date_col] >= start) & (registry[date_col] <= end)
    ].copy()

    diagnosis = _norm_text(registry[diagnosis_col])
    stroke_type = _norm_text(registry[type_col])

    print("Registry row counts by Diagnosis/Type in selected window:")
    ctab = (
        pd.DataFrame({
            "Diagnosis": diagnosis.fillna("<missing>"),
            "Type": stroke_type.fillna("<missing>"),
        })
        .value_counts()
        .rename("rows")
        .reset_index()
    )
    print(ctab.to_string(index=False))
    print()

    filters = [
        ("Primary+Ischemic", diagnosis.eq("primary") & stroke_type.eq("ischemic")),
        ("AnyDiagnosis+Ischemic", stroke_type.eq("ischemic")),
        ("Primary+AnyType", diagnosis.eq("primary")),
        ("AllRegistryRows", pd.Series(True, index=registry.index)),
    ]

    rows = []
    for label, mask in filters:
        reg_sub = registry.loc[mask].copy()
        truth = registry_patient_ids_from_fin_crosswalk(
            reg_sub,
            conversion,
            registry_fin_col=args.registry_fin_col,
            conversion_fin_col=args.conversion_fin_col,
            conversion_patient_col=args.conversion_patient_col,
            patient_prefix=args.patient_prefix or None,
        )
        metrics = linked_patient_precision(
            ehr,
            truth,
            patient_col="patient_id",
            include_exploratory=True,
        ).set_index("definition")

        row = {
            "truth_definition": label,
            "registry_rows": len(reg_sub),
            "registry_truth": int(truth.nunique()),
            "D0_positive": int(metrics.loc["D0", "definition_positive"]),
            "D0_matched": int(metrics.loc["D0", "matched_registry"]),
            "D0_PPV": float(metrics.loc["D0", "precision"]),
            "D1_positive": int(metrics.loc["D1", "definition_positive"]),
            "D1_matched": int(metrics.loc["D1", "matched_registry"]),
            "D1_PPV": float(metrics.loc["D1", "precision"]),
            "D9_positive": int(metrics.loc["D9", "definition_positive"]),
            "D9_matched": int(metrics.loc["D9", "matched_registry"]),
            "D9_PPV": float(metrics.loc["D9", "precision"]),
        }
        row["target_distance"] = _distance(row)
        rows.append(row)

    out = pd.DataFrame(rows).sort_values("target_distance")

    print("Historical aggregate targets:")
    print(HISTORICAL)
    print()
    print("Truth-definition comparison, closest first:")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
