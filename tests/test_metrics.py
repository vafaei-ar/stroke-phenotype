import math

import pandas as pd

from stroke_phenotype.metrics import compute_count_metrics


def test_mae_units_and_normalization():
    df = pd.DataFrame({"SR": [10, 20, 30], "D0": [12, 18, 36]})
    row = compute_count_metrics(df).set_index("definition").loc["D0"]
    assert math.isclose(row["MAE"], (2 + 2 + 6) / 3)
    assert math.isclose(row["registry_mean_monthly"], 20)
    assert math.isclose(row["nMAE"], ((2 + 2 + 6) / 3) / 20)


def test_all_missing_definition_is_not_evaluable():
    df = pd.DataFrame({"SR": [10, 20], "D6": [pd.NA, pd.NA]})
    row = compute_count_metrics(df).iloc[0]
    assert row["n_months"] == 0
    assert row["bias_direction"] == "not_evaluable"
