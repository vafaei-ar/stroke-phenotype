#!/usr/bin/env python
"""Prepare legacy-compatible Center 1 features from local PCORnet Parquet files.

All patient-level inputs and outputs remain local. Do not commit generated files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from stroke_phenotype.io import write_table
from stroke_phenotype.raw_center1 import (
    DIAGNOSIS_COLUMNS,
    ENCOUNTER_COLUMNS,
    LAB_COLUMNS,
    PROCEDURE_COLUMNS,
    compare_rehab_reference,
    prepare_legacy_compatible_center1_features,
    read_lipid_codes,
)


def _read_parquet(
    data_dir: Path,
    name: str,
    columns: tuple[str, ...],
) -> pd.DataFrame:
    path = data_dir / name
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path, columns=list(columns))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        required=True,
        help=(
            "Local directory containing diagnosis.parquet, encounter.parquet, "
            "procedures.parquet, and lab_result_cm.parquet"
        ),
    )
    parser.add_argument(
        "--lipid-codes",
        default="reference/lipid_loinc.csv",
        help="Validated lipid LOINC reference CSV",
    )
    parser.add_argument(
        "--rehab-reference",
        help=(
            "Optional rehabilitation reference CSV to compare with the exact "
            "hard-coded legacy notebook list. It is audited but does not alter "
            "legacy reproduction."
        ),
    )
    parser.add_argument(
        "--facility-contains",
        required=True,
        help="Local facility substring. Do not commit site-identifying values.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Canonical local feature output CSV/Parquet",
    )
    parser.add_argument(
        "--legacy-details-out",
        help="Optional protected local reconstruction of df_phen_details.csv",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    diagnosis = _read_parquet(
        data_dir,
        "diagnosis.parquet",
        DIAGNOSIS_COLUMNS,
    )
    encounters = _read_parquet(
        data_dir,
        "encounter.parquet",
        ENCOUNTER_COLUMNS,
    )
    procedures = _read_parquet(
        data_dir,
        "procedures.parquet",
        PROCEDURE_COLUMNS,
    )
    labs = _read_parquet(
        data_dir,
        "lab_result_cm.parquet",
        LAB_COLUMNS,
    )
    lipid_codes = read_lipid_codes(args.lipid_codes)

    if args.rehab_reference:
        missing_from_reference, extra_in_reference = compare_rehab_reference(
            args.rehab_reference
        )
        print("Rehabilitation reference audit:")
        print(
            "  missing from reference vs legacy notebook: "
            f"{sorted(missing_from_reference)}"
        )
        print(
            "  extra in reference vs legacy notebook: "
            f"{sorted(extra_in_reference)}"
        )
        print("  legacy reproduction continues with the exact notebook code list")
        print()

    details, canonical = prepare_legacy_compatible_center1_features(
        diagnosis,
        encounters,
        procedures,
        labs,
        lipid_codes=lipid_codes,
        facility_contains=args.facility_contains,
    )

    if args.legacy_details_out:
        write_table(details, args.legacy_details_out)
        print(
            f"Wrote {len(details):,} protected legacy detail rows "
            f"to {args.legacy_details_out}"
        )

    write_table(canonical, args.out)
    print(f"Wrote {len(canonical):,} standardized rows to {args.out}")
    print(f"Unique patients: {canonical['patient_id'].nunique():,}")
    print("This command preserves historical notebook semantics for regression testing.")


if __name__ == "__main__":
    main()
