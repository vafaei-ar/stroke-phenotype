import pandas as pd

from stroke_phenotype.definitions import phenotype_masks


def test_d0_is_all_rows_and_has_no_imaging_requirement():
    df = pd.DataFrame({
        "ct": [False, False],
        "mri": [False, True],
        "lipid": [False, False],
        "rehab": [False, False],
    })
    masks = phenotype_masks(df)
    assert masks["D0"].tolist() == [True, True]


def test_primary_definition_logic():
    df = pd.DataFrame({
        "ct": [True, False, True, False],
        "mri": [False, True, True, False],
        "lipid": [True, True, False, True],
        "rehab": [False, True, True, True],
    })
    m = phenotype_masks(df, include_exploratory=True)
    assert m["D1"].tolist() == [True, True, False, False]
    assert m["D3"].tolist() == [False, True, False, False]
    assert m["D6"].tolist() == [False, True, False, False]
    assert m["D8"].tolist() == [True, False, False, False]
    assert m["D9"].tolist() == [False, True, False, False]
