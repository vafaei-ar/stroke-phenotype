#!/usr/bin/env python
"""Run Center 1 encounter-linked precision/PPV analysis."""

from __future__ import annotations

import argparse

from stroke_phenotype.cohort import select_first_qualifying_encounter
from stroke_phenotype.io import read_table, write_table
from stroke_phenotype.linkage import filter_primary_ischemic_registry, linked_precision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ehr", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--patient-col", default="patient_id")
    parser.add_argument("--encounter-col", default="encounter_id")
    parser.add_argument("--date-col", default="admit_date")
    parser.add_argument("--include-exploratory", action="store_true")
    args = parser.parse_args()

    ehr = read_table(args.ehr)
    registry = read_table(args.registry)
    registry = filter_primary_ischemic_registry(registry)
    ehr = select_first_qualifying_encounter(
        ehr, patient_col=args.patient_col, date_col=args.date_col
    )
    result = linked_precision(
        ehr,
        registry,
        encounter_col=args.encounter_col,
        include_exploratory=args.include_exploratory,
    )
    write_table(result, args.out)


if __name__ == "__main__":
    main()
