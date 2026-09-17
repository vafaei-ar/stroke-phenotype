#!/usr/bin/env python
"""Audit the historical Center 1 length-of-stay rule without exposing patient data.

The manuscript describes hospitalizations lasting >24 hours. The historical notebook
used a non-same-calendar-day rule in part of the cohort construction, which is not
identical to an exact elapsed-time rule. This script reports the historical discrepancy
and, when a legacy monthly count table is supplied, quantifies the effect of enforcing
exact LOS >24 hours on D0-D8 monthly counts and count-based validation metrics.

No patient or encounter identifiers are printed or written.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from stroke_phenotype.aggregation import build_monthly_definition_counts
from stroke_phenotype.legacy import standardize_legacy_center1_features
from stroke_phenotype.metrics import compute_count_metrics

DEFINITIONS = tuple(f"D{i}" for i in range(9))


def _time_delta(series: pd.Series) -> pd.Series:
    """Parse legacy time values, which were stored as seconds from midnight."""
    numeric = pd.to_numeric(series, errors="coerce")
    return pd.to_timedelta(numeric, unit="s")


def _timestamp(date: pd.Series, time: pd.Series | None) -> pd.Series:
    parsed = pd.to_datetime(date, errors="coerce")
    if time is None:
        return parsed

    delta = _time_delta(time)
    with_time = parsed.dt.normalize() + delta
    return with_time.where(delta.notna(), parsed)


def _legacy_first_event(df: pd.DataFrame) -> pd.DataFrame:
    """Match the original notebook's ambiguous first-event selection exactly."""
    out = df.copy()
    out["ADMIT_DATE"] = pd.to_datetime(out["ADMIT_DATE"], errors="coerce")
    return out.sort_values("ADMIT_DATE").drop_duplicates("PATID", keep="first")


def _load_encounters(path: str) -> pd.DataFrame:
    legacy_objects = np.load(path, allow_pickle=True)
    if len(legacy_objects) < 3:
        raise ValueError("Legacy NPY does not contain the expected encounter dictionary")
    enc_dic = legacy_objects[2]

    encounter_frames = [enc_dic[key] for key in ("is9", "is10") if key in enc_dic]
    if not encounter_frames:
        raise KeyError("Legacy encounter dictionary has neither 'is9' nor 'is10'")

    encounters = pd.concat(encounter_frames, ignore_index=True)
    encounter_columns = [
        c
        for c in (
            "PATID",
            "ENCOUNTERID",
            "ADMIT_DATE",
            "DISCHARGE_DATE",
            "ADMIT_TIME",
            "DISCHARGE_TIME",
        )
        if c in encounters.columns
    ]
    return encounters[encounter_columns].drop_duplicates(
        subset=["PATID", "ENCOUNTERID"], keep="first"
    )


def _attach_los(features: pd.DataFrame, encounters: pd.DataFrame) -> pd.DataFrame:
    """Attach exact LOS and historical non-same-day flags to legacy feature rows."""
    out = features.merge(
        encounters,
        on=["PATID", "ENCOUNTERID"],
        how="left",
        suffixes=("", "_encounter"),
        sort=False,
        validate="many_to_one",
    )

    date_col = "ADMIT_DATE_encounter" if "ADMIT_DATE_encounter" in out else "ADMIT_DATE"
    admit_time = out["ADMIT_TIME"] if "ADMIT_TIME" in out else None
    discharge_time = out["DISCHARGE_TIME"] if "DISCHARGE_TIME" in out else None

    admit_ts = _timestamp(out[date_col], admit_time)
    discharge_ts = _timestamp(out["DISCHARGE_DATE"], discharge_time)
    out["_los_hours"] = (discharge_ts - admit_ts).dt.total_seconds() / 3600.0
    out["_legacy_non_same_day"] = (
        pd.to_datetime(out["DISCHARGE_DATE"], errors="coerce").dt.normalize()
        != pd.to_datetime(out[date_col], errors="coerce").dt.normalize()
    )
    return out


def _restrict_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    out = df.copy()
    out["admit_date"] = pd.to_datetime(out["admit_date"], errors="raise")
    return out[out["admit_date"].between(start, end)].copy()


