import pandas as pd

from stroke_phenotype.legacy import standardize_legacy_center1_features


def _legacy_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "PATID": ["p1", "p1", "p2", "p3"],
            "ENCOUNTERID": ["e1", "e2", "e3", "e4"],
            "ADMIT_DATE": ["2020-01-01", "2020-02-01", "2020-01-03", "2020-01-04"],
            "FACILITYID": ["OTHER", "TARGET", "TARGET", "TARGET"],
            "MRI-2": [False, True, False, "false"],
            "MRI-ENC": [False, False, True, "true"],
            "CT-2": [True, False, False, "0"],
            "CT-ENC": [False, False, False, "1"],
            "lip": [True, True, "1", "false"],
            "phy": [False, True, "yes", "no"],
        }
    )


def test_legacy_standardization_preserves_first_event_then_facility_filter() -> None:
    out = standardize_legacy_center1_features(
        _legacy_rows(),
        facility_contains="TARGET",
        first_event_only=True,
    )

    # p1 is excluded because the historical pipeline selected the first event
    # (OTHER) before applying the facility restriction.
    assert out["patient_id"].tolist() == ["p2", "p3"]
    assert out["encounter_id"].tolist() == ["e3", "e4"]


def test_legacy_imaging_union_matches_mri_2_enc_and_ct_2_enc() -> None:
    out = standardize_legacy_center1_features(_legacy_rows(), first_event_only=False)
    out = out.set_index("encounter_id")

    assert bool(out.loc["e3", "mri"])
    assert bool(out.loc["e4", "mri"])
    assert bool(out.loc["e1", "ct"])
    assert bool(out.loc["e4", "ct"])
    assert bool(out.loc["e3", "lipid"])
    assert bool(out.loc["e3", "rehab"])
