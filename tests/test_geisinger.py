import pandas as pd

from stroke_phenotype.geisinger import build_geisinger_monthly_table


MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _conditions_fixture() -> pd.DataFrame:
    sections = [
        ("SITE", None),
        ("any Imaging", 5),
        ("any imaging AND (Chol./Lip. OR Phy./Rehab.)", 2),
        ("any imaging AND Chol./Lip.", 1),
        ("CT AND Chol./Lip.", 8),
        ("MRI", 7),
        ("MRI AND (Chol./Lip. OR Phy./Rehab.)", 4),
        ("MRI AND Chol./Lip.", 3),
        ("MRI AND Chol./Lip. AND Phy./Rehab.", 6),
        ("diagnosis", 0),
    ]

    rows = [{"Row Labels": "SITE", "2020": 999}]
    for label, definition in sections[1:]:
        rows.append({"Row Labels": label, "2020": 999})
        for month_num, month in enumerate(MONTHS, start=1):
            rows.append({
                "Row Labels": month,
                "2020": definition * 100 + month_num,
            })
    return pd.DataFrame(rows)


def _registry_fixture() -> pd.DataFrame:
    row = {"Year": 2020}
    for month_num, month in enumerate(MONTHS, start=1):
        row[month] = month_num
    return pd.DataFrame([row])


def test_build_geisinger_monthly_table_maps_sections_to_definitions() -> None:
    out = build_geisinger_monthly_table(
        _conditions_fixture(),
        _registry_fixture(),
        start="2020-03",
        end="2020-05",
    )

    assert out["month"].tolist() == ["2020-03", "2020-04", "2020-05"]
    assert out["SR"].tolist() == [3, 4, 5]
    assert out["D0"].tolist() == [3, 4, 5]
    assert out["D1"].tolist() == [103, 104, 105]
    assert out["D6"].tolist() == [603, 604, 605]
    assert out["D8"].tolist() == [803, 804, 805]
