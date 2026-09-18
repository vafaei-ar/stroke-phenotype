# Analysis contract

This document records analysis choices that were previously distributed across multiple notebooks. The goal is to make the manuscript results reproducible and prevent silent divergence between notebooks.

## Candidate cohort

D0-D8 are evaluated only after the broad candidate ischemic stroke cohort has been constructed using the study ICD criteria and hospitalization rules. The analysis package therefore treats every row in the supplied patient-level feature table as D0-eligible.

## D0

D0 is explicitly the ICD-only baseline. Historical notebooks encoded D0 using a tautological comparison on an MRI-derived boolean column. Although that expression behaved as an all-row mask when the column contained only boolean values, it obscured the intended definition. The canonical implementation uses an explicit all-True mask and has no imaging dependency.

## First qualifying stroke event

For count-based analyses, patients are sorted by admission date and only the first qualifying stroke hospitalization in the analytic period is retained. Recurrent qualifying admissions are therefore not counted as additional index events.

## Linked validation at Center 1

The source analysis links EHR and registry records using the shared encounter identifier (FIN in the local source system), then evaluates the retained first qualifying event. Precision is calculated as:

```text
matched definition-positive encounters / all definition-positive encounters
```

This quantity is equivalent to positive predictive value (PPV).

## Registry reference cohort

When registry diagnostic fields are available, the reference cohort is restricted to `Diagnosis = Primary` and `Type = Ischemic`.

## Count-based validation

For each center and definition, monthly phenotype counts are compared with monthly registry counts.

- `MAE = mean(abs(definition_count - registry_count))`
- `nMAE = MAE / mean(registry_count)`
- `Pearson r` measures temporal concordance across months.

An MAE of 8 means that the phenotype-derived monthly count differs from the registry count by 8 encounters per month on average. It does not mean 8% disagreement.

## Missing feature availability

A phenotype that requires a feature not captured at a center is **not evaluable** at that center. It must not be converted to an all-zero series. This distinction is particularly important for definitions that require rehabilitation.

## Original and exploratory definitions

D0-D8 reproduce the original manuscript candidate set. D9, `(CT OR MRI) AND lipid AND rehabilitation`, is provided as a reviewer-requested exploratory extension. D9 should be reported separately from the original definition set unless the manuscript is explicitly revised to incorporate it.

## Site identity

The public repository intentionally does not map Center 1-Center 4 labels to institution names. Any mapping belongs in `config/centers.local.yaml`, which is ignored by Git.
