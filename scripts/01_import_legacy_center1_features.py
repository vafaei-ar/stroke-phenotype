#!/usr/bin/env python
"""Import the legacy Center 1 intermediate feature table into canonical schema.

This is a compatibility bridge for reproducing the current manuscript before
raw EHR extraction is fully refactored out of the historical notebooks.
"""

from __future__ import annotations

import argparse

from stroke_phenotype.io import read_table, write_table
from stroke_phenotype.legacy import standardize_legacy_center1_features


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Legacy df_phen_details CSV")
    parser.add_argument("--out", required=True, help="Canonical output CSV/Parquet")
    parser.add_argument(
        "--facility-contains",
        default=None,
        help="Optional local facility substring; do not commit institution-specific values",
    )
    parser.add_argument(
        "--keep-all-events",
        action="store_true",
        help="Do not apply the manuscript first-qualifying-event rule",
    )
    args = parser.parse_args()

    legacy = read_table(args.input)
    features = standardize_legacy_center1_features(
        legacy,
        facility_contains=args.facility_contains,
        first_event_only=not args.keep_all_events,
    )
    write_table(features, args.out)

    print(f"Wrote {len(features):,} standardized rows to {args.out}")
    print(f"Unique patients: {features['patient_id'].nunique():,}")


if __name__ == "__main__":
    main()
