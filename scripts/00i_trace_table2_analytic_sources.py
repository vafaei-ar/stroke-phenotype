#!/usr/bin/env python
"""Trace patient-level sources needed to rebuild manuscript Table 2.

This is a second-stage, aggregate-only audit.

Goals
-----
1. Center 1:
   Join the reproduced historical first-event feature table to the historical
   demographic source by patient identifier and summarize the exact D0 cohort
   over the manuscript count window.

2. Geisinger:
   Inspect the historical demographics Parquet schema and report only column
   names plus uniqueness/missingness for likely identifier fields so the
   patient-level key can be identified without printing identifiers.

3. Center 4/JHH:
   Inventory structured files under the local JHH analysis directory and print
   schemas/row counts only, to locate a patient-level demographic source.

No patient-level values or identifiers are printed.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


C1_START = pd.Timestamp("2016-12-01")
C1_END = pd.Timestamp("2023-12-31 23:59:59")


def norm_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def normalize_id(series: pd.Series) -> pd.Series:
    out = series.astype("string").str.strip()
    out = out.str.replace(r"\.0$", "", regex=True)
    out = out.mask(out.isin(["", "nan", "None", "<NA>"]))
    return out


def read_table(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path, columns=columns)

    if suffix in {".csv", ".tsv"}:
        sep = "\t" if suffix == ".tsv" else ","
        kwargs = {"sep": sep, "low_memory": False}
        if columns is not None:
            kwargs["usecols"] = columns
        try:
            return pd.read_csv(path, **kwargs)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin-1", **kwargs)

    raise ValueError(f"Unsupported file type: {path}")


def schema_only(path: Path) -> tuple[list[str], int | None]:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        try:
            import pyarrow.parquet as pq

            pf = pq.ParquetFile(path)
            return list(pf.schema_arrow.names), int(pf.metadata.num_rows)
        except Exception:
            df = pd.read_parquet(path)
            return list(df.columns), len(df)

    if suffix in {".csv", ".tsv"}:
        sep = "\t" if suffix == ".tsv" else ","
        try:
            df = pd.read_csv(path, sep=sep, nrows=0)
        except UnicodeDecodeError:
            df = pd.read_csv(path, sep=sep, nrows=0, encoding="latin-1")
        return list(df.columns), None

    raise ValueError(f"Unsupported file type: {path}")


def format_age(age: pd.Series) -> str:
    age = pd.to_numeric(age, errors="coerce").dropna()
    if age.empty:
        return "no nonmissing ages"
    q1, median, q3 = age.quantile([0.25, 0.5, 0.75])
    return (
        f"N={len(age):,}; mean={age.mean():.1f}; SD={age.std(ddof=1):.1f}; "
        f"median={median:.1f}; Q1={q1:.1f}; Q3={q3:.1f}"
    )


def print_counts(series: pd.Series, label: str) -> None:
    print(f"  {label}:")
    counts = (
        series.astype("string")
        .fillna("<missing>")
        .value_counts(dropna=False)
    )
    for value, n in counts.items():
        print(f"    {value}: {int(n):,}")


def center1_summary(features_path: Path, demographics_path: Path) -> None:
    print("=" * 80)
    print("CENTER 1 EXACT ANALYTIC-COHORT DEMOGRAPHIC AUDIT")
    print("=" * 80)

    if not features_path.exists():
        print(f"FEATURE FILE NOT FOUND: {features_path}")
        print(
            "Generate the reproduced Center 1 feature table first, or pass "
            "--center1-features PATH."
        )
        print()
        return

    if not demographics_path.exists():
        print(f"DEMOGRAPHIC FILE NOT FOUND: {demographics_path}")
        print()
        return

    features = read_table(features_path)
    fcols = {norm_name(c): c for c in features.columns}
    patient_col = fcols.get("patientid") or fcols.get("patid")
    admit_col = fcols.get("admitdate")

    if patient_col is None or admit_col is None:
        raise KeyError(
            "Center 1 feature table must contain patient_id/PATID and admit_date"
        )

    features = features[[patient_col, admit_col]].copy()
    features["_patient"] = normalize_id(features[patient_col])
    features["_admit"] = pd.to_datetime(features[admit_col], errors="coerce")
    features = features[
        features["_admit"].between(C1_START, C1_END, inclusive="both")
    ].copy()

    print(f"Feature rows in manuscript window: {len(features):,}")
    print(f"Unique feature patients: {features['_patient'].nunique(dropna=True):,}")
    print(
        "Duplicate patient IDs in feature rows: "
        f"{int(features['_patient'].duplicated(keep=False).sum()):,}"
    )
    print(
        f"Feature date range: {features['_admit'].min().date()} to "
        f"{features['_admit'].max().date()}"
    )

    demo_header, _ = schema_only(demographics_path)
    dmap = {norm_name(c): c for c in demo_header}
    d_patient = dmap.get("patid") or dmap.get("patientid")
    if d_patient is None:
        raise KeyError("Historical Center 1 demographic source has no PATID/patient ID")

    wanted = [d_patient]
    for key in ("birthdate", "sex", "hispanic", "race"):
        if key in dmap:
            wanted.append(dmap[key])

    demo = read_table(demographics_path, wanted)
    demo["_patient"] = normalize_id(demo[d_patient])

    # Keep one demographic row per patient only if repeated rows are identical
    # on the selected fields. Report conflicts rather than silently choosing.
    value_cols = [c for c in wanted if c != d_patient]
    duplicate_patients = int(
        demo.loc[demo["_patient"].duplicated(keep=False), "_patient"].nunique(dropna=True)
    )
    print(f"Historical demographic rows: {len(demo):,}")
    print(f"Unique demographic patients: {demo['_patient'].nunique(dropna=True):,}")
    print(f"Patients with repeated demographic rows: {duplicate_patients:,}")

    conflicts = 0
    if duplicate_patients:
        grouped = demo.dropna(subset=["_patient"]).groupby("_patient", sort=False)
        for col in value_cols:
            conflicts += int((grouped[col].nunique(dropna=False) > 1).sum())
    print(f"Repeated-patient field conflicts across selected demographics: {conflicts:,}")

    demo_one = demo.drop_duplicates(subset=["_patient"], keep="first")
    merged = features.merge(
        demo_one[["_patient"] + value_cols],
        on="_patient",
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    matched = int((merged["_merge"] == "both").sum())
    print(f"Matched analytic patients to demographics: {matched:,}/{len(merged):,}")
    print(f"Match rate: {100 * matched / len(merged):.2f}%")

    birth_col = dmap.get("birthdate")
    if birth_col and birth_col in merged.columns:
        birth = pd.to_datetime(merged[birth_col], errors="coerce")
        age = (merged["_admit"] - birth).dt.days / 365.2425
        age = age.where((age >= 0) & (age <= 120))
        print(f"Age at analytic admission: {format_age(age)}")

    if dmap.get("sex") in merged.columns:
        print_counts(merged[dmap["sex"]], "SEX raw categories")
    if dmap.get("hispanic") in merged.columns:
        print_counts(merged[dmap["hispanic"]], "HISPANIC raw categories")
    if dmap.get("race") in merged.columns:
        print_counts(merged[dmap["race"]], "RACE raw categories")

    print()


def likely_id_columns(columns: list[str]) -> list[str]:
    out: list[str] = []
    tokens = (
        "id",
        "mrn",
        "key",
        "nbr",
        "number",
        "num",
        "pat",
        "patient",
        "person",
        "empi",
        "member",
        "subject",
    )
    for col in columns:
        n = norm_name(col)
        if any(token in n for token in tokens):
            out.append(col)
    return out


def geisinger_summary(path: Path) -> None:
    print("=" * 80)
    print("GEISINGER DEMOGRAPHIC KEY AUDIT")
    print("=" * 80)
    if not path.exists():
        print(f"FILE NOT FOUND: {path}")
        print()
        return

    columns, rows = schema_only(path)
    print(f"File: {path}")
    print(f"Rows from metadata: {rows:,}" if rows is not None else "Rows: unknown")
    print("All columns:")
    for col in columns:
        print(f"  {col}")

    candidates = likely_id_columns(columns)
    print("Likely identifier/key columns:")
    if not candidates:
        print("  <none recognized>")
    else:
        df = read_table(path, candidates)
        for col in candidates:
            nonmissing = int(df[col].notna().sum())
            unique = int(df[col].nunique(dropna=True))
            print(
                f"  {col}: nonmissing={nonmissing:,}; unique={unique:,}; "
                f"duplicate_rows={nonmissing - unique:,}"
            )
    print()


def jhh_inventory(root: Path) -> None:
    print("=" * 80)
    print("CENTER 4 / JHH STRUCTURED FILE INVENTORY")
    print("=" * 80)
    if not root.exists():
        print(f"DIRECTORY NOT FOUND: {root}")
        print()
        return

    structured = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".csv", ".tsv", ".parquet"}
    ]
    if not structured:
        print("No CSV/TSV/Parquet files found.")
        print()
        return

    for path in sorted(structured):
        try:
            cols, rows = schema_only(path)
        except Exception as exc:
            print(f"{path.relative_to(root)}: unreadable ({type(exc).__name__})")
            continue

        row_text = f"{rows:,}" if rows is not None else "unknown"
        print(f"{path.relative_to(root)}")
        print(f"  rows={row_text}")
        print(f"  columns={cols}")
        id_cols = likely_id_columns(cols)
        demo_cols = [
            c for c in cols
            if any(
                token in norm_name(c)
                for token in ("birth", "age", "sex", "gender", "race", "ethnic", "hispan")
            )
        ]
        if id_cols:
            print(f"  likely ID/key columns={id_cols}")
        if demo_cols:
            print(f"  demographic-like columns={demo_cols}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--center1-features",
        default="data/processed/center1_features_from_raw.csv",
    )
    parser.add_argument(
        "--center1-demographics",
        default="../outcomes/PS_conditions_detailed.csv",
    )
    parser.add_argument(
        "--geisinger-demographics",
        default="../Geisinger/parquet/results_list_phase_1__DEMOGRAPHICS.parquet",
    )
    parser.add_argument(
        "--jhh-root",
        default="../phenotype/jhh",
    )
    args = parser.parse_args()

    center1_summary(
        Path(args.center1_features).expanduser().resolve(),
        Path(args.center1_demographics).expanduser().resolve(),
    )
    geisinger_summary(
        Path(args.geisinger_demographics).expanduser().resolve()
    )
    jhh_inventory(Path(args.jhh_root).expanduser().resolve())

    print("NEXT STEP")
    print(
        "Paste the complete output. It contains aggregate/schema information only. "
        "Do not paste patient-level rows or identifier values."
    )


if __name__ == "__main__":
    main()
