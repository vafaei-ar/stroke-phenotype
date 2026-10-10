#!/usr/bin/env python
"""Build monthly D0-D8 counts from a standardized patient-level feature table."""

from __future__ import annotations

import argparse

from stroke_phenotype.aggregation import build_monthly_definition_counts
from stroke_phenotype.io import read_table, write_table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--patient-col", default="patient_id")
    parser.add_argument("--date-col", default="admit_date")
    parser.add_argument("--include-exploratory", action="store_true")
    args = parser.parse_args()

    features = read_table(args.features)
    counts = build_monthly_definition_counts(
        features,
        patient_col=args.patient_col,
        date_col=args.date_col,
        include_exploratory=args.include_exploratory,
        first_event_only=True,
    )
    out = counts.reset_index().rename(columns={"index": "month"})
    out["month"] = out["month"].astype(str)
    write_table(out, args.out)


if __name__ == "__main__":
    main()
