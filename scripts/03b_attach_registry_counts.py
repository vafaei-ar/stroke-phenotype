#!/usr/bin/env python
"""Attach a monthly registry reference series to generated phenotype counts."""

from __future__ import annotations

import argparse

from stroke_phenotype.io import read_table, write_table
from stroke_phenotype.registry import align_counts_to_registry_months


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

    counts = read_table(args.counts)
    registry = read_table(args.registry_source)

    out, dropped = align_counts_to_registry_months(
        counts,
        registry,
        registry_col=args.registry_col,
    )
    write_table(out, args.out)

    definition_cols = [
        c for c in out.columns
        if c.startswith("D") and c[1:].isdigit()
    ]

    print(
        f"Wrote {len(out):,} registry-aligned monthly rows "
        f"to {args.out}"
    )
    if dropped:
        print(
            f"Dropped {len(dropped):,} phenotype-only months outside "
            "the registry observation window."
        )
        print(
            f"Registry window: {out['month'].min()} to {out['month'].max()}"
        )
    print("Definitions:", ", ".join(definition_cols))


if __name__ == "__main__":
    main()
