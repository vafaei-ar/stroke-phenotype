#!/usr/bin/env python
"""Audit Center 1 linked-validation cohort restrictions without exposing PHI.

This diagnostic compares aggregate PPV checkpoints under nested cohort filters
using the already reproduced Center 1 feature table. It is intended to identify
which historical linked-validation restrictions explain differences from the
manuscript precision values before rebuilding a separate linked cohort.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from stroke_phenotype.codes import ISCHEMIC_STROKE_ICD10, ISCHEMIC_STROKE_ICD9
from stroke_phenotype.io import read_table
from stroke_phenotype.linkage import (
    filter_primary_ischemic_registry,
    linked_patient_precision,
    registry_patient_ids_from_fin_crosswalk,
)


def _prepare_registry_truth(args: argparse.Namespace) -> pd.Series:
    registry = read_table(
        args.registry,
        dtype={args.registry_fin_col: "string"},
    )
    conversion = read_table(
        args.registry_conversion,
        dtype={
            args.conversion_fin_col: "string",
            args.conversion_patient_col: "string",
        },
    )
    registry = filter_primary_ischemic_registry(
        registry,
        diagnosis_col=args.registry_diagnosis_col,
        stroke_type_col=args.registry_type_col,
    )
    return registry_patient_ids_from_fin_crosswalk(
        registry,
        conversion,
        registry_fin_col=args.registry_fin_col,
        conversion_fin_col=args.conversion_fin_col,
        conversion_patient_col=args.conversion_patient_col,
        patient_prefix=args.patient_prefix or None,
    )


def _score(
    label: str,
    df: pd.DataFrame,
    truth: pd.Series,
    expected: pd.DataFrame | None,
) -> pd.DataFrame:
    result = linked_patient_precision(
        df,
        truth,
        patient_col="patient_id",
        include_exploratory=True,
    )
    result.insert(0, "variant", label)
    if expected is not None:
        result = result.merge(expected, on="definition", how="left")
        result["difference_pp"] = 100 * (
            result["precision"] - result["expected_precision"]
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ehr", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-conversion", required=True)
    parser.add_argument("--registry-fin-col", default="FIN")
    parser.add_argument("--conversion-fin-col", default="FIN")
    parser.add_argument("--conversion-patient-col", default="PAT_ID")
    parser.add_argument("--registry-diagnosis-col", default="Diagnosis")
    parser.add_argument("--registry-type-col", default="Type")
    parser.add_argument("--patient-prefix", default="PSU")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument(
        "--expected",
        default="reference/center1_precision_expected.csv",
    )
    args = parser.parse_args()

    ehr = read_table(
        args.ehr,
        dtype={"patient_id": "string", "encounter_id": "string"},
    ).copy()
    ehr["admit_date"] = pd.to_datetime(ehr["admit_date"], errors="raise")
    ehr = ehr[
        (ehr["admit_date"] >= pd.Timestamp(args.start_date))
        & (ehr["admit_date"] <= pd.Timestamp(args.end_date))
    ].copy()

    truth = _prepare_registry_truth(args)

    expected = None
    expected_path = Path(args.expected)
    if expected_path.exists():
        expected = pd.read_csv(expected_path).rename(
            columns={"precision": "expected_precision"}
        )

    data_dir = Path(args.data_dir)
    diagnosis = pd.read_parquet(
        data_dir / "diagnosis.parquet",
        columns=["PATID", "ENCOUNTERID", "DX", "PDX"],
    )
    encounter = pd.read_parquet(
        data_dir / "encounter.parquet",
        columns=[
            "PATID", "ENCOUNTERID", "ADMIT_DATE", "DISCHARGE_DATE"
        ],
    )
    demographic = pd.read_parquet(
        data_dir / "demographic.parquet",
        columns=["PATID", "BIRTH_DATE"],
    )

    for df in (diagnosis, encounter, demographic):
        df["PATID"] = df["PATID"].astype("string").str.strip()
    diagnosis["ENCOUNTERID"] = (
        diagnosis["ENCOUNTERID"].astype("string").str.strip()
    )
    encounter["ENCOUNTERID"] = (
        encounter["ENCOUNTERID"].astype("string").str.strip()
    )

    stroke_codes = set(ISCHEMIC_STROKE_ICD9) | set(ISCHEMIC_STROKE_ICD10)
    primary_dx = diagnosis[
        diagnosis["DX"].astype("string").isin(stroke_codes)
        & diagnosis["PDX"].astype("string").str.strip().eq("P")
    ]
    primary_keys = set(
        zip(
            primary_dx["PATID"].astype(str),
            primary_dx["ENCOUNTERID"].astype(str),
        )
    )

    ehr_keys = list(
        zip(
            ehr["patient_id"].astype(str),
            ehr["encounter_id"].astype(str),
        )
    )
    primary_mask = pd.Series(
        [key in primary_keys for key in ehr_keys],
        index=ehr.index,
    )

    birth = (
        demographic.dropna(subset=["PATID"])
        .drop_duplicates("PATID", keep="first")
        .set_index("PATID")["BIRTH_DATE"]
    )
    birth = pd.to_datetime(birth, errors="coerce")
    ehr_birth = pd.to_datetime(ehr["patient_id"].map(birth), errors="coerce")
    age_days = (ehr["admit_date"] - ehr_birth).dt.days
    adult_mask = age_days.ge(18 * 365.25)

    enc = encounter.drop_duplicates(
        ["PATID", "ENCOUNTERID"], keep="first"
    ).copy()
    enc["ADMIT_DATE"] = pd.to_datetime(enc["ADMIT_DATE"], errors="coerce")
    enc["DISCHARGE_DATE"] = pd.to_datetime(
        enc["DISCHARGE_DATE"], errors="coerce"
    )
    enc["los_days"] = (
        enc["DISCHARGE_DATE"] - enc["ADMIT_DATE"]
    ).dt.total_seconds() / 86400
    los_by_key = {
        (str(r.PATID), str(r.ENCOUNTERID)): r.los_days
        for r in enc.itertuples()
    }
    los = pd.Series(
        [los_by_key.get(key, float("nan")) for key in ehr_keys],
        index=ehr.index,
        dtype=float,
    )
    los_ge_1_mask = los.ge(1.0)

    variants = {
        "current": pd.Series(True, index=ehr.index),
        "primary_PDX": primary_mask,
        "adult": adult_mask,
        "LOS_ge_1_day": los_ge_1_mask,
        "primary_PDX+adult": primary_mask & adult_mask,
        "primary_PDX+LOS": primary_mask & los_ge_1_mask,
        "adult+LOS": adult_mask & los_ge_1_mask,
        "primary_PDX+adult+LOS": (
            primary_mask & adult_mask & los_ge_1_mask
        ),
    }

    outputs = []
    for label, mask in variants.items():
        subset = ehr.loc[mask].copy()
        outputs.append(_score(label, subset, truth, expected))

    combined = pd.concat(outputs, ignore_index=True)

    print(f"EHR rows in requested window: {len(ehr):,}")
    print(f"Unique linked registry patient IDs: {truth.nunique():,}")
    print()
    print("Cohort sizes:")
    for label, mask in variants.items():
        print(f"  {label}: {int(mask.sum()):,}")

    show_defs = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"]
    table = combined[combined["definition"].isin(show_defs)].copy()
    table["PPV_percent"] = 100 * table["precision"]

    cols = [
        "variant", "definition", "definition_positive",
        "matched_registry", "PPV_percent",
    ]
    if expected is not None:
        table["expected_percent"] = 100 * table["expected_precision"]
        cols += ["expected_percent", "difference_pp"]

    print()
    print(table[cols].to_string(index=False))

    if expected is not None:
        primary_defs = table["definition"].isin(
            [f"D{i}" for i in range(9)]
        )
        summary = (
            table.loc[primary_defs]
            .groupby("variant", as_index=False)["difference_pp"]
            .agg(
                mean_difference_pp="mean",
                mean_abs_difference_pp=lambda x: x.abs().mean(),
                max_abs_difference_pp=lambda x: x.abs().max(),
            )
            .sort_values("mean_abs_difference_pp")
        )
        print()
        print("Regression-distance summary, lower is closer:")
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
