#!/usr/bin/env python
"""Compare manuscript benchmarks with latest cohorts and test CTA/MRA extensions.

This is a reviewer-motivated sensitivity/provenance analysis. It does NOT replace
the manuscript-generating analyses.

Important assumptions for the latest Parquet files:
- each row is already in the ICD stroke candidate cohort, so D0 = all rows;
- rows are one-row-per-patient anchor records, not encounter-level histories;
- latest-file monthly metrics are therefore sensitivity analyses and should not
  be interpreted as exact reproductions of the historical cohorts.

The script reports:
1. paper/reproduced historical metrics versus metrics from the latest anchor-row
   files for PSU, GMC, and GCMC;
2. PSU historical PPV versus latest-file registry-linkage proportions (the latter
   are deliberately NOT labeled PPV);
3. prevalence/overlap of neuroimaging and vascular-imaging features;
4. a prespecified set of CTA/MRA exploratory definitions.

No patient identifiers or row-level records are printed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from stroke_phenotype.geisinger import parse_geisinger_registry
from stroke_phenotype.metrics import compute_count_metrics
from stroke_phenotype.registry import align_counts_to_registry_months, standardize_month_column


PSU_START = "2016-12"
PSU_END = "2023-12"
PSU_LINK_START = pd.Timestamp("2018-02-01")
PSU_LINK_END = pd.Timestamp("2019-01-31")

SITE_WINDOWS = {
    "PSU": ("2016-12", "2023-12"),
    "GMC": ("2017-01", "2022-07"),
    "GCMC": ("2016-03", "2022-07"),
}

ORIGINAL = [f"D{i}" for i in range(10)]
VASCULAR = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"]
ALL_DEFINITIONS = ORIGINAL + VASCULAR

DEFINITION_LABELS = {
    "D0": "ICD cohort only",
    "D1": "(CT OR MRI) AND lipid",
    "D2": "(CT OR MRI) AND (lipid OR rehab)",
    "D3": "MRI AND lipid",
    "D4": "MRI AND (lipid OR rehab)",
    "D5": "CT OR MRI",
    "D6": "MRI AND lipid AND rehab",
    "D7": "MRI",
    "D8": "CT AND lipid",
    "D9": "(CT OR MRI) AND lipid AND rehab",
    "V1": "CTA OR MRA",
    "V2": "(CTA OR MRA) AND lipid",
    "V3": "(CT OR MRI) AND (CTA OR MRA) AND lipid",
    "V4": "(CT OR MRI OR CTA OR MRA) AND lipid",
    "V5": "(CTA OR MRA) AND lipid AND rehab",
    "V6": "(CT OR MRI OR CTA OR MRA) AND lipid AND rehab",
    "V7": "CTA AND lipid",
    "V8": "MRA AND lipid",
}


def flag(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        raise KeyError(f"Missing required feature column: {column}")
    return pd.to_numeric(df[column], errors="coerce").eq(1)


def definition_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    # The supplied Parquets are already D0 candidate cohorts.
    d0 = pd.Series(True, index=df.index)
    ct = flag(df, "has_ct")
    mri = flag(df, "has_mri")
    cta = flag(df, "has_cta")
    mra = flag(df, "has_mra")
    lipid = flag(df, "has_lipid_panel")
    rehab = flag(df, "has_rehabilitation")

    neuro = ct | mri
    vascular = cta | mra
    any_imaging = neuro | vascular

    return {
        "D0": d0,
        "D1": neuro & lipid,
        "D2": neuro & (lipid | rehab),
        "D3": mri & lipid,
        "D4": mri & (lipid | rehab),
        "D5": neuro,
        "D6": mri & lipid & rehab,
        "D7": mri,
        "D8": ct & lipid,
        "D9": neuro & lipid & rehab,
        # Reviewer-motivated vascular-imaging sensitivity definitions.
        "V1": vascular,
        "V2": vascular & lipid,
        "V3": neuro & vascular & lipid,
        "V4": any_imaging & lipid,
        "V5": vascular & lipid & rehab,
        "V6": any_imaging & lipid & rehab,
        # Decomposition to determine whether CTA or MRA drives V2.
        "V7": cta & lipid,
        "V8": mra & lipid,
    }


def window_mask(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    dates = pd.to_datetime(df["DX_DATE_stroke"], errors="coerce")
    start_ts = pd.Period(start, freq="M").start_time
    end_ts = pd.Period(end, freq="M").end_time
    return dates.between(start_ts, end_ts, inclusive="both")


def monthly_counts(
    df: pd.DataFrame,
    *,
    start: str,
    end: str,
    site_mask: pd.Series | None = None,
) -> pd.DataFrame:
    if site_mask is None:
        site_mask = pd.Series(True, index=df.index)

    dates = pd.to_datetime(df["DX_DATE_stroke"], errors="coerce")
    selected = site_mask & window_mask(df, start, end) & dates.notna()
    masks = definition_masks(df)

    months = pd.period_range(start=start, end=end, freq="M").astype(str)
    out = pd.DataFrame({"month": months})

    month_values = dates.dt.to_period("M").astype("string")
    for definition in ALL_DEFINITIONS:
        counts = (
            month_values[selected & masks[definition]]
            .value_counts()
            .reindex(months, fill_value=0)
        )
        out[definition] = counts.to_numpy(dtype=int)
    return out


def load_psu_registry(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = standardize_month_column(df)
    if "SR" not in df.columns:
        raise KeyError(f"PSU registry source {path} does not contain SR")
    return df[["month", "SR"]].copy()


def load_geisinger_registry(path: Path, *, start: str, end: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    reg = parse_geisinger_registry(raw)
    return reg[(reg["month"] >= start) & (reg["month"] <= end)].copy()


def latest_metrics(counts: pd.DataFrame, registry: pd.DataFrame) -> pd.DataFrame:
    # Preserve both manuscript D* definitions and exploratory V* definitions.
    # The shared registry helper intentionally keeps only D-prefixed columns,
    # which is appropriate for manuscript analyses but would drop V1-V8 here.
    counts = standardize_month_column(counts)
    registry = standardize_month_column(registry)

    if "SR" not in registry.columns:
        raise KeyError("Registry table does not contain SR")

    registry_reference = registry[["month", "SR"]].copy()
    count_months = set(counts["month"])
    registry_months = set(registry_reference["month"])
    missing = sorted(registry_months - count_months)
    if missing:
        raise ValueError(
            "Latest phenotype counts are missing registry months: "
            f"{missing[:10]}"
        )

    aligned = registry_reference.merge(
        counts,
        on="month",
        how="left",
        validate="one_to_one",
    )
    return compute_count_metrics(
        aligned,
        registry_col="SR",
        definitions=ALL_DEFINITIONS,
    )


def historical_count_metrics(repo_root: Path) -> pd.DataFrame:
    rows = []

    c1 = repo_root / "reference" / "center1_reviewer_count_expected.csv"
    if c1.exists():
        x = pd.read_csv(c1)
        x.insert(0, "site", "PSU")
        rows.append(x)

    c23 = repo_root / "reference" / "center23_reviewer_count_expected.csv"
    if c23.exists():
        x = pd.read_csv(c23)
        x["site"] = x["center"].map({"Center 2": "GMC", "Center 3": "GCMC"})
        rows.append(x.drop(columns=["center"]))

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def compare_to_historical(
    site: str,
    latest: pd.DataFrame,
    historical: pd.DataFrame,
) -> pd.DataFrame:
    keep = [
        "definition",
        "n_months",
        "definition_total",
        "MAE",
        "nMAE_percent",
        "Pearson_r",
        "mean_signed_error",
        "total_count_ratio",
    ]
    new = latest[keep].copy().rename(columns={
        "n_months": "latest_n_months",
        "definition_total": "latest_total",
        "MAE": "latest_MAE",
        "nMAE_percent": "latest_nMAE_percent",
        "Pearson_r": "latest_r",
        "mean_signed_error": "latest_mean_signed_error",
        "total_count_ratio": "latest_total_count_ratio",
    })

    h = historical[historical["site"].eq(site)].copy()
    hcols = [
        c for c in [
            "definition", "n_months", "definition_total",
            "MAE", "nMAE_percent", "Pearson_r",
        ] if c in h.columns
    ]
    if h.empty:
        out = new
        out.insert(1, "paper_total", np.nan)
        return out

    h = h[hcols].rename(columns={
        "n_months": "paper_n_months",
        "definition_total": "paper_total",
        "MAE": "paper_MAE",
        "nMAE_percent": "paper_nMAE_percent",
        "Pearson_r": "paper_r",
    })

    out = new.merge(h, on="definition", how="left")
    if "paper_total" in out.columns:
        out["delta_total"] = out["latest_total"] - out["paper_total"]
        out["latest_to_paper_ratio"] = out["latest_total"] / out["paper_total"]
    if "paper_MAE" in out.columns:
        out["delta_MAE"] = out["latest_MAE"] - out["paper_MAE"]
    if "paper_nMAE_percent" in out.columns:
        out["delta_nMAE_pp"] = (
            out["latest_nMAE_percent"] - out["paper_nMAE_percent"]
        )
    if "paper_r" in out.columns:
        out["delta_r"] = out["latest_r"] - out["paper_r"]

    first = [
        "definition",
        "paper_total", "latest_total", "delta_total", "latest_to_paper_ratio",
        "paper_MAE", "latest_MAE", "delta_MAE",
        "paper_nMAE_percent", "latest_nMAE_percent", "delta_nMAE_pp",
        "paper_r", "latest_r", "delta_r",
        "latest_mean_signed_error", "latest_total_count_ratio",
    ]
    return out[[c for c in first if c in out.columns]]


def feature_overlap(
    df: pd.DataFrame,
    *,
    site: str,
    start: str,
    end: str,
    site_mask: pd.Series | None = None,
) -> pd.DataFrame:
    if site_mask is None:
        site_mask = pd.Series(True, index=df.index)
    w = site_mask & window_mask(df, start, end)

    ct = flag(df, "has_ct")
    mri = flag(df, "has_mri")
    cta = flag(df, "has_cta")
    mra = flag(df, "has_mra")
    lipid = flag(df, "has_lipid_panel")
    rehab = flag(df, "has_rehabilitation")

    neuro = ct | mri
    vascular = cta | mra

    signals = {
        "D0 rows": pd.Series(True, index=df.index),
        "CT": ct,
        "MRI": mri,
        "CTA": cta,
        "MRA": mra,
        "CT or MRI": neuro,
        "CTA or MRA": vascular,
        "neuro AND vascular": neuro & vascular,
        "vascular without neuro": vascular & ~neuro,
        "neuro without vascular": neuro & ~vascular,
        "lipid": lipid,
        "rehab": rehab,
    }

    denom = int(w.sum())
    rows = []
    for name, mask in signals.items():
        n = int((w & mask).sum())
        rows.append({
            "site": site,
            "feature": name,
            "n": n,
            "percent_of_D0": 100 * n / denom if denom else np.nan,
        })
    return pd.DataFrame(rows)


def psu_linkage_comparison(
    psu: pd.DataFrame,
    repo_root: Path,
) -> pd.DataFrame:
    dates = pd.to_datetime(psu["DX_DATE_stroke"], errors="coerce")
    window = dates.between(PSU_LINK_START, PSU_LINK_END, inclusive="both")
    linked = flag(psu, "in_stroke_registry")
    masks = definition_masks(psu)

    rows = []
    for definition in ALL_DEFINITIONS:
        positive = window & masks[definition]
        n = int(positive.sum())
        matched = int((positive & linked).sum())
        rows.append({
            "definition": definition,
            "latest_positive": n,
            "latest_registry_linked": matched,
            "latest_linkage_proportion": matched / n if n else np.nan,
        })
    latest = pd.DataFrame(rows)

    ref = repo_root / "reference" / "center1_linked_reviewer_expected.csv"
    if not ref.exists():
        return latest

    hist = pd.read_csv(ref)
    cols = [
        c for c in [
            "definition", "definition_positive", "matched_registry", "PPV"
        ] if c in hist.columns
    ]
    hist = hist[cols].rename(columns={
        "definition_positive": "paper_positive",
        "matched_registry": "paper_matched_registry",
        "PPV": "paper_PPV",
    })
    out = latest.merge(hist, on="definition", how="left")
    if "paper_PPV" in out.columns:
        out["linkage_minus_paper_pp"] = 100 * (
            out["latest_linkage_proportion"] - out["paper_PPV"]
        )
    return out


def print_table(title: str, df: pd.DataFrame) -> None:
    print()
    print("=" * 110)
    print(title)
    print("=" * 110)
    print(df.to_string(index=False))


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
        "--psu-registry",
        default="../outcomes/PS_conditions.csv",
        help="Monthly PSU registry table containing SR.",
    )
    parser.add_argument(
        "--gmc-registry",
        default="../phenotype/geisinger/GMC_registery.csv",
    )
    parser.add_argument(
        "--gcmc-registry",
        default="../phenotype/geisinger/GCMC_registery.csv",
    )
    parser.add_argument(
        "--outdir",
        default="outputs/latest_sensitivity",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    required = [
        "DX_DATE_stroke",
        "has_ct", "has_mri", "has_cta", "has_mra",
        "has_lipid_panel", "has_rehabilitation",
    ]

    psu = pd.read_parquet(args.psu)
    geis = pd.read_parquet(args.geisinger)

    for label, df in [("PSU", psu), ("Geisinger", geis)]:
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise KeyError(f"{label} is missing required columns: {missing}")

    if "ENC_DEP_NM" not in geis.columns:
        raise KeyError("Geisinger file is missing ENC_DEP_NM")
    if "in_stroke_registry" not in psu.columns:
        raise KeyError("PSU file is missing in_stroke_registry")

    gmc_mask = geis["ENC_DEP_NM"].astype("string").eq("GMC")
    gcmc_mask = geis["ENC_DEP_NM"].astype("string").eq("GCMC")

    # Feature overlap first: essential for interpreting whether CTA/MRA add new information.
    overlaps = pd.concat([
        feature_overlap(psu, site="PSU", start=PSU_START, end=PSU_END),
        feature_overlap(
            geis, site="GMC", start="2017-01", end="2022-07",
            site_mask=gmc_mask,
        ),
        feature_overlap(
            geis, site="GCMC", start="2016-03", end="2022-07",
            site_mask=gcmc_mask,
        ),
    ], ignore_index=True)
    overlaps.to_csv(outdir / "feature_overlap.csv", index=False)
    print_table("FEATURE PREVALENCE / OVERLAP IN LATEST ANCHOR-ROW COHORTS", overlaps)

    # Latest monthly counts.
    psu_counts = monthly_counts(psu, start=PSU_START, end=PSU_END)
    gmc_counts = monthly_counts(
        geis, start="2017-01", end="2022-07", site_mask=gmc_mask
    )
    gcmc_counts = monthly_counts(
        geis, start="2016-03", end="2022-07", site_mask=gcmc_mask
    )

    psu_counts.to_csv(outdir / "psu_latest_monthly_counts.csv", index=False)
    gmc_counts.to_csv(outdir / "gmc_latest_monthly_counts.csv", index=False)
    gcmc_counts.to_csv(outdir / "gcmc_latest_monthly_counts.csv", index=False)

    # Same registry series used by the historical count analyses.
    psu_reg = load_psu_registry(Path(args.psu_registry))
    gmc_reg = load_geisinger_registry(
        Path(args.gmc_registry), start="2017-01", end="2022-07"
    )
    gcmc_reg = load_geisinger_registry(
        Path(args.gcmc_registry), start="2016-03", end="2022-07"
    )

    metrics = {
        "PSU": latest_metrics(psu_counts, psu_reg),
        "GMC": latest_metrics(gmc_counts, gmc_reg),
        "GCMC": latest_metrics(gcmc_counts, gcmc_reg),
    }

    historical = historical_count_metrics(repo_root)

    comparisons = []
    for site in ["PSU", "GMC", "GCMC"]:
        latest = metrics[site].copy()
        latest.insert(0, "site", site)
        latest.to_csv(outdir / f"{site.lower()}_latest_metrics.csv", index=False)

        comp = compare_to_historical(site, metrics[site], historical)
        comp.insert(0, "site", site)
        comparisons.append(comp)
        print_table(
            f"{site}: PAPER/REPRODUCED BENCHMARKS VS LATEST ANCHOR-ROW METRICS",
            comp,
        )

    comparison_all = pd.concat(comparisons, ignore_index=True)
    comparison_all.to_csv(
        outdir / "paper_vs_latest_count_metrics.csv", index=False
    )

    # PSU linkage comparison. Historical PPV is shown as PPV; latest is not.
    linkage = psu_linkage_comparison(psu, repo_root)
    linkage.to_csv(outdir / "psu_paper_ppv_vs_latest_linkage.csv", index=False)
    print_table(
        "PSU: PAPER PPV VS LATEST REGISTRY-LINKAGE PROPORTION (NOT THE SAME ENDPOINT)",
        linkage,
    )

    # Focused reviewer-facing table: benchmarks + vascular candidates.
    focus_defs = ["D0", "D1", "D3", "D6", "D9", *VASCULAR]
    focus_rows = []
    for site in ["PSU", "GMC", "GCMC"]:
        x = metrics[site]
        x = x[x["definition"].isin(focus_defs)].copy()
        x.insert(0, "site", site)
        focus_rows.append(x)
    focus = pd.concat(focus_rows, ignore_index=True)
    focus.insert(
        2,
        "definition_label",
        focus["definition"].map(DEFINITION_LABELS),
    )
    focus.to_csv(outdir / "vascular_candidate_metrics.csv", index=False)

    focus_print = focus[
        [
            "site", "definition", "definition_label", "definition_total",
            "MAE", "nMAE_percent", "Pearson_r",
            "mean_signed_error", "total_count_ratio",
        ]
    ].copy()
    print_table(
        "PRESPECIFIED CTA/MRA EXPLORATORY DEFINITIONS VS D0/D1/D3/D6/D9",
        focus_print,
    )

    catalog = pd.DataFrame(
        [{"definition": k, "rule": v} for k, v in DEFINITION_LABELS.items()]
    )
    catalog.to_csv(outdir / "definition_catalog.csv", index=False)

    print()
    print(f"Wrote outputs to: {outdir}")
    print("Interpretation rule:")
    print("- Manuscript/reproduced benchmarks remain primary.")
    print("- Latest-file metrics are anchor-row sensitivity/provenance analyses.")
    print("- Latest PSU linkage_proportion is not called PPV unless linkage semantics are independently confirmed.")
    print("- V1-V8 are exploratory reviewer-motivated definitions and should not replace D0-D9 without replication.")


if __name__ == "__main__":
    main()
