import pandas as pd

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
