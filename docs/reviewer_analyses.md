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

If the protected registry-linked input is available in canonical schema, run:

```bash
python scripts/02_run_linked_validation.py \
  --ehr data/processed/center1_features_from_raw.csv \
  --registry <LOCAL CENTER 1 REGISTRY FILE> \
  --out outputs/center1_linked_precision_reviewer.csv \
  --include-exploratory
```

The registry reference should be restricted to Primary ischemic stroke when
those fields are available, consistent with the analysis contract.

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
