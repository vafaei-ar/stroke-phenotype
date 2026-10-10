#!/usr/bin/env python
"""Compare clean Center 1 monthly counts with the legacy manuscript input table."""

from __future__ import annotations

import argparse

import pandas as pd


def standardize_month(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a month/date/index-like column to YYYY-MM strings."""
    out = df.copy()

    if "month" in out.columns:
        source = "month"
    elif "date" in out.columns:
        source = "date"
    else:
        unnamed = [c for c in out.columns if str(c).startswith("Unnamed")]
        if not unnamed:
            raise ValueError(f"Cannot identify month column: {out.columns.tolist()}")
        source = unnamed[0]

    out = out.rename(columns={source: "month"})
    out["month"] = (
        pd.to_datetime(out["month"].astype(str), errors="raise")
        .dt.to_period("M")
        .astype(str)
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", required=True, help="Legacy PS_conditions.csv")
    parser.add_argument("--current", required=True, help="Clean monthly-count output")
    parser.add_argument(
        "--definitions",
        nargs="+",
        default=[f"D{i}" for i in range(9)],
        help="Definitions to compare (default: D0-D8)",
    )
    args = parser.parse_args()

    old = standardize_month(pd.read_csv(args.legacy))
    new = standardize_month(pd.read_csv(args.current))

    missing_old = [d for d in args.definitions if d not in old.columns]
    missing_new = [d for d in args.definitions if d not in new.columns]
    if missing_old or missing_new:
        raise KeyError(
            f"Missing definitions. legacy={missing_old or 'none'}, current={missing_new or 'none'}"
        )

    comparison = old[["month", *args.definitions]].merge(
        new[["month", *args.definitions]],
        on="month",
        suffixes=("_legacy", "_current"),
        how="inner",
        validate="one_to_one",
    )

    print(
        "Months compared:",
        comparison["month"].min(),
        "to",
        comparison["month"].max(),
        f"({len(comparison)} months)",
    )
    print()

    all_exact = True
    differences: list[tuple[str, pd.DataFrame]] = []

    for definition in args.definitions:
        old_col = f"{definition}_legacy"
        new_col = f"{definition}_current"
        diff = comparison[new_col] - comparison[old_col]
        exact = bool((diff.fillna(0) == 0).all())
        all_exact = all_exact and exact

        print(
            f"{definition}: "
            f"max_abs_diff={diff.abs().max():.0f}, "
            f"total_legacy={comparison[old_col].sum():.0f}, "
            f"total_current={comparison[new_col].sum():.0f}"
        )

        bad = comparison.loc[diff != 0, ["month", old_col, new_col]].copy()
        if not bad.empty:
            differences.append((definition, bad))

    print()
    print("EXACT MATCH:", all_exact)

    if differences:
        print("\nDiffering months:")
        for definition, bad in differences:
            print(f"\n{definition}")
            print(bad.to_string(index=False))

    return 0 if all_exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
