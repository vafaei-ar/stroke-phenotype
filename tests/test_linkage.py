import pandas as pd
import pytest

from stroke_phenotype.linkage import (
    filter_primary_ischemic_registry,
    linked_patient_precision,
    linked_precision,
    registry_patient_ids_from_fin_crosswalk,
)


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


def test_legacy_fin_crosswalk_to_patient_precision():
    ehr = pd.DataFrame({
        "patient_id": ["PSU1", "PSU2", "PSU3"],
        "ct": [True, True, False],
        "mri": [False, True, True],
        "lipid": [True, True, True],
        "rehab": [False, True, False],
    })
    registry = pd.DataFrame({
        "FIN": ["0011", "0099", "0010"],
        "Diagnosis": ["Primary", "Primary", "Secondary"],
        "Type": ["Ischemic", "Ischemic", "Ischemic"],
    })
    conversion = pd.DataFrame({
        "FIN": ["0011", "0099", "0010", "7777"],
        "PAT_ID": ["PSU2", "PSU9", "PSU1", "OTHER1"],
    })

    registry = filter_primary_ischemic_registry(
        registry,
        diagnosis_col="Diagnosis",
        stroke_type_col="Type",
    )
    truth = registry_patient_ids_from_fin_crosswalk(
        registry,
        conversion,
        registry_fin_col="FIN",
        conversion_fin_col="FIN",
        conversion_patient_col="PAT_ID",
        patient_prefix="PSU",
    )

    assert set(truth) == {"PSU2", "PSU9"}

    out = linked_patient_precision(
        ehr,
        truth,
        patient_col="patient_id",
        include_exploratory=True,
    ).set_index("definition")

    assert out.loc["D0", "definition_positive"] == 3
    assert out.loc["D0", "matched_registry"] == 1
    assert out.loc["D6", "definition_positive"] == 1
    assert out.loc["D6", "matched_registry"] == 1
    assert out.loc["D6", "precision"] == 1.0
    assert out.loc["D9", "precision"] == 1.0


def test_registry_filter_requires_primary_and_type_fields():
    registry = pd.DataFrame({"FIN": ["1"]})
    with pytest.raises(KeyError, match="required columns"):
        filter_primary_ischemic_registry(
            registry,
            diagnosis_col="Diagnosis",
            stroke_type_col="Type",
        )


def test_legacy_crosswalk_column_alias_pat_id_vs_patid():
    registry = pd.DataFrame({
        "FIN": ["0011"],
        "Diagnosis": ["Primary"],
        "Type": ["Ischemic"],
    })
    conversion = pd.DataFrame({
        "FIN": ["0011"],
        "PATID": ["PSU2"],
    })

    registry = filter_primary_ischemic_registry(
        registry,
        diagnosis_col="Diagnosis",
        stroke_type_col="Type",
    )
    truth = registry_patient_ids_from_fin_crosswalk(
        registry,
        conversion,
        registry_fin_col="FIN",
        conversion_fin_col="FIN",
        conversion_patient_col="PAT_ID",
        patient_prefix="PSU",
    )

    assert truth.tolist() == ["PSU2"]