def _monthly_counts(
    features: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    counts = build_monthly_definition_counts(
        features,
        include_exploratory=False,
        first_event_only=False,
    )
    months = pd.period_range(start=start, end=end, freq="M")
    return counts.reindex(months, fill_value=0).reindex(columns=DEFINITIONS, fill_value=0)


def _load_legacy_counts(path: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "month" in df.columns:
        month_col = "month"
    elif "date" in df.columns:
        month_col = "date"
    else:
        raise KeyError("Legacy count table must contain a 'month' or 'date' column")

    df = df.copy()
    df["month"] = pd.to_datetime(df[month_col], errors="raise").dt.to_period("M")
    if df["month"].duplicated().any():
        raise ValueError("Legacy count table has duplicate month rows")
    df = df.set_index("month").sort_index()
    start_month = start.to_period("M")
    end_month = end.to_period("M")
    return df.loc[start_month:end_month].copy()


def _print_sensitivity(
    baseline_features: pd.DataFrame,
    strict_features: pd.DataFrame,
    *,
    legacy_counts_path: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> None:
    baseline = _monthly_counts(baseline_features, start=start, end=end)
    strict = _monthly_counts(strict_features, start=start, end=end)
    legacy = _load_legacy_counts(legacy_counts_path, start, end)

    missing = [c for c in (*DEFINITIONS, "SR") if c not in legacy.columns]
    if missing:
        raise KeyError(f"Legacy count table is missing required columns: {missing}")

    legacy_defs = legacy.reindex(baseline.index)[list(DEFINITIONS)].apply(
        pd.to_numeric, errors="coerce"
    )
    if legacy_defs.isna().any().any():
        raise ValueError("Legacy count table has missing/non-numeric D0-D8 values in analysis window")

    baseline_match = baseline.equals(legacy_defs.astype(int))
    print()
    print("Exact >24-hour eligibility sensitivity")
    print("--------------------------------------")
    print(f"Baseline D0-D8 matches legacy monthly table: {baseline_match}")
    if not baseline_match:
        max_diff = (baseline - legacy_defs).abs().max().max()
        print(f"WARNING: baseline maximum monthly discrepancy vs legacy table: {max_diff:g}")

    print(
        f"Historical standardized cohort in window: {len(baseline_features):,}; "
        f"strict >24-hour cohort in window: {len(strict_features):,}; "
        f"net change: {len(strict_features) - len(baseline_features):+,}"
    )
    print()
    print("D0-D8 totals and monthly-count impact:")
    for definition in DEFINITIONS:
        old_total = int(baseline[definition].sum())
        new_total = int(strict[definition].sum())
        delta = new_total - old_total
        pct = 100.0 * delta / old_total if old_total else float("nan")
        monthly_diff = strict[definition] - baseline[definition]
        n_changed = int(monthly_diff.ne(0).sum())
        max_abs = int(monthly_diff.abs().max())
        print(
            f"{definition}: baseline={old_total:,}, strict={new_total:,}, "
            f"delta={delta:+,} ({pct:+.2f}%), months_changed={n_changed}, "
            f"max_month_abs_diff={max_abs}"
        )

    registry = legacy.reindex(baseline.index)[["SR"]].apply(pd.to_numeric, errors="coerce")
    if registry["SR"].isna().any():
        raise ValueError("Registry count column SR has missing/non-numeric values in analysis window")

    baseline_metrics = compute_count_metrics(
        registry.join(baseline), registry_col="SR", definitions=DEFINITIONS
    ).set_index("definition")
    strict_metrics = compute_count_metrics(
        registry.join(strict), registry_col="SR", definitions=DEFINITIONS
    ).set_index("definition")

    print()
    print("Count-based validation impact (same registry months):")
    for definition in DEFINITIONS:
        old = baseline_metrics.loc[definition]
        new = strict_metrics.loc[definition]
        print(
            f"{definition}: "
            f"MAE {old['MAE']:.2f} -> {new['MAE']:.2f} "
            f"(delta {new['MAE'] - old['MAE']:+.2f}); "
            f"nMAE {old['nMAE']:.3f} -> {new['nMAE']:.3f} "
            f"(delta {new['nMAE'] - old['nMAE']:+.3f}); "
            f"r {old['Pearson_r']:.3f} -> {new['Pearson_r']:.3f} "
            f"(delta {new['Pearson_r'] - old['Pearson_r']:+.3f})"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", required=True, help="Legacy outcomes/df_phen_details.csv")
    parser.add_argument("--legacy-npy", required=True, help="Legacy data_Sep2024.npy")
    parser.add_argument("--facility-contains", required=True)
    parser.add_argument(
        "--legacy-counts",
        help="Optional historical monthly count table (e.g. outcomes/PS_conditions.csv) for D0-D8 sensitivity",
    )
    parser.add_argument("--start", default="2016-12-01")
    parser.add_argument("--end", default="2023-12-31")
    args = parser.parse_args()

    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)

    features = pd.read_csv(args.features, low_memory=False)
    required = {"PATID", "ENCOUNTERID", "ADMIT_DATE", "FACILITYID"}
    missing = sorted(required - set(features.columns))
    if missing:
        raise KeyError(f"Feature table is missing required columns: {missing}")

    encounters = _load_encounters(args.legacy_npy)
    features_with_los = _attach_los(features, encounters)

    # Historical first-event audit: first event, then facility restriction, then window.
    cohort = _legacy_first_event(features_with_los)
    keep = cohort["FACILITYID"].astype("string").str.contains(
        args.facility_contains, case=False, regex=False, na=False
    )
    cohort = cohort.loc[keep].copy()
    cohort["ADMIT_DATE"] = pd.to_datetime(cohort["ADMIT_DATE"], errors="coerce")
    cohort = cohort[cohort["ADMIT_DATE"].between(start, end)].copy()

    los_hours = cohort["_los_hours"]
    legacy_non_same_day = cohort["_legacy_non_same_day"].fillna(False)
    valid = los_hours.notna()
    gt24 = los_hours > 24
    eq24 = los_hours.eq(24)
    lt24 = los_hours < 24

    print(f"Center 1 D0 rows in analysis window: {len(cohort):,}")
    print(f"Rows with calculable length of stay: {int(valid.sum()):,}")
    print(f"Rows with missing/invalid length of stay: {int((~valid).sum()):,}")
    print()
    print(f"Legacy non-same-calendar-day rule: {int(legacy_non_same_day.sum()):,}")
    print(f"Exact LOS >24 hours: {int((valid & gt24).sum()):,}")
    print(f"Exact LOS =24 hours: {int((valid & eq24).sum()):,}")
    print(f"Exact LOS <24 hours: {int((valid & lt24).sum()):,}")
    print()
    print(
        "Legacy included but not >24 hours: "
        f"{int((legacy_non_same_day & valid & ~gt24).sum()):,}"
    )
    print(
        ">24 hours but not legacy non-same-day: "
        f"{int((~legacy_non_same_day & valid & gt24).sum()):,}"
    )

    if valid.any():
        q = los_hours[valid].quantile([0.0, 0.25, 0.5, 0.75, 1.0])
        print()
        print("LOS hours among calculable rows:")
        print(
            f"min={q.loc[0.0]:.2f}, Q1={q.loc[0.25]:.2f}, "
            f"median={q.loc[0.5]:.2f}, Q3={q.loc[0.75]:.2f}, max={q.loc[1.0]:.2f}"
        )

    if args.legacy_counts:
        # Baseline reproduces the historical order exactly.
        baseline_features = standardize_legacy_center1_features(
            features,
            facility_contains=args.facility_contains,
            first_event_only=True,
        )
        baseline_features = _restrict_window(baseline_features, start, end)

        # For the strict sensitivity analysis, LOS >24 h is treated as an eligibility
        # criterion before selecting the first qualifying event. This allows a later
        # >24-hour event to become the first qualifying event if an earlier event was short.
        strict_input = features_with_los.loc[features_with_los["_los_hours"] > 24].copy()
        strict_features = standardize_legacy_center1_features(
            strict_input,
            facility_contains=args.facility_contains,
            first_event_only=True,
        )
        strict_features = _restrict_window(strict_features, start, end)

        _print_sensitivity(
            baseline_features,
            strict_features,
            legacy_counts_path=args.legacy_counts,
            start=start,
            end=end,
        )


if __name__ == "__main__":
    main()
