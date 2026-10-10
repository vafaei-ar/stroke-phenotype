"""Helpers for aligning phenotype and registry monthly count tables."""

from __future__ import annotations

import pandas as pd


def standardize_month_column(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a month/date/index-like column to YYYY-MM strings."""
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


def align_counts_to_registry_months(
    counts: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    registry_col: str = "SR",
) -> tuple[pd.DataFrame, list[str]]:
    """Align generated phenotype counts to the registry observation months.

    Generated phenotype tables may cover a wider time range than the registry.
    Validation should use the registry observation window, so extra phenotype
    months are dropped. Every registry month must still have phenotype counts.
    """
    counts = standardize_month_column(counts)
    registry = standardize_month_column(registry)

    if registry_col not in registry.columns:
        raise KeyError(f"Registry column {registry_col!r} not found")

    registry_reference = registry[["month", registry_col]].copy()
    if registry_reference[registry_col].isna().any():
        months = registry_reference.loc[
            registry_reference[registry_col].isna(), "month"
        ].tolist()
        raise ValueError(
            "Registry reference has missing counts for months: "
            f"{months[:10]}"
        )

    count_months = set(counts["month"])
    registry_months = set(registry_reference["month"])
    missing_count_months = sorted(registry_months - count_months)
    if missing_count_months:
        raise ValueError(
            "Generated phenotype counts are missing registry months: "
            f"{missing_count_months[:10]}"
        )

    dropped_count_months = sorted(count_months - registry_months)

    merged = registry_reference.merge(
        counts,
        on="month",
        how="left",
        validate="one_to_one",
    )

    definition_cols = [
        c for c in merged.columns
        if c.startswith("D") and c[1:].isdigit()
    ]
    out = merged[["month", registry_col, *definition_cols]].copy()
    return out, dropped_count_months
