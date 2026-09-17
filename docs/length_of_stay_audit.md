# Length-of-stay audit

The manuscript states that eligible hospitalizations lasted more than 24 hours. The historical Center 1 preparation notebook did not implement that criterion as an exact elapsed-time comparison. During construction of its intermediate dictionaries, it removed encounters occurring on the same calendar day, and the later feature-building step could reintroduce broader encounter records for patients who remained in the eligible patient set.

The aggregate audit was run against the protected historical intermediates using `scripts/00_audit_legacy_length_of_stay.py`. The script reproduced the historical first-event and Center 1 facility-selection order and joined the selected encounters back to the legacy encounter dictionary without printing or writing patient or encounter identifiers.

## Audit result

For the Center 1 D0 analysis cohort over the manuscript analysis window:

- historical D0 rows: 6,582;
- rows with calculable length of stay: 6,582;
- historical non-same-calendar-day rule: 6,581;
- exact elapsed length of stay >24 hours: 6,525;
- exact elapsed length of stay =24 hours: 0;
- exact elapsed length of stay <24 hours: 57;
- historical non-same-day encounters that were not >24 hours: 56;
- >24-hour encounters excluded by the non-same-day rule: 0.

The difference between the manuscript wording and the historical Center 1 implementation therefore affects 57 of 6,582 D0 encounters (0.87%). One of those encounters was same-day and appears in the final historical D0 cohort because the later feature-building step reintroduced a broader encounter record.

## Sensitivity analysis

The same script can now quantify the effect of treating exact LOS >24 hours as a true eligibility criterion before first-event selection. This is important because a patient whose earlier encounter is shorter than 24 hours may have a later encounter that becomes the first qualifying event under the strict rule.

Run locally with the protected legacy intermediates:

```bash
python scripts/00_audit_legacy_length_of_stay.py \
  --features ../outcomes/df_phen_details.csv \
  --legacy-npy ../data_Sep2024.npy \
  --legacy-counts ../outcomes/PS_conditions.csv \
  --facility-contains HMC
```

The sensitivity section reports only aggregate outputs:

- historical versus strict >24-hour cohort size;
- D0-D8 total changes;
- number of months changed and maximum monthly absolute difference for each definition;
- MAE, nMAE, and Pearson correlation before and after the strict rule, using the same registry months.

The script also verifies that the baseline reconstruction still matches the historical monthly D0-D8 count table before interpreting any sensitivity result.

## Interpretation

The manuscript phrase `>24 hours` is not an exact description of the historical Center 1 cohort-generation code. The strict sensitivity analysis should be reviewed before changing either the analysis or the Methods wording. Preserve the historical 6,582-row cohort as the regression target unless a deliberate analytic change is made.
