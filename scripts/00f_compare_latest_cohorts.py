#!/usr/bin/env python
"""Compare the latest patient-level stroke cohorts with manuscript checkpoints.

The latest PSU and Geisinger Parquet files contain one row per patient, anchored
to a first broad stroke encounter, with already-derived imaging/lipid/rehab
features. This script:

1. identifies whether the index DX itself meets the manuscript ischemic D0 rule;
2. applies D0-D9 using the existing binary feature columns, treating only value 1
   as present (so -1 is never accidentally truthy);
3. compares PSU totals in the historical Center 1 count window with stored
   aggregate checkpoints;
4. reports PSU registry-linkage proportions as a provenance diagnostic, NOT as
   PPV unless registry membership is confirmed to mean ischemic-stroke truth;
5. prints aggregate Geisinger department frequencies and, if regex patterns are
   supplied, compares GMC/GCMC-derived sites with Center 2/3 checkpoints.

No patient identifiers or row-level records are printed.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from stroke_phenotype.codes import ISCHEMIC_STROKE_ICD9, ISCHEMIC_STROKE_ICD10


DEFINITIONS = [f"D{i}" for i in range(10)]

PSU_START = pd.Timestamp("2016-12-01")
PSU_END = pd.Timestamp("2023-12-31")
PSU_LINK_START = pd.Timestamp("2018-02-01")
PSU_LINK_END = pd.Timestamp("2019-01-31")

CENTER_WINDOWS = {
    "Center 2": (pd.Timestamp("2017-01-01"), pd.Timestamp("2022-07-31")),
    "Center 3": (pd.Timestamp("2016-03-01"), pd.Timestamp("2022-07-31")),
}


def _norm_code(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


ICD9_NORM = {_norm_code(x) for x in ISCHEMIC_STROKE_ICD9}
ICD10_NORM = {_norm_code(x) for x in ISCHEMIC_STROKE_ICD10}


def _ischemic_index_dx(series: pd.Series) -> pd.Series:
    norm = series.map(_norm_code)
    # Manuscript rule: ICD-10 I63 family + H34.1, plus the historical ICD-9 set.
    return (
        norm.str.startswith("I63")
        | norm.eq("H341")
        | norm.isin(ICD9_NORM)
    )


def _flag(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        raise KeyError(f"Required feature column missing: {column}")
    numeric = pd.to_numeric(df[column], errors="coerce")
    return numeric.eq(1)


def _definition_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    d0 = _ischemic_index_dx(df["DX"])
    ct = _flag(df, "has_ct")
    mri = _flag(df, "has_mri")
    lipid = _flag(df, "has_lipid_panel")
    rehab = _flag(df, "has_rehabilitation")
    imaging = ct | mri

    return {
        "D0": d0,
        "D1": d0 & imaging & lipid,
        "D2": d0 & imaging & (lipid | rehab),
        "D3": d0 & mri & lipid,
        "D4": d0 & mri & (lipid | rehab),
        "D5": d0 & imaging,
        "D6": d0 & mri & lipid & rehab,
        "D7": d0 & mri,
        "D8": d0 & ct & lipid,
        "D9": d0 & imaging & lipid & rehab,
    }


def _date_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    dates = pd.to_datetime(df["DX_DATE_stroke"], errors="coerce")
    return dates.between(start, end, inclusive="both")


def _definition_counts(df: pd.DataFrame, row_mask: pd.Series | None = None) -> pd.DataFrame:
    if row_mask is None:
        row_mask = pd.Series(True, index=df.index)
    masks = _definition_masks(df)
    rows = []
    for definition in DEFINITIONS:
        rows.append({
            "definition": definition,
            "count": int((row_mask & masks[definition]).sum()),
        })
    return pd.DataFrame(rows)


def _load_expected(path: Path, center: str | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if center is not None and "center" in df.columns:
        df = df[df["center"].eq(center)].copy()
    cols = ["definition", "definition_total"]
    if not set(cols).issubset(df.columns):
        return pd.DataFrame()
    return df[cols].rename(columns={"definition_total": "historical_total"})


def _compare_counts(observed: pd.DataFrame, expected: pd.DataFrame) -> pd.DataFrame:
    out = observed.copy()
    if expected.empty:
        out["historical_total"] = np.nan
        out["difference"] = np.nan
        out["ratio_to_historical"] = np.nan
        return out

    out = out.merge(expected, on="definition", how="left")
    out["difference"] = out["count"] - out["historical_total"]
    out["ratio_to_historical"] = out["count"] / out["historical_total"]
    return out


def _print_flag_state_counts(df: pd.DataFrame, label: str) -> None:
    print(label)
    for col in [
        "has_ct",
        "has_mri",
        "has_cta",
        "has_mra",
        "has_ctp",
        "has_neuroimaging",
        "has_vascular_imaging",
        "has_lipid_panel",
        "has_rehabilitation",
        "phenotype_strict_eligible",
        "in_stroke_registry",
    ]:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        print(
            f"{col:28s} "
            f"-1={int(s.eq(-1).sum()):6d} "
            f"0={int(s.eq(0).sum()):6d} "
            f"1={int(s.eq(1).sum()):6d} "
            f"other/missing={int((~s.isin([-1,0,1])).sum()):6d}"
        )
    print()


def _dx_audit(df: pd.DataFrame, label: str) -> None:
    d0 = _ischemic_index_dx(df["DX"])
    strict = _flag(df, "phenotype_strict_eligible") if "phenotype_strict_eligible" in df.columns else None
    alt = _flag(df, "has_alt_qualifying_stroke_encounter") if "has_alt_qualifying_stroke_encounter" in df.columns else None

    print(label)
    print(f"rows/patients: {len(df):,}")
    print(f"index DX meets manuscript ischemic D0 rule: {int(d0.sum()):,} ({100*d0.mean():.2f}%)")
    if strict is not None:
        print(f"phenotype_strict_eligible=1: {int(strict.sum()):,} ({100*strict.mean():.2f}%)")
        print(f"D0 index-DX AND strict eligible: {int((d0 & strict).sum()):,}")
        print(f"D0 index-DX but NOT strict eligible: {int((d0 & ~strict).sum()):,}")
        print(f"strict eligible but index DX NOT D0: {int((strict & ~d0).sum()):,}")
    if alt is not None:
        print(f"has_alt_qualifying_stroke_encounter=1: {int(alt.sum()):,} ({100*alt.mean():.2f}%)")
    print()


def _psu_registry_linkage(df: pd.DataFrame) -> None:
    if "in_stroke_registry" not in df.columns:
        return
    window = _date_window(df, PSU_LINK_START, PSU_LINK_END)
    linked = _flag(df, "in_stroke_registry")
    masks = _definition_masks(df)

    rows = []
    for definition in DEFINITIONS:
        positive = window & masks[definition]
        n = int(positive.sum())
        matched = int((positive & linked).sum())
        rows.append({
            "definition": definition,
            "definition_positive": n,
            "registry_linked": matched,
            "linkage_proportion": matched / n if n else np.nan,
        })

    print("PSU 2018-02 through 2019-01: registry-linkage diagnostic")
    print("IMPORTANT: linkage_proportion is NOT labeled PPV here.")
    print(pd.DataFrame(rows).to_string(index=False))
    print()


def _geisinger_departments(df: pd.DataFrame, n: int) -> None:
    if "ENC_DEP_NM" not in df.columns:
        return
    dep = df["ENC_DEP_NM"].astype("string").fillna("<missing>")
    counts = dep.value_counts(dropna=False).head(n)
    print(f"GEISINGER ENC_DEP_NM TOP {n} (aggregate patient counts)")
    for name, count in counts.items():
        print(f"{int(count):6d}  {name}")
    print()

    print("GEISINGER DEPARTMENT KEYWORD COUNTS")
    for keyword in [
        "GMC",
        "GCMC",
        "COMMUNITY",
        "MEDICAL CENTER",
        "GEISINGER MEDICAL",
        "GEISINGER COMMUNITY",
        "DANVILLE",
        "SCRANTON",
    ]:
        matched = dep.str.contains(keyword, case=False, regex=False, na=False)
        print(f"{keyword:22s}: {int(matched.sum()):,}")
    print()


def _site_compare(
    df: pd.DataFrame,
    *,
    label: str,
    regex: str,
    center: str,
    expected_path: Path,
) -> None:
    dep = df["ENC_DEP_NM"].astype("string").fillna("")
    site = dep.str.contains(regex, case=False, regex=True, na=False)
    start, end = CENTER_WINDOWS[center]
    window = _date_window(df, start, end)
    selected = site & window

    observed = _definition_counts(df, selected)
    expected = _load_expected(expected_path, center=center)
    compared = _compare_counts(observed, expected)

    print(f"{label} -> {center} candidate mapping")
    print(f"regex: {regex}")
    print(f"patients matching site regex, all dates: {int(site.sum()):,}")
    print(f"patients in manuscript window: {int(selected.sum()):,}")
    print(compared.to_string(index=False))
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--psu",
        default="data/raw/psu_stroke_cohort_unimputed.parquet",
    )
    parser.add_argument(
        "--geisinger",
        default="data/raw/geisinger_stroke_cohort_unimputed.parquet",
    )
    parser.add_argument(
        "--gmc-regex",
        help="Regex matching GMC rows using ENC_DEP_NM. If omitted, no Center 2 comparison is run.",
    )
    parser.add_argument(
        "--gcmc-regex",
        help="Regex matching GCMC rows using ENC_DEP_NM. If omitted, no Center 3 comparison is run.",
    )
    parser.add_argument(
        "--show-geisinger-departments",
        type=int,
        default=60,
    )
    args = parser.parse_args()

    psu_path = Path(args.psu)
    geisinger_path = Path(args.geisinger)

    psu_cols = [
        "PATID", "DX", "DX_DATE_stroke",
        "has_ct", "has_mri", "has_cta", "has_mra", "has_ctp",
        "has_neuroimaging", "has_vascular_imaging",
        "has_lipid_panel", "has_rehabilitation",
        "phenotype_strict_eligible", "has_alt_qualifying_stroke_encounter",
        "in_stroke_registry",
    ]
    geisinger_cols = [
        "PATID", "DX", "DX_DATE_stroke", "ENC_DEP_NM",
        "has_ct", "has_mri", "has_cta", "has_mra", "has_ctp",
        "has_neuroimaging", "has_vascular_imaging",
        "has_lipid_panel", "has_rehabilitation",
        "phenotype_strict_eligible", "has_alt_qualifying_stroke_encounter",
        "in_stroke_registry",
    ]

    psu = pd.read_parquet(psu_path, columns=psu_cols)
    geisinger = pd.read_parquet(geisinger_path, columns=geisinger_cols)

    print("=" * 100)
    print("LATEST COHORT VS MANUSCRIPT CHECKPOINT AUDIT")
    print("=" * 100)
    print("No patient identifiers or row-level records are printed.")
    print()

    _dx_audit(psu, "PSU INDEX-DX / STRICT-ELIGIBILITY AUDIT")
    _print_flag_state_counts(psu, "PSU FEATURE STATE COUNTS")

    psu_window = _date_window(psu, PSU_START, PSU_END)
    psu_observed = _definition_counts(psu, psu_window)
    psu_expected = _load_expected(Path("reference/center1_reviewer_count_expected.csv"))
    psu_compare = _compare_counts(psu_observed, psu_expected)

    print("PSU: current one-row-per-patient cohort in manuscript Center 1 count window")
    print("window: 2016-12-01 through 2023-12-31, based on DX_DATE_stroke")
    print(psu_compare.to_string(index=False))
    print()

    print("PSU: full available current cohort D0-D9 totals")
    print(_definition_counts(psu).to_string(index=False))
    print()

    _psu_registry_linkage(psu)

    _dx_audit(geisinger, "GEISINGER INDEX-DX / STRICT-ELIGIBILITY AUDIT")
    _print_flag_state_counts(geisinger, "GEISINGER FEATURE STATE COUNTS")
    _geisinger_departments(geisinger, args.show_geisinger_departments)

    print("GEISINGER: full current combined cohort D0-D9 totals")
    print(_definition_counts(geisinger).to_string(index=False))
    print()

    expected23 = Path("reference/center23_reviewer_count_expected.csv")
    if args.gmc_regex:
        _site_compare(
            geisinger,
            label="GMC",
            regex=args.gmc_regex,
            center="Center 2",
            expected_path=expected23,
        )
    else:
        print("Center 2 comparison skipped: provide --gmc-regex after reviewing ENC_DEP_NM aggregate names.")
        print()

    if args.gcmc_regex:
        _site_compare(
            geisinger,
            label="GCMC",
            regex=args.gcmc_regex,
            center="Center 3",
            expected_path=expected23,
        )
    else:
        print("Center 3 comparison skipped: provide --gcmc-regex after reviewing ENC_DEP_NM aggregate names.")
        print()

    if args.gmc_regex and args.gcmc_regex:
        dep = geisinger["ENC_DEP_NM"].astype("string").fillna("")
        gmc = dep.str.contains(args.gmc_regex, case=False, regex=True, na=False)
        gcmc = dep.str.contains(args.gcmc_regex, case=False, regex=True, na=False)
        overlap = int((gmc & gcmc).sum())
        neither = int((~gmc & ~gcmc).sum())
        print("GEISINGER SITE-MAPPING SANITY CHECK")
        print(f"GMC/GCMC overlap rows: {overlap:,}")
        print(f"rows matching neither regex: {neither:,}")
        print()


if __name__ == "__main__":
    main()
