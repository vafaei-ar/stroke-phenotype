#!/usr/bin/env python
"""Audit local historical demographic sources for rebuilding manuscript Table 2.

This script is deliberately a *source-discovery and aggregate-profile* tool.
It does not use the newer one-row-per-patient anchor Parquets under this
repository's data/ directory unless --include-repo-data is supplied.

Default mode searches a local historical project root for CSV/TSV/Parquet files
whose schemas contain demographic fields. It prints only:
- relative file paths;
- row counts when available from file metadata;
- matching column names;
- simple candidate scores.

No patient identifiers or row-level values are printed.

Use --profile PATH (repeatable) after candidate files are identified. Profile
mode still prints aggregate information only: total rows, unique-patient counts,
date ranges, missingness, and low-cardinality demographic category counts.
Identifier values are never printed.

Typical first run from the stroke-phenotype repository:

    python scripts/00h_audit_table2_demographics.py --root ..

Then paste the output into the project conversation. If a few strong candidate
files are obvious, profile them, for example:

    python scripts/00h_audit_table2_demographics.py \
      --root .. \
      --profile stroke_data/demographic.parquet \
      --profile path/to/another_candidate.csv

The goal is to identify the historical source(s) that can support a patient-level
characteristics table aligned with the manuscript analysis, without silently
substituting the newer sensitivity-analysis anchor cohorts.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


SUPPORTED_SUFFIXES = {".csv", ".tsv", ".parquet"}

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "site-packages",
    "dist",
    "build",
}

# These values are printed only as manuscript/provenance checkpoints. They are
# NOT treated as target denominators for the rebuilt patient-characteristics
# table.
CURRENT_TABLE2_OLD_N = {
    "Overall": 71988,
    "Center 1": 24603,
    "Center 2": 7263,
    "Center 3": 3088,
    "Center 4": 37047,
}

MANUSCRIPT_D0_TOTALS = {
    "Center 1": 6582,
    "Center 2": 4166,
    "Center 3": 2230,
    "Center 4": 1491,
}

PRIOR_AGE_SUMMARY_N = {
    "Center 1": 5124,
    "Center 2": 3782,
    "Center 3": 1845,
}


@dataclass
class Candidate:
    path: Path
    fmt: str
    rows: int | None
    columns: list[str]
    demo_columns: list[str]
    id_columns: list[str]
    date_columns: list[str]
    site_columns: list[str]
    score: int


def normalize_column(name: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def classify_columns(columns: Iterable[object]) -> tuple[list[str], list[str], list[str], list[str]]:
    demo: list[str] = []
    ids: list[str] = []
    dates: list[str] = []
    sites: list[str] = []

    for raw in columns:
        col = str(raw)
        n = normalize_column(col)

        if _contains_any(
            n,
            (
                "age",
                "birthdate",
                "birthdt",
                "birthyear",
                "dateofbirth",
                "dob",
                "sex",
                "gender",
                "race",
                "ethnic",
                "hispan",
            ),
        ):
            demo.append(col)

        if (
            n in {"patid", "patientid", "patient", "personid", "subjectid", "mrn"}
            or n.endswith("patientid")
            or n.endswith("patid")
        ):
            ids.append(col)

        if (
            _contains_any(n, ("admitdate", "admissiondate", "encounterdate", "dxdate", "strokedate", "indexdate"))
            or (n.endswith("date") and "birth" not in n)
        ):
            dates.append(col)

        if _contains_any(n, ("facility", "hospital", "siteid", "sitename", "location")):
            sites.append(col)

    return demo, ids, dates, sites


def demographic_groups(columns: Iterable[str]) -> set[str]:
    groups: set[str] = set()
    for col in columns:
        n = normalize_column(col)
        if _contains_any(n, ("age", "birthdate", "birthdt", "birthyear", "dateofbirth", "dob")):
            groups.add("age")
        if _contains_any(n, ("sex", "gender")):
            groups.add("sex")
        if "race" in n:
            groups.add("race")
        if _contains_any(n, ("ethnic", "hispan")):
            groups.add("ethnicity")
    return groups


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def should_skip(path: Path, *, repo_root: Path, include_repo_data: bool) -> bool:
    if any(part in SKIP_DIR_NAMES for part in path.parts):
        return True
    if not include_repo_data and is_under(path, repo_root / "data"):
        return True
    return False


def csv_columns(path: Path, sep: str) -> list[str]:
    try:
        return list(pd.read_csv(path, sep=sep, nrows=0).columns)
    except UnicodeDecodeError:
        return list(pd.read_csv(path, sep=sep, nrows=0, encoding="latin-1").columns)


def parquet_schema(path: Path) -> tuple[list[str], int | None]:
    try:
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(path)
        return list(pf.schema_arrow.names), int(pf.metadata.num_rows)
    except Exception:
        # Fallback still reads only schema/zero columns with pandas when the
        # installed parquet engine supports it.
        df = pd.read_parquet(path, columns=[])
        return list(df.columns), len(df)


def inspect_schema(path: Path) -> tuple[str, list[str], int | None]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv", csv_columns(path, ","), None
    if suffix == ".tsv":
        return "tsv", csv_columns(path, "\t"), None
    if suffix == ".parquet":
        cols, rows = parquet_schema(path)
        return "parquet", cols, rows
    raise ValueError(f"Unsupported file type: {suffix}")


def candidate_score(
    demo_columns: list[str],
    id_columns: list[str],
    date_columns: list[str],
    site_columns: list[str],
) -> int:
    groups = demographic_groups(demo_columns)
    score = 5 * len(groups)
    score += 3 if id_columns else 0
    score += 2 if date_columns else 0
    score += 1 if site_columns else 0
    return score


def discover_candidates(
    root: Path,
    *,
    repo_root: Path,
    include_repo_data: bool,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if should_skip(path, repo_root=repo_root, include_repo_data=include_repo_data):
            continue

        try:
            fmt, columns, rows = inspect_schema(path)
        except Exception:
            continue

        demo, ids, dates, sites = classify_columns(columns)
        if not demo:
            continue

        candidates.append(
            Candidate(
                path=path,
                fmt=fmt,
                rows=rows,
                columns=columns,
                demo_columns=demo,
                id_columns=ids,
                date_columns=dates,
                site_columns=sites,
                score=candidate_score(demo, ids, dates, sites),
            )
        )

    candidates.sort(
        key=lambda x: (
            -x.score,
            -(x.rows or -1),
            str(x.path).lower(),
        )
    )
    return candidates


def display_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return path.name


def print_reference_checkpoints() -> None:
    print("REFERENCE CHECKPOINTS (for diagnosis only; not assumed Table 2 targets)")
    print("Current manuscript Table 2 denominators:")
    for key, value in CURRENT_TABLE2_OLD_N.items():
        print(f"  {key}: {value:,}")

    center_sum = sum(
        value for key, value in CURRENT_TABLE2_OLD_N.items() if key.startswith("Center ")
    )
    print(f"  Sum of displayed center Ns: {center_sum:,}")
    print(
        "  Difference from displayed Overall N: "
        f"{center_sum - CURRENT_TABLE2_OLD_N['Overall']:+,}"
    )

    print("Manuscript/reproduced D0 totals over registry-overlap windows:")
    for key, value in MANUSCRIPT_D0_TOTALS.items():
        print(f"  {key}: {value:,}")

    print("Previously reported age-summary Ns:")
    for key, value in PRIOR_AGE_SUMMARY_N.items():
        print(f"  {key}: {value:,}")
    print()


def print_candidates(candidates: list[Candidate], root: Path, top: int) -> None:
    print(f"DEMOGRAPHIC SOURCE CANDIDATES (top {min(top, len(candidates))} of {len(candidates)})")
    if not candidates:
        print("  No CSV/TSV/Parquet files with demographic-like columns were found.")
        return

    for i, item in enumerate(candidates[:top], start=1):
        rows = f"{item.rows:,}" if item.rows is not None else "unknown from header-only scan"
        print(f"[{i}] {display_relative(item.path, root)}")
        print(f"    format={item.fmt}; rows={rows}; score={item.score}")
        print(f"    demographic columns: {item.demo_columns}")
        print(f"    patient-id candidates: {item.id_columns or ['<none>']}")
        print(f"    date candidates: {item.date_columns or ['<none>']}")
        print(f"    site/facility candidates: {item.site_columns or ['<none>']}")
        print()


def resolve_profile_path(value: str, root: Path) -> Path:
    direct = Path(value).expanduser()
    if direct.exists():
        return direct.resolve()

    under_root = (root / value).expanduser()
    if under_root.exists():
        return under_root.resolve()

    raise FileNotFoundError(
        f"Could not find profile path {value!r} either directly or under {root}"
    )


def read_selected(path: Path, columns: list[str]) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path, columns=columns)

    sep = "\t" if suffix == ".tsv" else ","
    try:
        return pd.read_csv(path, sep=sep, usecols=columns, low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(
            path,
            sep=sep,
            usecols=columns,
            low_memory=False,
            encoding="latin-1",
        )


def is_birth_column(column: str) -> bool:
    n = normalize_column(column)
    return _contains_any(n, ("birth", "dob", "dateofbirth"))


def profile_file(
    path: Path,
    *,
    root: Path,
    max_categories: int,
) -> None:
    fmt, columns, metadata_rows = inspect_schema(path)
    demo, ids, dates, sites = classify_columns(columns)

    selected = list(dict.fromkeys(demo + ids + dates + sites))
    if not selected:
        print(f"PROFILE {display_relative(path, root)}")
        print("  No demographic/id/date/site columns recognized.")
        print()
        return

    df = read_selected(path, selected)
    print(f"PROFILE {display_relative(path, root)}")
    print(f"  format: {fmt}")
    print(f"  rows read: {len(df):,}")
    if metadata_rows is not None and metadata_rows != len(df):
        print(f"  metadata rows: {metadata_rows:,}")

    if ids:
        print("  unique-patient counts (identifier values suppressed):")
        for col in ids:
            print(f"    {col}: {df[col].nunique(dropna=True):,}")

    profile_dates = [col for col in dates if not is_birth_column(col)]
    if profile_dates:
        print("  date ranges:")
        for col in profile_dates:
            values = pd.to_datetime(df[col], errors="coerce")
            nonmissing = int(values.notna().sum())
            if nonmissing:
                print(
                    f"    {col}: nonmissing={nonmissing:,}; "
                    f"min={values.min().date()}; max={values.max().date()}"
                )
            else:
                print(f"    {col}: no parseable dates")

    print("  demographic fields:")
    for col in demo:
        series = df[col]
        nonmissing = int(series.notna().sum())
        missing = len(series) - nonmissing
        nunique = int(series.nunique(dropna=True))
        print(
            f"    {col}: nonmissing={nonmissing:,}; missing={missing:,}; "
            f"unique={nunique:,}"
        )

        # Only low-cardinality demographic fields are safe/useful to print as
        # aggregate category counts. Free-text/high-cardinality fields are not
        # printed.
        n = normalize_column(col)
        is_categorical_demo = _contains_any(n, ("sex", "gender", "race", "ethnic", "hispan"))
        if is_categorical_demo and nunique <= max_categories:
            counts = (
                series.astype("string")
                .fillna("<missing>")
                .value_counts(dropna=False)
            )
            for label, count in counts.items():
                print(f"      {label}: {int(count):,}")

    if sites:
        print("  site/facility fields (values suppressed):")
        for col in sites:
            print(
                f"    {col}: nonmissing={int(df[col].notna().sum()):,}; "
                f"unique={int(df[col].nunique(dropna=True)):,}"
            )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Find historical local demographic sources for rebuilding manuscript Table 2 "
            "without printing patient-level values."
        )
    )
    parser.add_argument(
        "--root",
        default="..",
        help=(
            "Historical project root to scan. From the repository, '..' usually points "
            "to the parent workspace containing legacy analysis directories."
        ),
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Maximum number of ranked source candidates to print.",
    )
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "Profile a selected candidate file using aggregate counts only. May be repeated. "
            "PATH may be absolute, relative to the current directory, or relative to --root."
        ),
    )
    parser.add_argument(
        "--max-categories",
        type=int,
        default=30,
        help="Maximum unique categories to print for sex/race/ethnicity fields.",
    )
    parser.add_argument(
        "--include-repo-data",
        action="store_true",
        help=(
            "Also scan stroke-phenotype/data. Off by default so the newer anchor Parquets "
            "are not accidentally treated as historical Table 2 sources."
        ),
    )
    args = parser.parse_args()

    if args.top < 1:
        raise ValueError("--top must be >= 1")
    if args.max_categories < 1:
        raise ValueError("--max-categories must be >= 1")

    repo_root = Path(__file__).resolve().parents[1]
    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Search root does not exist: {root}")

    print_reference_checkpoints()

    candidates = discover_candidates(
        root,
        repo_root=repo_root,
        include_repo_data=args.include_repo_data,
    )
    print_candidates(candidates, root, args.top)

    if args.profile:
        print("SELECTED AGGREGATE PROFILES")
        for raw_path in args.profile:
            path = resolve_profile_path(raw_path, root)
            profile_file(
                path,
                root=root,
                max_categories=args.max_categories,
            )

    print("NEXT STEP")
    if args.profile:
        print(
            "  Paste the candidate list and selected aggregate profiles. "
            "Do not paste patient-level rows or identifier values."
        )
    else:
        print(
            "  Paste this candidate list. We will choose the historical source files, "
            "then rerun with --profile on only those files."
        )


if __name__ == "__main__":
    main()
