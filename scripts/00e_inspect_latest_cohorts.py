#!/usr/bin/env python
"""Inspect latest cohort Parquet files without printing patient-level values.

This is a schema/provenance audit only. It reports aggregate metadata, column
names/types, missingness, likely identifier/date/phenotype columns, and date
ranges. It deliberately does not print example rows or identifier values.

After reviewing this output, build a second, dataset-specific comparison against
the historical manuscript checkpoints.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


KEY_PATTERNS = {
    "patient_id": (
        r"(^|_)(patid|pat_id|patient_id|patientid|mrn)($|_)",
    ),
    "encounter_id": (
        r"(^|_)(encounterid|encounter_id|enc_id|visit_id|visitid|fin)($|_)",
    ),
    "date": (
        r"(date|time|admit|admission|discharge|stroke|onset)",
    ),
    "site": (
        r"(site|center|centre|facility|hospital|location)",
    ),
    "diagnosis": (
        r"(dx|diagnos|icd|stroke_type|stroke.*type|pdx)",
    ),
    "imaging": (
        r"(^|_)(ct|mri)($|_)|imaging",
    ),
    "lipid": (
        r"(lipid|chol|loinc)",
    ),
    "rehab": (
        r"(rehab|physical|occupational|speech|therapy|\bpt\b|\bot\b)",
    ),
    "demographic": (
        r"(age|birth|dob|sex|gender|race|ethnic)",
    ),
    "registry": (
        r"(registry|register|gwtg|gold|truth|label)",
    ),
}


def _match_columns(columns: list[str], patterns: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for col in columns:
        text = str(col).casefold()
        if any(re.search(p, text, flags=re.I) for p in patterns):
            hits.append(str(col))
    return hits


def _safe_nunique(series: pd.Series) -> int | None:
    try:
        return int(series.nunique(dropna=True))
    except Exception:
        return None


def _date_summary(path: Path, column: str) -> dict[str, object]:
    try:
        s = pd.read_parquet(path, columns=[column])[column]
    except Exception as exc:
        return {"column": column, "error": f"read failed: {exc}"}

    parsed = pd.to_datetime(s, errors="coerce")
    valid = parsed.notna()
    if not valid.any():
        return {
            "column": column,
            "non_null": int(s.notna().sum()),
            "parsed": 0,
            "min": None,
            "max": None,
        }
    return {
        "column": column,
        "non_null": int(s.notna().sum()),
        "parsed": int(valid.sum()),
        "min": str(parsed.loc[valid].min()),
        "max": str(parsed.loc[valid].max()),
    }


def _id_summary(path: Path, column: str) -> dict[str, object]:
    try:
        s = pd.read_parquet(path, columns=[column])[column]
    except Exception as exc:
        return {"column": column, "error": f"read failed: {exc}"}
    return {
        "column": column,
        "non_null": int(s.notna().sum()),
        "unique": _safe_nunique(s),
        "duplicated_non_null": int(s.notna().sum() - s.nunique(dropna=True)),
    }


def _booleanish_summary(path: Path, column: str) -> dict[str, object] | None:
    """Summarize only columns that look binary/boolean; never print raw values."""
    try:
        s = pd.read_parquet(path, columns=[column])[column]
    except Exception:
        return None

    non_null = s.dropna()
    if non_null.empty:
        return {
            "column": column,
            "non_null": 0,
            "unique": 0,
            "true_like": 0,
        }

    # Only summarize if cardinality is very small. Do not emit category labels.
    nunique = int(non_null.nunique(dropna=True))
    if nunique > 4:
        return None

    if pd.api.types.is_bool_dtype(non_null):
        true_like = int(non_null.astype(bool).sum())
    else:
        normalized = non_null.astype(str).str.strip().str.casefold()
        true_like = int(
            normalized.isin({"1", "true", "t", "yes", "y", "positive", "present"}).sum()
        )
    return {
        "column": column,
        "non_null": int(non_null.shape[0]),
        "unique": nunique,
        "true_like": true_like,
    }


def inspect_one(path: Path) -> None:
    print("=" * 100)
    print(f"FILE: {path}")
    print("=" * 100)

    if not path.exists():
        print("MISSING")
        print()
        return

    pf = pq.ParquetFile(path)
    schema = pf.schema_arrow
    columns = [field.name for field in schema]

    print(f"size_bytes: {path.stat().st_size:,}")
    print(f"rows: {pf.metadata.num_rows:,}")
    print(f"columns: {len(columns):,}")
    print(f"row_groups: {pf.metadata.num_row_groups:,}")
    print(f"created_by: {pf.metadata.created_by}")
    print()

    print("SCHEMA")
    for i, field in enumerate(schema, start=1):
        print(f"{i:3d}. {field.name} :: {field.type}")
    print()

    print("LIKELY COLUMN GROUPS")
    grouped: dict[str, list[str]] = {}
    for label, patterns in KEY_PATTERNS.items():
        hits = _match_columns(columns, patterns)
        grouped[label] = hits
        print(f"{label:14s}: {hits if hits else '[]'}")
    print()

    id_candidates = []
    for label in ("patient_id", "encounter_id"):
        for col in grouped[label]:
            if col not in id_candidates:
                id_candidates.append(col)

    if id_candidates:
        print("IDENTIFIER AGGREGATES (NO VALUES PRINTED)")
        for col in id_candidates[:12]:
            print(_id_summary(path, col))
        print()

    date_candidates = []
    for col in grouped["date"]:
        if col not in date_candidates:
            date_candidates.append(col)

    if date_candidates:
        print("DATE RANGES")
        for col in date_candidates[:20]:
            print(_date_summary(path, col))
        print()

    feature_candidates: list[str] = []
    for label in ("imaging", "lipid", "rehab", "registry"):
        for col in grouped[label]:
            if col not in feature_candidates:
                feature_candidates.append(col)

    bool_summaries = []
    for col in feature_candidates[:40]:
        summary = _booleanish_summary(path, col)
        if summary is not None:
            bool_summaries.append(summary)

    if bool_summaries:
        print("LOW-CARDINALITY FEATURE AGGREGATES (NO CATEGORY VALUES PRINTED)")
        for item in bool_summaries:
            print(item)
        print()

    # Missingness is collected from row-group metadata when available. It avoids
    # loading the full wide cohort solely for this diagnostic.
    missing_rows: list[tuple[str, int | None, float | None]] = []
    total_rows = pf.metadata.num_rows
    for i, col in enumerate(columns):
        null_count = 0
        complete = True
        for rg_idx in range(pf.metadata.num_row_groups):
            rg = pf.metadata.row_group(rg_idx)
            chunk = rg.column(i)
            stats = chunk.statistics
            if stats is None or not stats.has_null_count:
                complete = False
                break
            null_count += int(stats.null_count)
        if complete:
            pct = (100.0 * null_count / total_rows) if total_rows else 0.0
            missing_rows.append((col, null_count, pct))
        else:
            missing_rows.append((col, None, None))

    known = [row for row in missing_rows if row[1] is not None]
    unknown = [row for row in missing_rows if row[1] is None]
    if known:
        known_sorted = sorted(known, key=lambda x: x[2] or 0.0, reverse=True)
        print("MISSINGNESS FROM PARQUET METADATA: TOP 25")
        for col, nnull, pct in known_sorted[:25]:
            print(f"{col}: null={nnull:,} ({pct:.2f}%)")
        print()
    if unknown:
        print(
            f"missingness_metadata_unavailable_for: {len(unknown)} columns "
            "(not an error; statistics were not stored)"
        )
        print()

    print("NOTES")
    print("- No row-level values or identifiers were printed.")
    print("- This output is only for deciding how to map the new cohort to the existing D0-D9 analysis.")
    print("- Do not infer equivalence with the manuscript cohort until the cohort construction and date/site fields are mapped.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "paths",
        nargs="*",
        default=[
            "data/raw/psu_stroke_cohort_unimputed.parquet",
            "data/raw/geisinger_stroke_cohort_unimputed.parquet",
        ],
    )
    args = parser.parse_args()

    print("Latest cohort schema audit")
    print("working_directory:", os.getcwd())
    print()
    for raw in args.paths:
        inspect_one(Path(raw))


if __name__ == "__main__":
    main()
