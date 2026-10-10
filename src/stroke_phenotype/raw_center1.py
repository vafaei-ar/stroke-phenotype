"""Legacy-compatible Center 1 feature preparation from protected PCORnet tables.

This module reproduces the manuscript-generating notebook behavior first. It does
not silently replace legacy cohort or imaging-window semantics with the clinically
intended rules described in the manuscript. Those discrepancies are documented
and can be addressed in a deliberate canonical-analysis revision later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .codes import (
    CT_CPT,
    ISCHEMIC_STROKE_ICD10,
    ISCHEMIC_STROKE_ICD9,
    LEGACY_REHAB_CPT,
    MRI_CPT,
)
from .legacy import standardize_legacy_center1_features

DIAGNOSIS_COLUMNS = ("PATID", "ENCOUNTERID", "DX")
ENCOUNTER_COLUMNS = (
    "PATID",
    "ENCOUNTERID",
    "ADMIT_DATE",
    "DISCHARGE_DATE",
    "ENC_TYPE",
    "FACILITYID",
)
PROCEDURE_COLUMNS = ("PATID", "ENCOUNTERID", "PX_DATE", "PX")
LAB_COLUMNS = ("PATID", "ENCOUNTERID", "LAB_LOINC")


def _require_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"{label} is missing required columns: {missing}")


def _prepare_ids(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        out[column] = out[column].astype("string")
    return out


def _historical_non_same_day_mask(encounters: pd.DataFrame) -> pd.Series:
    """Reproduce the notebook's effective overnight rule.

    The notebook kept rows whenever its admission/discharge calendar-day values
    differed. Missing discharge dates also survived that comparison. This is a
    compatibility rule, not an exact elapsed LOS >24-hour rule.
    """
    admit = pd.to_datetime(encounters["ADMIT_DATE"], errors="coerce")
    discharge = pd.to_datetime(encounters["DISCHARGE_DATE"], errors="coerce")
    same_day = (
        admit.notna()
        & discharge.notna()
        & admit.dt.normalize().eq(discharge.dt.normalize())
    )
    return ~same_day


def _membership_keys(
    df: pd.DataFrame,
    code_col: str,
    codes: set[str],
) -> set[tuple[str, str]]:
    selected = df[df[code_col].isin(codes)]
    return set(zip(selected["PATID"].astype(str), selected["ENCOUNTERID"].astype(str)))


def _within_two_days(
    rows: pd.DataFrame,
    procedures: pd.DataFrame,
    codes: set[str],
) -> pd.Series:
    selected = procedures[procedures["PX"].isin(codes)].copy()
    selected["PX_DATE"] = pd.to_datetime(selected["PX_DATE"], errors="coerce")
    dates_by_patient = {
        str(patient_id): group["PX_DATE"].dropna().to_numpy(dtype="datetime64[ns]")
        for patient_id, group in selected.groupby("PATID", sort=False)
    }

    values: list[bool] = []
    for patient_id, admit_date in zip(rows["PATID"].astype(str), rows["ADMIT_DATE"]):
        dates = dates_by_patient.get(patient_id)
        if dates is None or len(dates) == 0 or pd.isna(admit_date):
            values.append(False)
            continue
        admit64 = np.datetime64(pd.Timestamp(admit_date).to_datetime64())
        values.append(bool(np.min(np.abs(dates - admit64)) <= np.timedelta64(2, "D")))
    return pd.Series(values, index=rows.index, dtype=bool)


def _family_intermediates(
    diagnosis: pd.DataFrame,
    encounters: pd.DataFrame,
    procedures: pd.DataFrame,
    labs: pd.DataFrame,
    codes: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dx_encounter_ids = pd.unique(
        diagnosis.loc[diagnosis["DX"].isin(codes), "ENCOUNTERID"].dropna()
    )
    family_encounters = encounters[
        encounters["ENCOUNTERID"].isin(dx_encounter_ids)
    ].copy()

    eligible = family_encounters[_historical_non_same_day_mask(family_encounters)]
    eligible_encounter_ids = np.unique(
        eligible["ENCOUNTERID"].dropna().astype(str).to_numpy()
    )
    eligible_patient_ids = np.unique(
        eligible["PATID"].dropna().astype(str).to_numpy()
    )

    procedure_by_encounter = procedures[
        procedures["ENCOUNTERID"].isin(eligible_encounter_ids)
    ].copy()
    procedure_by_patient = procedures[
        procedures["PATID"].isin(eligible_patient_ids)
    ].copy()
    lab_by_encounter = labs[
        labs["ENCOUNTERID"].isin(eligible_encounter_ids)
    ].copy()

    return (
        family_encounters,
        procedure_by_encounter,
        procedure_by_patient,
        lab_by_encounter,
    )


def build_legacy_center1_details(
    diagnosis: pd.DataFrame,
    encounters: pd.DataFrame,
    procedures: pd.DataFrame,
    labs: pd.DataFrame,
    *,
    lipid_codes: Iterable[str],
    rehab_codes: Iterable[str] = LEGACY_REHAB_CPT,
) -> pd.DataFrame:
    """Reconstruct the historical df_phen_details.csv feature table.

    Preserved behaviors include EI/IP encounter restriction, the notebook's
    non-same-calendar-day patient qualification, patient-history imaging searched
    with an absolute +/-2-day admission window, same-encounter imaging/rehab/lipid
    flags from qualifying encounter IDs, and the historical requirement that
    qualifying patients appear in the procedures table.
    """
    _require_columns(diagnosis, DIAGNOSIS_COLUMNS, "diagnosis")
    _require_columns(encounters, ENCOUNTER_COLUMNS, "encounter")
    _require_columns(procedures, PROCEDURE_COLUMNS, "procedures")
    _require_columns(labs, LAB_COLUMNS, "lab_result_cm")

    diagnosis = _prepare_ids(
        diagnosis[list(DIAGNOSIS_COLUMNS)],
        ("PATID", "ENCOUNTERID", "DX"),
    )
    encounters = _prepare_ids(
        encounters[list(ENCOUNTER_COLUMNS)],
        ("PATID", "ENCOUNTERID", "ENC_TYPE", "FACILITYID"),
    )
    procedures = _prepare_ids(
        procedures[list(PROCEDURE_COLUMNS)],
        ("PATID", "ENCOUNTERID", "PX"),
    )
    labs = _prepare_ids(
        labs[list(LAB_COLUMNS)],
        ("PATID", "ENCOUNTERID", "LAB_LOINC"),
    )

    encounters["ADMIT_DATE"] = pd.to_datetime(
        encounters["ADMIT_DATE"],
        errors="coerce",
    )
    encounters["DISCHARGE_DATE"] = pd.to_datetime(
        encounters["DISCHARGE_DATE"],
        errors="coerce",
    )
    procedures["PX_DATE"] = pd.to_datetime(
        procedures["PX_DATE"],
        errors="coerce",
    )

    encounters = encounters[encounters["ENC_TYPE"].isin(("EI", "IP"))].copy()

    family_data = [
        _family_intermediates(
            diagnosis,
            encounters,
            procedures,
            labs,
            ISCHEMIC_STROKE_ICD9,
        ),
        _family_intermediates(
            diagnosis,
            encounters,
            procedures,
            labs,
            ISCHEMIC_STROKE_ICD10,
        ),
    ]

    sub_enc = pd.concat(
        [item[0] for item in family_data],
        axis=0,
        ignore_index=True,
    )
    sub_px_enc = pd.concat(
        [item[1] for item in family_data],
        axis=0,
        ignore_index=True,
    )
    sub_px_patient = pd.concat(
        [item[2] for item in family_data],
        axis=0,
        ignore_index=True,
    )
    sub_lab_enc = pd.concat(
        [item[3] for item in family_data],
        axis=0,
        ignore_index=True,
    )

    # Historical patient order came from the concatenated patient-history
    # procedure table, with ICD-9 family rows before ICD-10 family rows.
    patient_order = [
        str(value)
        for value in pd.unique(sub_px_patient["PATID"].dropna())
    ]
    order = {
        patient_id: index
        for index, patient_id in enumerate(patient_order)
    }

    # The notebook used a sorted PATID/ENCOUNTERID MultiIndex and called
    # drop_duplicates on the remaining encounter columns for each patient.
    rows = sub_enc[sub_enc["PATID"].isin(patient_order)].copy()
    rows = rows.sort_values(
        ["PATID", "ENCOUNTERID"],
        kind="mergesort",
    )
    rows = rows.drop_duplicates(
        subset=[
            "PATID",
            "ENC_TYPE",
            "FACILITYID",
            "ADMIT_DATE",
            "DISCHARGE_DATE",
        ],
        keep="first",
    )
    rows["_patient_order"] = rows["PATID"].astype(str).map(order)
    rows = rows.sort_values(
        ["_patient_order", "ENCOUNTERID"],
        kind="mergesort",
    ).reset_index(drop=True)

    mri_codes = set(MRI_CPT)
    ct_codes = set(CT_CPT)
    rehab_codes = {str(code) for code in rehab_codes}
    lipid_codes = {str(code) for code in lipid_codes}

    mri_patient_encounter = _membership_keys(
        sub_px_patient,
        "PX",
        mri_codes,
    )
    ct_patient_encounter = _membership_keys(
        sub_px_patient,
        "PX",
        ct_codes,
    )
    mri_eligible_encounter = _membership_keys(
        sub_px_enc,
        "PX",
        mri_codes,
    )
    ct_eligible_encounter = _membership_keys(
        sub_px_enc,
        "PX",
        ct_codes,
    )
    rehab_eligible_encounter = _membership_keys(
        sub_px_enc,
        "PX",
        rehab_codes,
    )
    lipid_eligible_encounter = _membership_keys(
        sub_lab_enc,
        "LAB_LOINC",
        lipid_codes,
    )

    keys = list(
        zip(
            rows["PATID"].astype(str),
            rows["ENCOUNTERID"].astype(str),
        )
    )
    rows["MRI"] = [
        key in mri_patient_encounter
        for key in keys
    ]
    rows["CT"] = [
        key in ct_patient_encounter
        for key in keys
    ]
    rows["MRI-2"] = _within_two_days(
        rows,
        sub_px_patient,
        mri_codes,
    )
    rows["CT-2"] = _within_two_days(
        rows,
        sub_px_patient,
        ct_codes,
    )
    rows["MRI-ENC"] = [
        key in mri_eligible_encounter
        for key in keys
    ]
    rows["CT-ENC"] = [
        key in ct_eligible_encounter
        for key in keys
    ]
    rows["phy"] = [
        key in rehab_eligible_encounter
        for key in keys
    ]
    rows["lip"] = [
        key in lipid_eligible_encounter
        for key in keys
    ]

    dx_union = diagnosis[
        diagnosis["DX"].isin(
            ISCHEMIC_STROKE_ICD9 + ISCHEMIC_STROKE_ICD10
        )
    ]
    diag_counts = dx_union.groupby(
        ["PATID", "ENCOUNTERID"],
        sort=False,
    ).size()
    rows["NSDiag"] = [
        int(diag_counts.get(key, 0))
        for key in keys
    ]

    return rows[
        [
            "PATID",
            "ENCOUNTERID",
            "FACILITYID",
            "ADMIT_DATE",
            "NSDiag",
            "MRI",
            "CT",
            "MRI-2",
            "CT-2",
            "MRI-ENC",
            "CT-ENC",
            "lip",
            "phy",
        ]
    ].reset_index(drop=True)


def prepare_legacy_compatible_center1_features(
    diagnosis: pd.DataFrame,
    encounters: pd.DataFrame,
    procedures: pd.DataFrame,
    labs: pd.DataFrame,
    *,
    lipid_codes: Iterable[str],
    facility_contains: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return historical detail rows plus canonical first-event features."""
    details = build_legacy_center1_details(
        diagnosis,
        encounters,
        procedures,
        labs,
        lipid_codes=lipid_codes,
    )
    canonical = standardize_legacy_center1_features(
        details,
        facility_contains=facility_contains,
        first_event_only=True,
    )
    return details, canonical


def read_lipid_codes(path: str | Path) -> list[str]:
    df = pd.read_csv(
        path,
        dtype="string",
        keep_default_na=False,
    )
    if "loinc_code" in df.columns:
        column = "loinc_code"
    elif "LOINC_NUM" in df.columns:
        column = "LOINC_NUM"
    else:
        raise KeyError(
            "Lipid code file must contain loinc_code or LOINC_NUM"
        )

    codes = df[column].astype("string").str.strip()
    return [
        str(code)
        for code in codes
        if code
    ]


def compare_rehab_reference(
    path: str | Path,
) -> tuple[set[str], set[str]]:
    df = pd.read_csv(
        path,
        dtype="string",
        keep_default_na=False,
    )
    if "cpt_code" in df.columns:
        column = "cpt_code"
    elif "CPT Code" in df.columns:
        column = "CPT Code"
    else:
        raise KeyError(
            "Rehabilitation code file must contain cpt_code or CPT Code"
        )

    observed = {
        str(code).strip()
        for code in df[column]
        if str(code).strip()
    }
    legacy = set(LEGACY_REHAB_CPT)
    return legacy - observed, observed - legacy
