#!/usr/bin/env python
"""Convert legacy Geisinger aggregate pivot exports to monthly D0-D8 tables."""

from __future__ import annotations

import argparse

import pandas as pd

from stroke_phenotype.geisinger import build_geisinger_monthly_table
from stroke_phenotype.io import write_table
from stroke_phenotype.metrics import compute_count_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conditions", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM")
    parser.add_argument("--end", required=True, help="YYYY-MM")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    conditions = pd.read_csv(args.conditions)
    registry = pd.read_csv(args.registry)

    out = build_geisinger_monthly_table(
        conditions,
        registry,
        start=args.start,
        end=args.end,
    )
    write_table(out, args.out)

    metrics = compute_count_metrics(out)
    print(f"Wrote {len(out)} rows: {out['month'].min()} to {out['month'].max()}")
    print()
    print(
        metrics[
            [
                "definition",
                "n_months",
                "definition_total",
                "registry_mean_monthly",
                "MAE",
                "nMAE",
                "nMAE_percent",
                "Pearson_r",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
