#!/usr/bin/env python
"""Audit historical Center 1 linked-validation registry snapshot and date window.

Only aggregate counts are printed. No patient identifiers are emitted.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from stroke_phenotype.io import read_table
from stroke_phenotype.linkage import (
    filter_primary_ischemic_registry,
    linked_patient_precision,
    registry_patient_ids_from_fin_crosswalk,
)


WINDOWS = [
    ("2018-02_to_2019-01", "2018-02-01", "2019-01-31"),
    ("2018-03_to_2019-02", "2018-03-01", "2019-02-28"),
    ("2018-02_to_2019-02", "2018-02-01", "2019-02-28"),
]

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


def _distance(row: dict[str, object]) -> int:
    return sum(
        abs(int(row[k]) - int(v))
        for k, v in HISTORICAL.items()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ehr", required=True)
    parser.add_argument(
        "--registry",
        action="append",
        required=True,
        help="Registry CSV. Repeat --registry to compare snapshots.",
    )
    parser.add_argument("--registry-conversion", required=True)
    parser.add_argument("--registry-fin-col", default="FIN")
    parser.add_argument("--conversion-fin-col", default="FIN")
    parser.add_argument("--conversion-patient-col", default="PAT_ID")
    parser.add_argument("--registry-diagnosis-col", default="Diagnosis")
    parser.add_argument("--registry-type-col", default="Type")
    parser.add_argument("--registry-date-col", default="Admit Date")
    parser.add_argument("--patient-prefix", default="PSU")
    args = parser.parse_args()

    ehr = read_table(
        args.ehr,
        dtype={"patient_id": "string", "encounter_id": "string"},
    ).copy()
    ehr["admit_date"] = pd.to_datetime(ehr["admit_date"], errors="raise")

    conversion = read_table(
        args.registry_conversion,
        dtype={
            args.conversion_fin_col: "string",
            args.conversion_patient_col: "string",
        },
    )

    rows: list[dict[str, object]] = []

    for registry_path in args.registry:
        registry = read_table(
            registry_path,
            dtype={args.registry_fin_col: "string"},
        )
        date_col = _resolve_column(registry, args.registry_date_col)
        registry[date_col] = pd.to_datetime(
            registry[date_col].astype("string").str.split().str[0],
            errors="coerce",
        )
        registry = filter_primary_ischemic_registry(
            registry,
            diagnosis_col=args.registry_diagnosis_col,
            stroke_type_col=args.registry_type_col,
        )

        for label, start, end in WINDOWS:
            start_ts = pd.Timestamp(start)
            end_ts = pd.Timestamp(end)

            ehr_w = ehr[
                (ehr["admit_date"] >= start_ts)
                & (ehr["admit_date"] <= end_ts)
            ].copy()
            reg_w = registry[
                (registry[date_col] >= start_ts)
                & (registry[date_col] <= end_ts)
            ].copy()

            truth = registry_patient_ids_from_fin_crosswalk(
                reg_w,
                conversion,
                registry_fin_col=args.registry_fin_col,
                conversion_fin_col=args.conversion_fin_col,
                conversion_patient_col=args.conversion_patient_col,
                patient_prefix=args.patient_prefix or None,
            )
            metrics = linked_patient_precision(
                ehr_w,
                truth,
                patient_col="patient_id",
                include_exploratory=True,
            ).set_index("definition")

            row = {
                "registry": Path(registry_path).name,
                "window": label,
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

    out = pd.DataFrame(rows).sort_values(
        ["target_distance", "registry", "window"]
    )

    print("Historical aggregate targets:")
    print(HISTORICAL)
    print()
    print("Snapshot/window comparison, closest first:")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
