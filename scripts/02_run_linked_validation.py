#!/usr/bin/env python
"""Run Center 1 linked precision/PPV analysis."""

from __future__ import annotations

import argparse

import pandas as pd

from stroke_phenotype.cohort import select_first_qualifying_encounter
from stroke_phenotype.io import read_table, write_table
from stroke_phenotype.linkage import (
    filter_primary_ischemic_registry,
    linked_patient_precision,
    linked_precision,
    registry_patient_ids_from_fin_crosswalk,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ehr", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--out", required=True)

    parser.add_argument("--patient-col", default="patient_id")
    parser.add_argument("--encounter-col", default="encounter_id")
    parser.add_argument("--date-col", default="admit_date")

    parser.add_argument("--registry-encounter-col", default="encounter_id")
    parser.add_argument("--registry-diagnosis-col", default="diagnosis")
    parser.add_argument("--registry-type-col", default="stroke_type")

    parser.add_argument(
        "--registry-conversion",
        help="FIN-to-EHR-patient crosswalk for historical Center 1 linkage",
    )
    parser.add_argument("--registry-fin-col", default="FIN")
    parser.add_argument("--conversion-fin-col", default="FIN")
    parser.add_argument("--conversion-patient-col", default="PAT_ID")
    parser.add_argument("--patient-prefix", default="PSU")

    parser.add_argument("--start-date", help="Inclusive YYYY-MM-DD")
    parser.add_argument("--end-date", help="Inclusive YYYY-MM-DD")
    parser.add_argument("--include-exploratory", action="store_true")
    args = parser.parse_args()

    ehr_dtype = {
        args.patient_col: "string",
        args.encounter_col: "string",
    }
    registry_dtype = {
        args.registry_encounter_col: "string",
        args.registry_fin_col: "string",
    }

    ehr = read_table(args.ehr, dtype=ehr_dtype)
    registry = read_table(args.registry, dtype=registry_dtype)

    registry = filter_primary_ischemic_registry(
        registry,
        diagnosis_col=args.registry_diagnosis_col,
        stroke_type_col=args.registry_type_col,
    )

    if args.date_col not in ehr.columns:
        raise KeyError(f"EHR date column not found: {args.date_col!r}")

    ehr = ehr.copy()
    ehr[args.date_col] = pd.to_datetime(ehr[args.date_col], errors="raise")

    if args.start_date:
        ehr = ehr[ehr[args.date_col] >= pd.Timestamp(args.start_date)]
    if args.end_date:
        ehr = ehr[ehr[args.date_col] <= pd.Timestamp(args.end_date)]

    ehr = select_first_qualifying_encounter(
        ehr,
        patient_col=args.patient_col,
        date_col=args.date_col,
    )

    if args.registry_conversion:
        conversion = read_table(
            args.registry_conversion,
            dtype={
                args.conversion_fin_col: "string",
                args.conversion_patient_col: "string",
            },
        )
        registry_patient_ids = registry_patient_ids_from_fin_crosswalk(
            registry,
            conversion,
            registry_fin_col=args.registry_fin_col,
            conversion_fin_col=args.conversion_fin_col,
            conversion_patient_col=args.conversion_patient_col,
            patient_prefix=args.patient_prefix or None,
        )
        result = linked_patient_precision(
            ehr,
            registry_patient_ids,
            patient_col=args.patient_col,
            include_exploratory=args.include_exploratory,
        )
        linkage_description = (
            f"FIN crosswalk to {args.conversion_patient_col}, "
            f"then patient-level membership"
        )
        registry_linked_n = int(registry_patient_ids.nunique())
    else:
        result = linked_precision(
            ehr,
            registry,
            encounter_col=args.encounter_col,
            registry_encounter_col=args.registry_encounter_col,
            include_exploratory=args.include_exploratory,
        )
        linkage_description = (
            f"direct {args.encounter_col} to {args.registry_encounter_col}"
        )
        registry_linked_n = int(
            registry[args.registry_encounter_col].dropna().astype(str).nunique()
        )

    write_table(result, args.out)

    print(
        f"EHR rows after date filtering and first-event selection: {len(ehr):,}"
    )
    print(
        f"Primary ischemic registry rows before linkage: {len(registry):,}"
    )
    print(f"Linkage: {linkage_description}")
    print(f"Unique linked registry identifiers: {registry_linked_n:,}")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
