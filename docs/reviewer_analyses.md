# Reviewer-requested analyses

This document keeps the reviewer-response analyses separate from the frozen
D0-D8 manuscript reproduction checks.

## Questions addressed

The current revision needs three additional outputs:

1. report normalized MAE (nMAE) alongside raw MAE so count disagreement can be
   interpreted relative to each center's mean monthly registry volume;
2. report external performance for D6 wherever rehabilitation is evaluable,
   rather than dropping the definition after Center 1;
3. evaluate the exploratory D9 definition requested during review:
   `(CT OR MRI) AND lipid AND rehabilitation`.

D9 is exploratory and should remain separate from the original D0-D8 set unless
the manuscript is intentionally revised to make it part of the primary
definition family.

## Metric interpretation

For monthly registry counts `R_t` and phenotype counts `P_t`:

```text
MAE  = mean_t |P_t - R_t|
nMAE = MAE / mean_t(R_t)
```

Thus nMAE = 0.25 means the average absolute monthly count error is 25% of the
center's mean monthly registry volume. nMAE is not MAPE and does not average
month-specific percentage errors.

Pearson `r` measures temporal co-movement. It is not an agreement metric and
should be interpreted separately from MAE/nMAE.

## Center 1 D9 count analysis

The raw Center 1 preparation has already reproduced historical D0-D8 monthly
counts exactly. Rebuild the same monthly table with D9 included:

```bash
python scripts/03_build_monthly_counts.py \
  --features data/processed/center1_features_from_raw.csv \
  --out data/processed/center1_definition_counts_with_d9.csv \
  --include-exploratory

python scripts/03b_attach_registry_counts.py \
  --counts data/processed/center1_definition_counts_with_d9.csv \
  --registry-source ../outcomes/PS_conditions.csv \
  --registry-col SR \
  --out data/processed/center1_monthly_counts_reviewer.csv
```

The first command changes only the definition set, not the underlying Center 1
cohort or feature extraction. The generated phenotype table can extend beyond the
registry observation period. `03b_attach_registry_counts.py` therefore restricts
validation to the months present in the registry reference table, while requiring
a phenotype count for every registry month.

## Center 1 D9 count checkpoint achieved

The reviewer count rerun has now been completed against the same 85-month
registry window used for the historical Center 1 validation. Adding D9 did not
alter any D0-D8 monthly count: the legacy comparison remained an exact match for
all definitions.

The selected Center 1 metrics were:

| Definition | Total | MAE | nMAE | nMAE (%) | Pearson r |
|---|---:|---:|---:|---:|---:|
| D0 | 6,582 | 30.45 | 0.6470 | 64.70 | 0.425 |
| D1 | 4,953 | 12.58 | 0.2673 | 26.73 | 0.642 |
| D3 | 4,320 | 8.14 | 0.1730 | 17.30 | 0.588 |
| D6 | 3,388 | 14.78 | 0.3140 | 31.40 | 0.054 |
| D9 | 3,827 | 18.98 | 0.4033 | 40.33 | 0.049 |

For Center 1, broadening D6 from MRI to CT-or-MRI increased the D9 count by 439
patients, but did not improve count agreement with the registry: MAE increased
from 14.78 to 18.98 encounters/month and Pearson r remained near zero. This
should be described as a Center 1 exploratory result, not generalized to the
external centers before their reruns are available.

The aggregate checkpoint is stored in
`reference/center1_reviewer_count_expected.csv`.

## Center 1 D9 linked analysis

The historical Center 1 linked validation did not compare registry FIN directly
with the EHR encounter identifier. The notebook first merged the registry to
`MRN to PatID_04212025.csv` on FIN, retained mapped PSU PAT_ID values, and then
used those EHR patient identifiers as the registry truth set. The historical
precision calculation compared phenotype-positive PATID sets with that linked
registry PATID set.

The clean script now reproduces that FIN-to-PAT_ID crosswalk explicitly,
preserves identifier columns as strings, and keeps direct encounter linkage only
as a separate non-legacy mode.

Regression audits substantially narrowed the historical linked-validation
configuration. All available registry snapshots produced identical values over
the candidate period. The closest match to the historical linked counts used the
12-month EHR/registry window February 2018 through January 2019 and included all
ischemic registry rows regardless of Primary/Secondary diagnosis role.

That configuration reproduced the historical aggregate counts closely:
registry truth 702 versus 701; D0 positive 921 versus 918 and matched 640 versus
636; D1 positive 721 versus 720 and matched 574 versus 573. By contrast,
restricting the registry to Primary ischemic stroke reduced the linked truth set
to 630 and materially worsened the precision regression.

