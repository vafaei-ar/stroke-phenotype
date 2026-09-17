# Legacy-to-canonical provenance

The historical analysis was developed across multiple notebooks. To avoid changing results while the raw-EHR extraction is being refactored, the repository first reproduces the manuscript from the protected intermediate table created by the Center 1 notebook.

## Current provenance

The historical Center 1 count pipeline is:

```text
protected raw EHR tables
        |
        v
phd_rec.ipynb
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

The compatibility importer in `scripts/01_import_legacy_center1_features.py` reproduces the middle of this pipeline without committing any patient-level data.

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

This establishes the historical Center 1 monthly phenotype-count pipeline as a frozen regression target while the upstream raw-EHR extraction is refactored.

## Why this bridge exists

The original notebook contains raw extraction, exploratory analyses, hard-coded local paths, and manuscript calculations in one file. Rewriting all of that at once risks changing the scientific analysis silently. The compatibility stage lets us first prove that the new canonical D0-D8 implementation reproduces the current manuscript results. After that check passes, the protected raw-EHR extraction can be refactored into a separate, testable preparation module.

## Important historical behavior preserved

1. The candidate table is already ICD-eligible.
2. D0 is therefore every eligible row.
3. The manuscript imaging flag used `MRI-2-ENC`/`CT-2-ENC`, the union of the 2-day and same-encounter indicators.
4. The historical code selected the first qualifying encounter per patient before applying the local facility restriction. The compatibility importer preserves this ordering exactly, including legacy same-date tie behavior for reproduction only.
5. Local facility strings belong in local command lines/configuration only and must not be committed.

## Open reconciliation item

The frozen Center 1 monthly D0 total is 6,582, while the current manuscript reports 6,579 for the Center 1 ICD-only analytic cohort. This 3-record discrepancy is not caused by the clean refactor because the refactor reproduces the historical monthly file exactly. It should be reconciled against the manuscript cohort-count derivation before the manuscript is revised.

## Next refactor stage

Replace the notebook extraction with a protected-data preparation command that reads the local EHR tables and produces the same canonical schema:

```text
patient_id, encounter_id, admit_date, ct, mri, lipid, rehab
```

That change should be validated against the compatibility output before the historical notebook is retired.
