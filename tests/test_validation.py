import pandas as pd

from stroke_phenotype.validation import _month_filter


def test_month_filter_accepts_legacy_date_column() -> None:
    df = pd.DataFrame(
        {
            "date": ["2023-01", "2023-02", "2023-03", "2023-04"],
            "SR": [1, 2, 3, 4],
            "D0": [2, 3, 4, 5],
        }
    )

    out = _month_filter(df, "2023-02", "2023-03")

    assert out["month"].tolist() == ["2023-02", "2023-03"]
    assert out.index.astype(str).tolist() == ["2023-02", "2023-03"]
