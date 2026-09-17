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

## Why this bridge exists

The original notebook contains raw extraction, exploratory analyses, hard-coded local paths, and manuscript calculations in one file. Rewriting all of that at once risks changing the scientific analysis silently. The compatibility stage lets us first prove that the new canonical D0-D8 implementation reproduces the current manuscript results. After that check passes, the protected raw-EHR extraction can be refactored into a separate, testable preparation module.

## Important historical behavior preserved

1. The candidate table is already ICD-eligible.
2. D0 is therefore every eligible row.
3. The manuscript imaging flag used `MRI-2-ENC`/`CT-2-ENC`, the union of the 2-day and same-encounter indicators.
4. The historical code selected the first qualifying encounter per patient before applying the local facility restriction. The compatibility importer preserves this ordering exactly.
5. Local facility strings belong in local command lines/configuration only and must not be committed.

## Next refactor stage

Once the compatibility pipeline reproduces the manuscript aggregate values, replace the notebook extraction with a protected-data preparation command that reads the local EHR tables and produces the same canonical schema:

```text
patient_id, encounter_id, admit_date, ct, mri, lipid, rehab
```

That change should be validated against the compatibility output before the historical notebook is retired.
