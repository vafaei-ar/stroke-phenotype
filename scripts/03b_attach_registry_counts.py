#!/usr/bin/env python
"""Attach a monthly registry reference series to generated phenotype counts."""

from __future__ import annotations

import argparse

import pandas as pd

from stroke_phenotype.io import read_table, write_table


def _standardize_month(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "month" in out.columns:
        source = "month"
    elif "date" in out.columns:
        source = "date"
    else:
        unnamed = [c for c in out.columns if str(c).startswith("Unnamed")]
        if not unnamed:
            raise ValueError(
                f"Cannot identify a month/date column: {out.columns.tolist()}"
            )
        source = unnamed[0]

    out = out.rename(columns={source: "month"})
    out["month"] = (
        pd.to_datetime(out["month"].astype(str), errors="raise")
        .dt.to_period("M")
        .astype(str)
    )
    if out["month"].duplicated().any():
        dup = out.loc[out["month"].duplicated(), "month"].tolist()[:5]
        raise ValueError(f"Duplicate months found: {dup}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--counts",
        required=True,
        help="Generated monthly phenotype-count table",
    )
    parser.add_argument(
        "--registry-source",
        required=True,
        help="Monthly table containing the registry reference series",
    )
    parser.add_argument(
        "--registry-col",
        default="SR",
        help="Registry count column in --registry-source (default: SR)",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    counts = _standardize_month(read_table(args.counts))
    registry = _standardize_month(read_table(args.registry_source))

    if args.registry_col not in registry.columns:
        raise KeyError(
            f"Registry column {args.registry_col!r} not found in "
            f"{args.registry_source}"
        )

    merged = counts.merge(
        registry[["month", args.registry_col]],
        on="month",
        how="left",
        validate="one_to_one",
    )
    missing = merged[args.registry_col].isna()
    if missing.any():
        months = merged.loc[missing, "month"].tolist()
        raise ValueError(
            "Registry counts are missing for generated phenotype months: "
            f"{months[:10]}"
        )

    definition_cols = [
        c for c in merged.columns if c.startswith("D") and c[1:].isdigit()
    ]
    out = merged[["month", args.registry_col, *definition_cols]].copy()
    write_table(out, args.out)

    print(
        f"Wrote {len(out):,} monthly rows with registry reference "
        f"to {args.out}"
    )
    print(
        "Definitions:",
        ", ".join(definition_cols),
    )


if __name__ == "__main__":
    main()
