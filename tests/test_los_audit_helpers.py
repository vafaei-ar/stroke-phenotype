import pandas as pd


def test_legacy_same_day_is_not_equivalent_to_gt24() -> None:
    admit = pd.Timestamp("2020-01-01 23:00:00")
    discharge = pd.Timestamp("2020-01-02 01:00:00")

    non_same_day = admit.normalize() != discharge.normalize()
    gt24 = (discharge - admit) > pd.Timedelta(hours=24)

    assert non_same_day
    assert not gt24
