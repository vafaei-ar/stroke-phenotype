# Reference files

This directory contains non-patient-level reference material used by the reproducible analysis.

## Aggregate manuscript regression values

The existing aggregate CSVs contain only values reported in the manuscript and are used as regression checks when the local protected-data pipeline is rerun.

They are **not ground truth for future revisions**. If the canonical analysis is intentionally changed after reviewer-requested analyses, update them only after the change is reviewed and documented.

## Historical feature code lists

The historical Center 1 extraction used a 214-row lipid/cholesterol LOINC file with columns `LOINC_NUM` and `COMPONENT`. Two located copies were byte-identical. Their SHA-256 was:

`89524fe32e4f08d4e297873d8a48dbb9ebafcf56d9bcd0b42f8217f14444747a`

The located `Physical_Rehab.csv` contains 65 rows with columns `CPT Code` and `Description`; its SHA-256 was:

`c85255d34eff3cb2f8dcfabea56e8a37906d54b779f8ead661d577b879ee4854`

The manuscript-generating notebook, however, used a hard-coded rehabilitation list containing 78 entries because CPT codes 97161-97172 appeared twice. After deduplication, that notebook list contains 66 unique CPT codes. The reference audit identified the one-code difference exactly: `97156` is present in the notebook rule and absent from the 65-row `Physical_Rehab.csv`. Therefore exact legacy reproduction uses the notebook-derived 66-code rule; the CSV is retained only as a reference/audit source.

Use `scripts/00_prepare_reference_codes.py` to validate the located source files and write standardized local code-list copies:

```bash
python scripts/00_prepare_reference_codes.py \
  --lipid ../lipid_corrected_by_harold.csv \
  --rehab ../phenotype/Physical_Rehab.csv \
  --out-dir reference
```

The generated files are:

- `reference/lipid_loinc.csv` with columns `loinc_code,component`;
- `reference/rehab_cpt.csv` with columns `cpt_code,description`.

For exact legacy reproduction, `src/stroke_phenotype/codes.py` uses the 66 unique rehabilitation CPT codes traced directly from the historical notebook. The raw preparation command compares those codes with `reference/rehab_cpt.csv` and reports the missing `97156` without changing the historical rule. Using that notebook-derived rehabilitation rule, the raw-data refactor reproduced the historical D0-D8 monthly counts exactly.

The preparation script reads codes as strings, validates the source hashes, columns, and row counts, and does not access patient-level data.
