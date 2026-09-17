#!/usr/bin/env python
"""Audit the historical Center 1 length-of-stay rule without exposing patient data.

The manuscript describes hospitalizations lasting >24 hours. The historical notebook
first removed same-calendar-day encounters while building intermediate dictionaries,
but later reconstructed the candidate table from a broader encounter dictionary. This
script joins the historical candidate table back to those encounter records and reports
aggregate length-of-stay counts for the exact Center 1 D0 analysis cohort.

No patient or encounter identifiers are printed or written.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", required=True, help="Legacy outcomes/df_phen_details.csv")
    parser.add_argument("--legacy-npy", required=True, help="Legacy data_Sep2024.npy")
    parser.add_argument("--facility-contains", required=True)
    parser.add_argument("--start", default="2016-12-01")
    parser.add_argument("--end", default="2023-12-31")
    args = parser.parse_args()

    features = pd.read_csv(args.features, low_memory=False)
    required = {"PATID", "ENCOUNTERID", "ADMIT_DATE", "FACILITYID"}
    missing = sorted(required - set(features.columns))
    if missing:
        raise KeyError(f"Feature table is missing required columns: {missing}")

    legacy_objects = np.load(args.legacy_npy, allow_pickle=True)
    if len(legacy_objects) < 3:
        raise ValueError("Legacy NPY does not contain the expected encounter dictionary")
    enc_dic = legacy_objects[2]

    encounter_frames = []
    for key in ("is9", "is10"):
        if key in enc_dic:
            encounter_frames.append(enc_dic[key])
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
    encounters = encounters[encounter_columns].drop_duplicates(
        subset=["PATID", "ENCOUNTERID"], keep="first"
    )

    # Preserve the historical order: first event per patient, then facility restriction.
    cohort = _legacy_first_event(features)
    keep = cohort["FACILITYID"].astype("string").str.contains(
        args.facility_contains, case=False, regex=False, na=False
    )
    cohort = cohort.loc[keep].copy()
    cohort["ADMIT_DATE"] = pd.to_datetime(cohort["ADMIT_DATE"], errors="coerce")
    cohort = cohort[
        cohort["ADMIT_DATE"].between(pd.Timestamp(args.start), pd.Timestamp(args.end))
    ].copy()

    # Join only to calculate duration. Identifier columns are never printed.
    joined = cohort[["PATID", "ENCOUNTERID", "ADMIT_DATE"]].merge(
        encounters,
        on=["PATID", "ENCOUNTERID"],
        how="left",
        suffixes=("_feature", "_encounter"),
    )

    date_col = "ADMIT_DATE_encounter" if "ADMIT_DATE_encounter" in joined else "ADMIT_DATE_feature"
    admit_time = joined["ADMIT_TIME"] if "ADMIT_TIME" in joined else None
    discharge_time = joined["DISCHARGE_TIME"] if "DISCHARGE_TIME" in joined else None

    admit_ts = _timestamp(joined[date_col], admit_time)
    discharge_ts = _timestamp(joined["DISCHARGE_DATE"], discharge_time)
    los_hours = (discharge_ts - admit_ts).dt.total_seconds() / 3600.0

    legacy_non_same_day = (
        pd.to_datetime(joined["DISCHARGE_DATE"], errors="coerce").dt.normalize()
        != pd.to_datetime(joined[date_col], errors="coerce").dt.normalize()
    )
    valid = los_hours.notna()
    gt24 = los_hours > 24
    eq24 = los_hours.eq(24)
    lt24 = los_hours < 24

    print(f"Center 1 D0 rows in analysis window: {len(joined):,}")
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


if __name__ == "__main__":
    main()
