#!/usr/bin/env python
"""Generate manuscript-facing tables and compare them with aggregate reference values."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from stroke_phenotype.io import read_table


def compare_reference(current: pd.DataFrame, reference: pd.DataFrame, keys: list[str], values: list[str]) -> pd.DataFrame:
    merged = reference.merge(current, on=keys, how="left", suffixes=("_expected", "_current"))
    for value in values:
        if f"{value}_expected" in merged and f"{value}_current" in merged:
            merged[f"{value}_delta"] = merged[f"{value}_current"] - merged[f"{value}_expected"]
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--linked", required=True)
    parser.add_argument("--count", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    linked = read_table(args.linked)
    count = read_table(args.count)

    linked_primary = linked[linked["definition"].str.match(r"D[0-8]$")].copy()
    linked_primary.to_csv(outdir / "center1_precision_all_definitions.csv", index=False)

    selected = count[count["definition"].isin(["D0", "D1", "D3", "D6"])].copy()
    selected.to_csv(outdir / "count_validation_selected_definitions.csv", index=False)

    ref_precision = pd.read_csv(root / "reference" / "center1_precision_expected.csv")
    ref_count = pd.read_csv(root / "reference" / "manuscript_table3_expected.csv")

    precision_check = compare_reference(linked_primary, ref_precision, ["definition"], ["precision"])
    count_check = compare_reference(count, ref_count, ["center", "definition"], ["MAE", "Pearson_r"])

    precision_check.to_csv(outdir / "precision_regression_check.csv", index=False)
    count_check.to_csv(outdir / "count_regression_check.csv", index=False)

    max_precision_delta = precision_check["precision_delta"].abs().max(skipna=True)
    max_mae_delta = count_check["MAE_delta"].abs().max(skipna=True)
    max_r_delta = count_check["Pearson_r_delta"].abs().max(skipna=True)

    print("Aggregate manuscript regression checks")
    print(f"  max |precision delta|: {max_precision_delta:.4f}")
    print(f"  max |MAE delta|:       {max_mae_delta:.4f}")
    print(f"  max |r delta|:         {max_r_delta:.4f}")
    thresholds = [(max_precision_delta, 0.02), (max_mae_delta, 0.10), (max_r_delta, 0.02)]
    if any(np.isfinite(v) and v > t for v, t in thresholds):
        print("WARNING: current aggregate outputs differ from the manuscript reference values.")


if __name__ == "__main__":
    main()
