#!/usr/bin/env python
"""Audit an aggregate external-center monthly count file without exposing PHI."""

from __future__ import annotations

import argparse

import pandas as pd

from stroke_phenotype.metrics import compute_count_metrics
from stroke_phenotype.registry import standardize_month_column


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--registry-col", default="SR")
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    df = standardize_month_column(df)

    if args.start:
        df = df[df["month"] >= pd.Period(args.start, freq="M").strftime("%Y-%m")]
    if args.end:
        df = df[df["month"] <= pd.Period(args.end, freq="M").strftime("%Y-%m")]

    if args.registry_col not in df.columns:
        raise KeyError(f"Registry column {args.registry_col!r} not found")

    definitions = [
        c for c in df.columns
        if c.startswith("D") and c[1:].isdigit()
    ]

    print(f"Rows/months: {len(df)}")
    print(f"Window: {df['month'].min()} to {df['month'].max()}")
    print()

    print("Definition availability:")
    for definition in definitions:
        values = pd.to_numeric(df[definition], errors="coerce")
        nonmissing = int(values.notna().sum())
        nonzero = int((values.fillna(0) > 0).sum())
        total = float(values.sum(skipna=True))
        print(
            f"  {definition}: nonmissing_months={nonmissing}, "
            f"nonzero_months={nonzero}, total={total:.0f}"
        )

    print()
    metrics = compute_count_metrics(
        df,
        registry_col=args.registry_col,
        definitions=definitions,
    )
    show = metrics[
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
    ]
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
