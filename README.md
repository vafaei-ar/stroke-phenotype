# Stroke phenotype benchmarking

Reproducible analysis code for **Benchmarking EHR Stroke Phenotype Definitions: A Temporal Cross-System Comparison**.

The repository implements the rule-based ischemic stroke definitions used in the study, patient-level registry linkage, first-stroke selection, monthly count aggregation, and count-based validation against stroke registry data. Patient-level EHR and registry data are intentionally excluded from Git.

## Analysis contract

The current manuscript analysis follows these rules:

1. The candidate EHR cohort already satisfies the study's ischemic-stroke ICD eligibility criteria and hospitalization criteria.
2. **D0 is the ICD-only baseline**. It is every eligible candidate encounter and has no imaging requirement.
3. D1-D8 add structured neuroimaging, lipid laboratory, and rehabilitation signals to D0.
4. For longitudinal count analyses, each patient contributes only the **first qualifying stroke hospitalization** in the analytic period.
5. Center 1 registry linkage uses the encounter identifier shared with the registry (FIN in the source data). Precision is equivalent to positive predictive value.
6. The registry reference cohort is restricted to **Primary ischemic stroke** when those fields are available.
7. Monthly count validation reports MAE, normalized MAE, and Pearson correlation. MAE is in **encounters per month**, not percent disagreement.
8. A definition that cannot be evaluated because a required structured feature is unavailable at a center must be reported as **not evaluable**, not as zero cases.

See [`docs/analysis_contract.md`](docs/analysis_contract.md) for details.

## Phenotype definitions

| Definition | Additional criteria after ICD eligibility |
|---|---|
| D0 | none |
| D1 | CT or MRI AND lipid testing |
| D2 | CT or MRI AND (lipid testing OR rehabilitation) |
| D3 | MRI AND lipid testing |
| D4 | MRI AND (lipid testing OR rehabilitation) |
| D5 | CT or MRI |
| D6 | MRI AND lipid testing AND rehabilitation |
| D7 | MRI |
| D8 | CT AND lipid testing |

`D9` is included as an **exploratory reviewer-requested definition**: CT or MRI AND lipid testing AND rehabilitation. It is not part of the original D0-D8 set.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Local data

Copy `config/centers.example.yaml` to `config/centers.local.yaml`, then place protected data under `data/`. The local config and everything under `data/` are ignored by Git.

The core patient-level feature table has one row per eligible EHR encounter with:

```text
patient_id, encounter_id, admit_date, ct, mri, lipid, rehab
```

Monthly count files use:

```text
month, SR, D0, D1, ..., D8
```

where `SR` is the monthly registry count.

## First reproduce the current Center 1 manuscript pipeline

Before refactoring raw EHR extraction, use the protected historical intermediate `outcomes/df_phen_details.csv` to verify that the canonical implementation reproduces the manuscript results:

```bash
python scripts/01_import_legacy_center1_features.py \
  --input ../outcomes/df_phen_details.csv \
  --out data/processed/center1_features.csv \
  --facility-contains '<LOCAL FACILITY SUBSTRING>'

python scripts/03_build_monthly_counts.py \
  --features data/processed/center1_features.csv \
  --out data/processed/center1_definition_counts.csv
```

The facility value is local protected configuration and should not be committed. See [`docs/legacy_provenance.md`](docs/legacy_provenance.md).

## Reproduce the manuscript analyses

```bash
python scripts/02_run_linked_validation.py \
  --ehr data/processed/center1_features.parquet \
  --registry data/processed/center1_registry.parquet \
  --out outputs/center1_linked_precision.csv

python scripts/03_build_monthly_counts.py \
  --features data/processed/center1_features.parquet \
  --out data/processed/center1_definition_counts.csv

python scripts/04_run_multicenter_validation.py \
  --config config/centers.local.yaml \
  --out outputs/count_metrics_all_definitions.csv

python scripts/05_generate_manuscript_tables.py \
  --linked outputs/center1_linked_precision.csv \
  --count outputs/count_metrics_all_definitions.csv \
  --outdir outputs/manuscript
```

## Privacy

Do not commit patient identifiers, encounter identifiers, patient-level dates, local source paths, or center-name mappings. The public repository uses only generic Center 1-Center 4 labels and aggregate manuscript benchmark values.
