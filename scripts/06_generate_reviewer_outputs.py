#!/usr/bin/env python
"""Generate reviewer-facing D6, D9, and normalized-MAE analysis tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from stroke_phenotype.io import read_table


COUNT_COLUMNS = [
    "center",
    "definition",
    "n_months",
    "registry_mean_monthly",
    "definition_mean_monthly",
    "MAE",
    "nMAE",
    "nMAE_percent",
    "Pearson_r",
    "mean_signed_error",
    "total_count_ratio",
]

LINKED_COLUMNS = [
    "definition",
    "definition_positive",
    "matched_registry",
    "precision",
    "PPV",
]


def _evaluable_status(row: pd.Series | None) -> str:
    if row is None:
        return "missing_from_input"
    n_months = pd.to_numeric(row.get("n_months"), errors="coerce")
    if pd.isna(n_months) or int(n_months) == 0:
        return "not_evaluable"
    return "evaluable"


def _definition_rows(
    count: pd.DataFrame,
    definition: str,
    centers: list[str],
) -> pd.DataFrame:
    rows = []
    for center in centers:
        match = count[
            (count["center"] == center)
            & (count["definition"] == definition)
        ]
        if match.empty:
            row = {"center": center, "definition": definition}
            row["status"] = "missing_from_input"
        else:
            source = match.iloc[0]
            row = {
                col: source.get(col, pd.NA)
                for col in COUNT_COLUMNS
            }
            row["status"] = _evaluable_status(source)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--count",
        required=True,
        help="Multicenter count metrics from 04_run_multicenter_validation.py",
    )
    parser.add_argument(
        "--linked",
        help="Optional Center 1 linked metrics including exploratory D9",
    )
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    count = read_table(args.count)
    required = {"center", "definition", "n_months", "MAE", "nMAE", "Pearson_r"}
    missing = sorted(required - set(count.columns))
    if missing:
        raise KeyError(f"Count metric table is missing columns: {missing}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    keep = [c for c in COUNT_COLUMNS if c in count.columns]
    count[keep].to_csv(
        outdir / "reviewer_count_metrics_all_definitions.csv",
        index=False,
    )

    centers = list(dict.fromkeys(count["center"].astype(str).tolist()))
    external_centers = [c for c in centers if c != "Center 1"]

    d6 = _definition_rows(count, "D6", external_centers)
    d6.to_csv(outdir / "reviewer_d6_external.csv", index=False)

    d9_count = _definition_rows(count, "D9", ["Center 1"])
    d9_count.to_csv(outdir / "reviewer_d9_center1_count.csv", index=False)

    if args.linked:
        linked = read_table(args.linked)
        linked_keep = [c for c in LINKED_COLUMNS if c in linked.columns]
        d9_linked = linked[linked["definition"] == "D9"][linked_keep].copy()
        if d9_linked.empty:
            d9_linked = pd.DataFrame(
                [{
                    "definition": "D9",
                    "status": "missing_from_input",
                }]
            )
        else:
            d9_linked.insert(1, "status", "evaluable")
        d9_linked.to_csv(
            outdir / "reviewer_d9_center1_linked.csv",
            index=False,
        )

    core = count[
        count["definition"].isin(["D0", "D1", "D3", "D6", "D9"])
    ].copy()
    if "nMAE_percent" not in core.columns and "nMAE" in core.columns:
        core["nMAE_percent"] = 100 * pd.to_numeric(
            core["nMAE"],
            errors="coerce",
        )
    core.to_csv(outdir / "reviewer_core_summary.csv", index=False)

    print("Reviewer analysis outputs")
    print(f"  all count metrics: {outdir / 'reviewer_count_metrics_all_definitions.csv'}")
    print(f"  external D6:       {outdir / 'reviewer_d6_external.csv'}")
    print(f"  Center 1 D9 count: {outdir / 'reviewer_d9_center1_count.csv'}")
    if args.linked:
        print(f"  Center 1 D9 linked:{outdir / 'reviewer_d9_center1_linked.csv'}")
    print(f"  core summary:      {outdir / 'reviewer_core_summary.csv'}")
    print()
    print("External D6 status:")
    print(d6[["center", "status", "MAE", "nMAE", "Pearson_r"]].to_string(index=False))
    print()
    print("Center 1 D9 count status:")
    print(
        d9_count[
            ["center", "status", "MAE", "nMAE", "Pearson_r"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
