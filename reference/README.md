# Reference files

This directory contains non-patient-level reference material used by the reproducible analysis.

## Aggregate manuscript regression values

The existing aggregate CSVs contain only values reported in the manuscript and are used as regression checks when the local protected-data pipeline is rerun.

They are **not ground truth for future revisions**. If the canonical analysis is intentionally changed after reviewer-requested analyses, update them only after the change is reviewed and documented.

## Historical feature code lists

The historical Center 1 extraction used two local, code-only reference CSVs:

- lipid laboratory codes: 214 rows with columns `LOINC_NUM` and `COMPONENT`;
- rehabilitation procedure codes: 65 rows with columns `CPT Code` and `Description`.

The two located lipid CSV copies were byte-identical. Their SHA-256 was:

`89524fe32e4f08d4e297873d8a48dbb9ebafcf56d9bcd0b42f8217f14444747a`

The rehabilitation CSV SHA-256 was:

`c85255d34eff3cb2f8dcfabea56e8a37906d54b779f8ead661d577b879ee4854`

Use `scripts/00_prepare_reference_codes.py` to validate those exact historical files and write standardized public code lists:

```bash
python scripts/00_prepare_reference_codes.py \
  --lipid ../lipid_corrected_by_harold.csv \
  --rehab ../phenotype/Physical_Rehab.csv \
  --out-dir reference
```

The generated files are:

- `reference/lipid_loinc.csv` with columns `loinc_code,component`;
- `reference/rehab_cpt.csv` with columns `cpt_code,description`.

The preparation script reads all codes as strings, validates the source hashes, columns, and row counts, and does not access patient-level data.