This creates a provenance discrepancy: the later `new_approach_reg.ipynb`
explicitly filters the registry to Primary ischemic stroke, whereas the
manuscript-era linked precision table is numerically consistent with all ischemic
registry rows. Preserve that distinction in the audit trail rather than silently
forcing the later notebook rule onto the historical precision table.

Run the best-matching historical regression configuration and compare D0-D8
against `reference/center1_precision_expected.csv`:

```bash
python scripts/02_run_linked_validation.py \
  --ehr data/processed/center1_features_from_raw.csv \
  --registry "../reg_inv/Super Universe_Zand 04142025.csv" \
  --registry-conversion "../reg_inv/MRN to PatID_04212025.csv" \
  --registry-fin-col FIN \
  --conversion-fin-col FIN \
  --conversion-patient-col PAT_ID \
  --registry-diagnosis-col Diagnosis \
  --registry-type-col Type \
  --registry-diagnosis-mode any \
  --registry-date-col "Admit Date" \
  --start-date 2018-02-01 \
  --end-date 2019-01-31 \
  --out outputs/center1_linked_precision_reviewer.csv \
  --include-exploratory
```

If D0-D8 reproduce the historical rounded precision values under this
configuration, report the reviewer-requested D9 PPV from the same linked cohort
as an exploratory sensitivity result and retain the small residual count
differences as a provenance limitation.


## Center 2 and Center 3 Geisinger aggregate importer

The legacy Geisinger condition exports are repeated-section pivot tables. Their
section labels map to the manuscript definitions as follows:

| Legacy section | Definition |
|---|---|
| diagnosis | D0 |
| any imaging AND Chol./Lip. | D1 |
| any imaging AND (Chol./Lip. OR Phy./Rehab.) | D2 |
| MRI AND Chol./Lip. | D3 |
| MRI AND (Chol./Lip. OR Phy./Rehab.) | D4 |
| any Imaging | D5 |
| MRI AND Chol./Lip. AND Phy./Rehab. | D6 |
| MRI | D7 |
| CT AND Chol./Lip. | D8 |

The historical effective registry windows are Center 2 from January 2017 through
July 2022 and Center 3 from March 2016 through July 2022. The clean importer
`scripts/04c_import_geisinger_monthly.py` converts the legacy pivot exports into
canonical monthly tables with columns `month, SR, D0-D8` and prints MAE, nMAE,
and Pearson r.

Example local commands:

```bash
python scripts/04c_import_geisinger_monthly.py \
  --conditions ../phenotype/geisinger/GMC_conditions.csv \
  --registry ../phenotype/geisinger/GMC_registery.csv \
  --start 2017-01 \
  --end 2022-07 \
  --out data/processed/center2_monthly_counts.csv

python scripts/04c_import_geisinger_monthly.py \
  --conditions ../phenotype/geisinger/GCMC_conditions.csv \
  --registry ../phenotype/geisinger/GCMC_registery.csv \
  --start 2016-03 \
  --end 2022-07 \
  --out data/processed/center3_monthly_counts.csv
```

The expected historical D6 regression values are MAE 12.54 and r 0.61 for
Center 2, and MAE 7.49 and r 0.50 for Center 3. The clean rerun should reproduce
these before the new nMAE values are used in the revision.

## Center 2 and Center 3 checkpoints achieved

The clean Geisinger importer reproduced the manuscript-era regression values for
both external Geisinger centers.

| Center | Definition | Total | MAE | nMAE | nMAE (%) | Pearson r |
|---|---|---:|---:|---:|---:|---:|
| Center 2 | D0 | 4,166 | 14.01 | 0.2748 | 27.48 | 0.150 |
| Center 2 | D1 | 3,225 | 7.64 | 0.1498 | 14.98 | 0.534 |
| Center 2 | D3 | 2,684 | 11.54 | 0.2262 | 22.62 | 0.574 |
| Center 2 | D6 | 2,589 | 12.54 | 0.2458 | 24.58 | 0.605 |
| Center 3 | D0 | 2,230 | 6.17 | 0.2219 | 22.19 | 0.563 |
| Center 3 | D1 | 2,060 | 5.60 | 0.2013 | 20.13 | 0.588 |
| Center 3 | D3 | 1,734 | 6.84 | 0.2461 | 24.61 | 0.553 |
| Center 3 | D6 | 1,666 | 7.49 | 0.2695 | 26.95 | 0.496 |

The D6 MAE and Pearson-r values reproduce the historical regression targets to
rounding. These reruns establish that D6 is evaluable at Centers 2 and 3 and can
be reported in the revision. The full D0-D8 aggregate checkpoint is stored in
`reference/center23_reviewer_count_expected.csv`.

