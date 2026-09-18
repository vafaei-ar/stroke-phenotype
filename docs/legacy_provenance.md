# Legacy-to-canonical provenance

The historical analysis was developed across multiple notebooks. The refactor therefore proceeds in checkpoints: first reproduce the manuscript-generating intermediate outputs, then replace the raw extraction without silently changing the scientific analysis.

## Historical Center 1 pipeline

The traced historical Center 1 pipeline is:

```text
protected PCORnet tables
        |
        v
stroke-code encounter selection
        |
        +-- encounter type restricted to EI/IP
        +-- overnight/non-same-calendar-day patient qualification
        +-- procedure/lab subsets built from qualifying encounter and patient IDs
        |
        v
phd_rec.ipynb
        |
        +-- CT/MRI same-encounter flags
        +-- CT/MRI absolute +/-2-day patient-history flags
        +-- lipid and rehabilitation same-encounter flags
        |
        v
outcomes/df_phen_details.csv
        |
        +-- MRI-2-ENC = MRI-2 OR MRI-ENC
        +-- CT-2-ENC  = CT-2 OR CT-ENC
        |
        v
first qualifying encounter per patient
        |
        v
local Center 1 facility restriction
        |
        v
D0-D8 monthly counts
```

The compatibility importer in `scripts/01_import_legacy_center1_features.py` reproduces the pipeline from `df_phen_details.csv` forward. The new `scripts/01_prepare_center1_features.py` begins the upstream replacement from the protected raw PCORnet Parquet tables.

## Compatibility checkpoint achieved

On the protected Center 1 intermediate data, the clean compatibility pipeline reproduced the historical `PS_conditions.csv` monthly counts exactly for every definition D0-D8 over December 2016 through December 2023 (85 months):

| Definition | Historical total | Clean compatibility total | Maximum monthly absolute difference |
|---|---:|---:|---:|
| D0 | 6,582 | 6,582 | 0 |
| D1 | 4,953 | 4,953 | 0 |
| D2 | 5,872 | 5,872 | 0 |
| D3 | 4,320 | 4,320 | 0 |
| D4 | 4,821 | 4,821 | 0 |
| D5 | 6,192 | 6,192 | 0 |
| D6 | 3,388 | 3,388 | 0 |
| D7 | 5,016 | 5,016 | 0 |
| D8 | 4,189 | 4,189 | 0 |

This is the frozen regression target while the upstream raw-EHR extraction is refactored.

## Historical behaviors that must be reproduced before cleanup

1. Stroke-code encounters were restricted to EI/IP encounter types.
2. The notebook's hospitalization rule was not an exact elapsed LOS >24-hour calculation. It used a non-same-calendar-day qualification step. The separate LOS audit documents the resulting sensitivity analysis.
3. That qualification created eligible patient and encounter IDs but did not permanently filter the broader stroke-encounter table. As a result, a same-day stroke encounter could later reappear for a patient who had another qualifying overnight encounter.
4. The patient list used to build `df_phen_details.csv` came from the qualifying-patient procedure subset. Therefore an otherwise qualifying patient with no procedure record could be absent from the detail table. This historical behavior is preserved only for regression testing and should be evaluated before any canonical redesign.
5. The historical imaging variable used in D0-D8 was `MRI-2-ENC`/`CT-2-ENC`, defined as the union of a same-encounter flag and a patient-history imaging flag where the minimum **absolute** difference between admission date and procedure date was <=2 days. This is not identical to the manuscript prose stating two days before admission through the end of hospitalization.
6. Rehabilitation and lipid flags were same-encounter signals from the qualifying encounter subsets.
7. The historical code selected the first qualifying encounter per patient before applying the local facility restriction. The compatibility importer preserves this ordering, including the original same-date tie behavior, for reproduction only.
8. Local facility strings and patient-level data remain local and must not be committed.

## Code-list provenance

The historical imaging lists contain 3 CT CPT codes and 6 MRI CPT codes. The ischemic stroke lists contain 9 ICD-9 codes and 118 ICD-10 codes. The lipid list contains 214 LOINC entries and was recovered from the historical CSV.

