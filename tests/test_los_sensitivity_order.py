import pandas as pd

from stroke_phenotype.legacy import standardize_legacy_center1_features


def _features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "PATID": ["p1", "p1", "p2"],
            "ENCOUNTERID": ["e1", "e2", "e3"],
            "ADMIT_DATE": ["2020-01-01", "2020-01-03", "2020-01-02"],
            "FACILITYID": ["TARGET", "TARGET", "TARGET"],
            "MRI-2": [False, True, False],
            "MRI-ENC": [False, False, True],
            "CT-2": [True, False, False],
            "CT-ENC": [False, False, False],
            "lip": [True, True, True],
            "phy": [False, True, False],
        }
    )


def test_exact_los_eligibility_is_applied_before_first_event_selection() -> None:
    features = _features()

    baseline = standardize_legacy_center1_features(
        features,
        facility_contains="TARGET",
        first_event_only=True,
    )
    assert baseline.loc[baseline["patient_id"] == "p1", "encounter_id"].item() == "e1"

    # Simulate exact LOS >24 h excluding p1's earlier short encounter.
    strict_input = features.loc[features["ENCOUNTERID"] != "e1"].copy()
    strict = standardize_legacy_center1_features(
        strict_input,
        facility_contains="TARGET",
        first_event_only=True,
    )

    # The later encounter becomes p1's first qualifying event under the strict rule.
    assert strict.loc[strict["patient_id"] == "p1", "encounter_id"].item() == "e2"
