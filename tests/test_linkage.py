import pandas as pd
import pytest

from stroke_phenotype.linkage import filter_primary_ischemic_registry, linked_precision


def test_registry_filter_and_encounter_linked_precision():
    ehr = pd.DataFrame({
        "encounter_id": ["10", "11", "12"],
        "ct": [True, True, False],
        "mri": [False, True, True],
        "lipid": [True, True, True],
        "rehab": [False, True, False],
    })
    registry = pd.DataFrame({
        "encounter_id": ["10", "11", "99"],
        "diagnosis": ["Primary", "Primary", "Secondary"],
        "stroke_type": ["Ischemic", "Ischemic", "Ischemic"],
    })
    registry = filter_primary_ischemic_registry(registry)
    out = linked_precision(ehr, registry).set_index("definition")
    assert out.loc["D0", "definition_positive"] == 3
    assert out.loc["D0", "matched_registry"] == 2
    assert out.loc["D0", "precision"] == 2 / 3
    assert out.loc["D6", "precision"] == 1.0


def test_legacy_registry_column_names_and_leading_zero_ids():
    ehr = pd.DataFrame({
        "encounter_id": ["0010", "0011"],
        "ct": [True, True],
        "mri": [False, True],
        "lipid": [True, True],
        "rehab": [False, True],
    })
    registry = pd.DataFrame({
        "FIN": ["0011", "0099", "0010"],
        "Diagnosis": ["Primary", "Primary", "Secondary"],
        "Type": ["Ischemic", "Ischemic", "Ischemic"],
    })

    registry = filter_primary_ischemic_registry(
        registry,
        diagnosis_col="Diagnosis",
        stroke_type_col="Type",
    )
    out = linked_precision(
        ehr,
        registry,
        registry_encounter_col="FIN",
    ).set_index("definition")

    assert out.loc["D0", "matched_registry"] == 1
    assert out.loc["D6", "matched_registry"] == 1
    assert out.loc["D6", "precision"] == 1.0


def test_registry_filter_requires_primary_and_type_fields():
    registry = pd.DataFrame({"FIN": ["1"]})
    with pytest.raises(KeyError, match="required columns"):
        filter_primary_ischemic_registry(
            registry,
            diagnosis_col="Diagnosis",
            stroke_type_col="Type",
        )