The manuscript-generating rehabilitation code used a hard-coded list of 78 entries with a duplicated 97161-97172 block, corresponding to 66 unique CPT codes. A separately located `Physical_Rehab.csv` has 65 rows. Exact legacy reproduction therefore uses the 66 notebook-derived unique codes while the one-code discrepancy is audited.

## Resolved Center 1 D0 count

The reproducible Center 1 D0 total is **6,582**. The prior manuscript value of 6,579 was traced to a manually entered/stale value rather than a reproducible count derivation. Unless a separate scientifically justified exclusion is found, the manuscript should be corrected to 6,582; with the other three site totals unchanged, the corresponding four-center total becomes 14,469.

## Length-of-stay discrepancy

The manuscript states hospitalization >24 hours, whereas the historical Center 1 implementation used a calendar-day rule. The strict >24-hour sensitivity changed Center 1 D0 from 6,582 to 6,534 and produced only small changes in monthly validation metrics. The current reproducibility target therefore remains the historical cohort; the Methods wording and cross-site LOS operationalization should be resolved explicitly rather than silently changing the Center 1 analysis.

## Raw-data refactor checkpoint achieved

The raw schemas were confirmed for `diagnosis.parquet`, `encounter.parquet`, `procedures.parquet`, and `lab_result_cm.parquet`. The new preparation module reads only the needed columns and produces the canonical local schema:

```text
patient_id, encounter_id, admit_date, facility_id, ct, mri, lipid, rehab
```

Running `scripts/01_prepare_center1_features.py` against the current protected `stroke_data` snapshot produced 14,890 reconstructed legacy detail rows and 11,147 standardized first-event rows. Rebuilding monthly D0-D8 counts from those standardized rows reproduced `PS_conditions.csv` exactly over all 85 months from December 2016 through December 2023:

| Definition | Legacy total | Raw-refactor total | Maximum monthly absolute difference |
|---|---:|---:|---:|
| D0 | 6,582 | 6,582 | 0 |
| D1 | 4,953 | 4,953 | 0 |
| D2 | 5,872 | 5,872 | 0 |
| D3 | 4,320 | 4,320 | 0 |
| D4 | 4,821 | 4,821 | 0 |
| D5 | 6,192 | 6,192 | 0 |
| D6 | 3,388 | 3,388 | 0 |
| D7 | 5,016 | 5,016 | 0 |
| D8 | 4,189 | 4,189 | 0 |

This establishes an end-to-end Center 1 count-reproduction path from the protected raw PCORnet tables to the manuscript-generating monthly phenotype counts without depending on `data_Sep2024.npy` or `phd_rec.ipynb`.

The rehabilitation reference audit also identified the exact difference between the 65-row `Physical_Rehab.csv` and the 66 unique notebook-derived CPT codes: `97156` is present in the notebook rule and absent from the CSV. Exact historical reproduction therefore continues to use the notebook-derived list.

### Adult-age eligibility audit

The manuscript currently describes the cohort as adults age >=18. The historical Center 1 notebook provenance does not show an explicit age filter in the phenotype-construction path traced so far. In `eda_Jan2024.ipynb`, `patid_dic` is created directly from diagnosis rows matching the ischemic/hemorrhagic code lists:

```text
sub_df = df_dx[df_dx['DX'].isin(codes)].compute()
patid_dic[i] = unique(sub_df['PATID'])
encid_dic[i] = unique(sub_df['ENCOUNTERID'])
```

The later `stroke_data` export builds `pat_id_all` from those diagnosis-derived patient-ID sets and subsets each PCORnet table by PATID. That export contains no demographic join, BIRTH_DATE calculation, or age >=18 condition. Demographics and age are merged/calculated later for descriptive and downstream analyses.

This strongly indicates that age >=18 was not explicitly enforced in the traced Center 1 phenotype pipeline. One narrow provenance check remains before treating this as fully resolved: confirm that `df_dx` itself was loaded from the diagnosis source without an upstream age-restricted filter. The clean raw-data preparer should not add an age filter unless such an upstream restriction is found.
