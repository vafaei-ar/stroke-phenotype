import pandas as pd

from stroke_phenotype.codes import LEGACY_REHAB_CPT
from stroke_phenotype.raw_center1 import (
    build_legacy_center1_details,
    prepare_legacy_compatible_center1_features,
)


def _tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    diagnosis = pd.DataFrame(
        {
            "PATID": ["p1", "p1", "p2", "p3", "p4"],
            "ENCOUNTERID": ["e1", "e2", "e3", "e4", "e5"],
            "DX": ["I63.9", "I63.9", "433.01", "I63.9", "Z00.0"],
        }
    )
    encounters = pd.DataFrame(
        {
            "PATID": ["p1", "p1", "p2", "p3", "p4"],
            "ENCOUNTERID": ["e1", "e2", "e3", "e4", "e5"],
            "ADMIT_DATE": pd.to_datetime(
                [
                    "2020-01-01",
                    "2020-02-01",
                    "2020-01-05",
                    "2020-01-07",
                    "2020-01-01",
                ]
            ),
            "DISCHARGE_DATE": pd.to_datetime(
                [
                    "2020-01-03",
                    "2020-02-01",
                    "2020-01-06",
                    "2020-01-07",
                    "2020-01-03",
                ]
            ),
            "ENC_TYPE": ["IP", "IP", "EI", "IP", "IP"],
            "FACILITYID": ["TARGET"] * 5,
        }
    )
    procedures = pd.DataFrame(
        {
            "PATID": ["p1", "p1", "p1", "p2", "p3"],
            "ENCOUNTERID": ["e1", "e2", "e1", "e3", "e4"],
            "PX_DATE": pd.to_datetime(
                [
                    "2020-01-01",
                    "2020-02-01",
                    "2020-01-02",
                    "2020-01-05",
                    "2020-01-07",
                ]
            ),
            "PX": ["70450", "70551", LEGACY_REHAB_CPT[0], "70460", "70551"],
        }
    )
    labs = pd.DataFrame(
        {
            "PATID": ["p1", "p1", "p2", "p3"],
            "ENCOUNTERID": ["e1", "e2", "e3", "e4"],
            "LAB_LOINC": ["LIP", "LIP", "LIP", "LIP"],
        }
    )
    return diagnosis, encounters, procedures, labs


def test_raw_legacy_reintroduces_same_day_for_overnight_eligible_patient() -> None:
    diagnosis, encounters, procedures, labs = _tables()
    details = build_legacy_center1_details(
        diagnosis,
        encounters,
        procedures,
        labs,
        lipid_codes=["LIP"],
    )

    # ICD-9 family rows precede ICD-10 family rows in the original concatenation.
    assert details["ENCOUNTERID"].tolist() == ["e3", "e1", "e2"]

    e2 = details.set_index("ENCOUNTERID").loc["e2"]
    assert bool(e2["MRI"])
    assert bool(e2["MRI-2"])
    assert not bool(e2["MRI-ENC"])
    assert not bool(e2["lip"])


def test_raw_legacy_drops_patient_without_overnight_stay_even_with_procedure() -> None:
    diagnosis, encounters, procedures, labs = _tables()
    details = build_legacy_center1_details(
        diagnosis,
        encounters,
        procedures,
        labs,
        lipid_codes=["LIP"],
    )

    assert "e4" not in set(details["ENCOUNTERID"])


def test_raw_to_canonical_preserves_first_event_and_feature_union() -> None:
    diagnosis, encounters, procedures, labs = _tables()
    details, canonical = prepare_legacy_compatible_center1_features(
        diagnosis,
        encounters,
        procedures,
        labs,
        lipid_codes=["LIP"],
        facility_contains="TARGET",
    )

    assert len(details) == 3
    assert canonical["patient_id"].tolist() == ["p1", "p2"]

    p1 = canonical.set_index("patient_id").loc["p1"]
    assert bool(p1["ct"])
    assert not bool(p1["mri"])
    assert bool(p1["lipid"])
    assert bool(p1["rehab"])


def test_legacy_code_list_cardinalities_are_frozen() -> None:
    from stroke_phenotype.codes import (
        CT_CPT,
        ISCHEMIC_STROKE_ICD10,
        ISCHEMIC_STROKE_ICD9,
        MRI_CPT,
    )

    assert len(CT_CPT) == 3
    assert len(MRI_CPT) == 6
    assert len(ISCHEMIC_STROKE_ICD9) == 9
    assert len(ISCHEMIC_STROKE_ICD10) == 118
    assert len(LEGACY_REHAB_CPT) == 66
    assert len(set(LEGACY_REHAB_CPT)) == 66
