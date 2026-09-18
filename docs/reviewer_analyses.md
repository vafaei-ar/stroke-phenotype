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
cohort or feature extraction.

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
