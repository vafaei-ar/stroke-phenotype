# Local data contract

Everything in this directory except this README is ignored by Git.

## Patient-level feature table

The analysis layer expects one row per **eligible EHR encounter**. Eligibility for the candidate cohort (ICD and hospitalization rules) should be established upstream.

Required columns:

| Column | Meaning |
|---|---|
| `patient_id` | local patient identifier |
| `encounter_id` | encounter identifier used for registry linkage when available |
| `admit_date` | encounter admission date/time |
| `ct` | CT feature, boolean |
| `mri` | MRI feature, boolean |
| `lipid` | lipid/cholesterol laboratory feature, boolean |
| `rehab` | rehabilitation assessment feature, boolean |

## Registry table for linked validation

Required: `encounter_id`. Recommended when available: `patient_id`, `admit_date`, `diagnosis`, `stroke_type`.

If `diagnosis` and `stroke_type` are supplied, the canonical filter is `Primary` and `Ischemic`, respectively.

## Monthly count table

One row per calendar month:

```text
month, SR, D0, D1, D2, D3, D4, D5, D6, D7, D8
```

`SR` is the registry-confirmed ischemic stroke count. Definitions that are not evaluable because a required structured feature is unavailable should be `NA`, not zero.
