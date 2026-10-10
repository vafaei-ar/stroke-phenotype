import pandas as pd

from stroke_phenotype.cohort import select_first_qualifying_encounter


def test_first_qualifying_encounter_per_patient():
    df = pd.DataFrame({
        "patient_id": ["a", "a", "b"],
        "admit_date": ["2021-02-01", "2021-01-01", "2021-03-01"],
        "encounter_id": ["a2", "a1", "b1"],
    })
    out = select_first_qualifying_encounter(df)
    assert out["encounter_id"].tolist() == ["a1", "b1"]
