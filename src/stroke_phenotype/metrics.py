"""Count-based agreement metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def pearson_safe(x: pd.Series, y: pd.Series) -> float:
    """Pearson correlation, returning NaN when correlation is undefined."""
    x = pd.Series(x, dtype=float)
    y = pd.Series(y, dtype=float)
    mask = x.notna() & y.notna()
    x = x[mask]
    y = y[mask]
    if len(x) < 2 or x.nunique() < 2 or y.nunique() < 2:
        return float("nan")
    return float(stats.pearsonr(x, y).statistic)


def compute_count_metrics(
    df: pd.DataFrame,
    *,
    registry_col: str = "SR",
    definitions: list[str] | tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Compare monthly phenotype counts with monthly registry counts."""
    if registry_col not in df.columns:
        raise KeyError(f"Registry column not found: {registry_col}")
    if definitions is None:
        definitions = [c for c in df.columns if c.startswith("D")]

    records = []
    for definition in definitions:
        if definition not in df.columns:
            continue
        tmp = df[[registry_col, definition]].apply(pd.to_numeric, errors="coerce").dropna()
        if tmp.empty:
            records.append({
                "definition": definition,
                "n_months": 0,
                "registry_total": np.nan,
                "definition_total": np.nan,
                "registry_mean_monthly": np.nan,
                "definition_mean_monthly": np.nan,
                "MAE": np.nan,
                "nMAE": np.nan,
                "nMAE_percent": np.nan,
                "mean_signed_error": np.nan,
                "total_count_ratio": np.nan,
                "Pearson_r": np.nan,
                "bias_direction": "not_evaluable",
            })
            continue

        y = tmp[registry_col].astype(float)
        x = tmp[definition].astype(float)
        diff = x - y
        mae = float(diff.abs().mean())
        mean_registry = float(y.mean())
        nmae = mae / mean_registry if mean_registry != 0 else np.nan
        signed = float(diff.mean())
        ratio = float(x.sum() / y.sum()) if y.sum() != 0 else np.nan

        records.append({
            "definition": definition,
            "n_months": int(len(tmp)),
            "registry_total": float(y.sum()),
            "definition_total": float(x.sum()),
            "registry_mean_monthly": mean_registry,
            "definition_mean_monthly": float(x.mean()),
            "MAE": mae,
            "nMAE": float(nmae),
            "nMAE_percent": float(100 * nmae) if pd.notna(nmae) else np.nan,
            "mean_signed_error": signed,
            "total_count_ratio": ratio,
            "Pearson_r": pearson_safe(x, y),
            "bias_direction": "over-count" if signed > 0 else "under-count" if signed < 0 else "balanced",
        })
    return pd.DataFrame(records)
