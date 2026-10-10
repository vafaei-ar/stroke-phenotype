"""Import legacy Geisinger pivot tables into canonical monthly count format."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Historical Geisinger condition-table section labels mapped to manuscript
# phenotype definitions.
GEISINGER_SECTION_TO_DEFINITION: Mapping[str, str] = {
    "diagnosis": "D0",
    "any imaging and chol./lip.": "D1",
    "any imaging and (chol./lip. or phy./rehab.)": "D2",
    "mri and chol./lip.": "D3",
    "mri and (chol./lip. or phy./rehab.)": "D4",
    "any imaging": "D5",
    "mri and chol./lip. and phy./rehab.": "D6",
    "mri": "D7",
    "ct and chol./lip.": "D8",
}


def _numeric(value: object) -> float:
    """Convert legacy comma-formatted cell values to numeric."""
    if pd.isna(value):
        return float("nan")
    text = str(value).strip().replace(",", "")
    if not text:
        return float("nan")
    return float(text)


def _normalize_label(value: object) -> str:
    return " ".join(str(value).strip().casefold().split())


def parse_geisinger_conditions(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the repeated-section Geisinger condition export to monthly D0-D8."""
    if "Row Labels" not in df.columns:
        raise KeyError("Conditions table must contain 'Row Labels'")

    year_cols = [c for c in df.columns if str(c).isdigit() and len(str(c)) == 4]
    if not year_cols:
        raise ValueError("No four-digit year columns found in conditions table")

    labels = df["Row Labels"].map(_normalize_label)
    rows: list[dict[str, object]] = []

    for section_label, definition in GEISINGER_SECTION_TO_DEFINITION.items():
        matches = df.index[labels == section_label].tolist()
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one section {section_label!r}; found {len(matches)}"
            )

        start = matches[0] + 1
        block = df.iloc[start : start + 12].copy()
        block_months = block["Row Labels"].astype(str).str.strip().tolist()
        if block_months != MONTHS:
            raise ValueError(
                f"Unexpected month rows after {section_label!r}: {block_months}"
            )

        for _, row in block.iterrows():
            month_name = str(row["Row Labels"]).strip()
            month_num = MONTHS.index(month_name) + 1
            for year in year_cols:
                rows.append({
                    "month": f"{int(year):04d}-{month_num:02d}",
                    "definition": definition,
                    "count": _numeric(row[year]),
                })

    long = pd.DataFrame(rows)
    wide = (
        long.pivot(index="month", columns="definition", values="count")
        .reset_index()
        .rename_axis(columns=None)
        .sort_values("month")
    )

    ordered = [f"D{i}" for i in range(9)]
    missing = [d for d in ordered if d not in wide.columns]
    if missing:
        raise ValueError(f"Missing parsed definitions: {missing}")
    return wide[["month", *ordered]]


def parse_geisinger_registry(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the Year x month Geisinger registry export to month/SR."""
    if "Year" not in df.columns:
        raise KeyError("Registry table must contain 'Year'")

    missing_months = [m for m in MONTHS if m not in df.columns]
    if missing_months:
        raise KeyError(f"Registry table is missing month columns: {missing_months}")

    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        year = int(row["Year"])
        for month_num, month_name in enumerate(MONTHS, start=1):
            rows.append({
                "month": f"{year:04d}-{month_num:02d}",
                "SR": _numeric(row[month_name]),
            })

    return pd.DataFrame(rows).sort_values("month").reset_index(drop=True)


def build_geisinger_monthly_table(
    conditions: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Return registry-aligned monthly D0-D8 counts for an analytic window."""
    cond = parse_geisinger_conditions(conditions)
    reg = parse_geisinger_registry(registry)

    cond = cond[(cond["month"] >= start) & (cond["month"] <= end)].copy()
    reg = reg[(reg["month"] >= start) & (reg["month"] <= end)].copy()

    out = reg.merge(cond, on="month", how="left", validate="one_to_one")

    if out.empty:
        raise ValueError(f"No rows in requested analytic window {start} to {end}")

    if out["SR"].isna().any():
        months = out.loc[out["SR"].isna(), "month"].tolist()
        raise ValueError(f"Registry counts missing in analytic window: {months[:10]}")

    definitions = [f"D{i}" for i in range(9)]
    missing = out[definitions].isna().any(axis=1)
    if missing.any():
        months = out.loc[missing, "month"].tolist()
        raise ValueError(
            "Phenotype counts missing in analytic window: "
            f"{months[:10]}"
        )

    for col in ["SR", *definitions]:
        out[col] = pd.to_numeric(out[col], errors="raise").astype(int)

    return out[["month", "SR", *definitions]]