## External D6 and multicenter nMAE

Update `config/centers.local.yaml` so each center points to its local monthly
table containing `month`, `SR`, and the available D0-D8 columns. For Center 1,
point to `data/processed/center1_monthly_counts_reviewer.csv` so D9 is also
included.

If a center truly lacks a structured feature required by a definition, list that
definition in `unavailable_definitions`. Do not mark D6 unavailable merely
because a historical table shows a blank result; confirm the underlying
rehabilitation feature availability first.

Run:

```bash
python scripts/04_run_multicenter_validation.py \
  --config config/centers.local.yaml \
  --out outputs/count_metrics_reviewer.csv

python scripts/06_generate_reviewer_outputs.py \
  --count outputs/count_metrics_reviewer.csv \
  --linked outputs/center1_linked_precision_reviewer.csv \
  --outdir outputs/reviewer
```

If linked D9 is not yet available, omit the `--linked` argument.

The reviewer generator writes:

- `reviewer_count_metrics_all_definitions.csv`
- `reviewer_d6_external.csv`
- `reviewer_d9_center1_count.csv`
- `reviewer_d9_center1_linked.csv` when linked input is supplied
- `reviewer_core_summary.csv`


## Center 4 selected-window checkpoint achieved

The historical Center 4 aggregate table contains earlier months, but the
manuscript-generating analysis used March 2023 through June 2024. This window
selection is supported by both provenance and numerical reproduction.

Using January 2023 through June 2024 produced D0 total 1,592, MAE 64.83, and
Pearson r 0.528. Restricting to March 2023 through June 2024 produced D0 total
1,491, MAE 68.81, and r 0.292; D1 MAE 21.56 and r 0.200; and D3 MAE 23.69 and
r 0.306. These values reproduce the manuscript reference values to rounding.

Accordingly, the March 2023 through June 2024 interval should be documented as
the usable Center 4 benchmarking period selected after inspection of overlapping
EHR and registry completeness. The manuscript already states that center-specific
periods were restricted to intervals with acceptable completeness. The exact
technical defect in the excluded January-February 2023 data is not reconstructed
here, so the revision should describe this as a data-completeness/quality
restriction rather than invent a more specific cause.

D6 is present in the source aggregate table as all zero, but the historical
analysis explicitly dropped D6 and skipped it in downstream Center 4 evaluation.
Therefore the zero series should not be interpreted as an observed zero-case
phenotype. For reporting, Center 4 D6 remains not evaluable unless the upstream
rehabilitation feature capture can be independently confirmed.

The aggregate checkpoint is stored in
`reference/center4_reviewer_count_expected.csv`.


## Multicenter reviewer count checkpoint achieved

The four-center reviewer count rerun is now complete. The final selected metrics
for D0, D1, D3, D6, and exploratory D9 are stored in
`reference/multicenter_reviewer_core_expected.csv`.

Key reviewer-facing findings are:

- Center 1 D9 was evaluable, but broadening D6 to CT-or-MRI did not improve
  monthly registry agreement: D9 MAE 18.98, nMAE 40.33%, r 0.049 versus D6 MAE
  14.78, nMAE 31.40%, r 0.054.
- D6 was evaluable at Center 2 (MAE 12.54, nMAE 24.58%, r 0.605) and Center 3
  (MAE 7.49, nMAE 26.95%, r 0.496).
- Center 4 used the manuscript-reproducing March 2023 through June 2024 window.
  D6 remained not evaluable there, while D0, D1, and D3 reproduced the historical
  manuscript values to rounding.
- nMAE provides scale-aware interpretation across centers. In particular, the
  large raw Center 4 MAE values correspond to nMAE values of 282.31% for D0,
  88.46% for D1, and 97.18% for D3.

The multicenter count-analysis component of the reviewer response is therefore
complete. The remaining reviewer analysis is the Center 1 linked D9 precision
check against the protected stroke registry.

## Manuscript revision rules after results are available

- Add nMAE to the count-based Methods and manuscript-facing tables.
- Keep MAE in encounters/month because it remains directly interpretable.
- Report D6 for Centers 2 and 3 if evaluable.
- Report Center 4 D6 as not evaluable only if local data confirm that the
  rehabilitation signal is unavailable or not captured.
- Describe D9 as an exploratory reviewer-requested sensitivity definition.
- Do not reinterpret Pearson `r` as agreement.
- Do not change the historical Center 1 cohort solely to enforce exact LOS >24 h
  or age >=18. The provenance audits show that those literal rules were not
  explicitly implemented in the manuscript-generating Center 1 pipeline; any
  Methods revision should describe the implemented analysis accurately.
