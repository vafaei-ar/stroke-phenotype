import pandas as pd
import pytest

from stroke_phenotype.registry import align_counts_to_registry_months


def test_registry_alignment_drops_phenotype_only_months() -> None:
    counts = pd.DataFrame(
        {
            "month": ["2010-01", "2016-12", "2017-01", "2024-01"],
            "D0": [5, 10, 11, 7],
            "D9": [1, 4, 5, 2],
        }
    )
    registry = pd.DataFrame(
        {
            "month": ["2016-12", "2017-01"],
            "SR": [8, 9],
        }
    )

    out, dropped = align_counts_to_registry_months(counts, registry)

    assert out["month"].tolist() == ["2016-12", "2017-01"]
    assert out["SR"].tolist() == [8, 9]
    assert out["D9"].tolist() == [4, 5]
    assert dropped == ["2010-01", "2024-01"]


def test_registry_alignment_requires_every_registry_month() -> None:
    counts = pd.DataFrame(
        {
            "month": ["2016-12"],
            "D0": [10],
        }
    )
    registry = pd.DataFrame(
        {
            "month": ["2016-12", "2017-01"],
            "SR": [8, 9],
        }
    )

    with pytest.raises(ValueError, match="missing registry months"):
        align_counts_to_registry_months(counts, registry)
