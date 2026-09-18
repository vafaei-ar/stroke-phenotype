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

The strict sensitivity treated exact LOS >24 hours as a true eligibility criterion before first-event selection. This allowed a later encounter to become the first qualifying event when an earlier historical encounter was shorter than 24 hours.

The baseline reconstruction exactly matched the historical monthly D0-D8 count table. Applying exact LOS >24 hours changed the Center 1 cohort from 6,582 to 6,534 patients, a net reduction of 48 patients (0.73%). Definition totals changed as follows:

| Definition | Historical total | Strict >24 h | Change | Percent change |
| --- | ---: | ---: | ---: | ---: |
| D0 | 6,582 | 6,534 | -48 | -0.73% |
| D1 | 4,953 | 4,929 | -24 | -0.48% |
| D2 | 5,872 | 5,849 | -23 | -0.39% |
| D3 | 4,320 | 4,302 | -18 | -0.42% |
| D4 | 4,821 | 4,803 | -18 | -0.37% |
| D5 | 6,192 | 6,152 | -40 | -0.65% |
| D6 | 3,388 | 3,378 | -10 | -0.30% |
| D7 | 5,016 | 4,996 | -20 | -0.40% |
| D8 | 4,189 | 4,169 | -20 | -0.48% |

Monthly changes were small: the largest absolute monthly difference was 3 patients for D0 and D5, 2 patients for D1-D4, D7, and D8, and 1 patient for D6.

Count-based validation metrics were also minimally affected. The largest MAE change was D0, 30.45 to 30.02 (-0.42). The largest nMAE change was D0, 0.647 to 0.638 (-0.009). The largest Pearson-correlation change was D0, 0.425 to 0.416 (-0.009). D1 and D3, the two definitions emphasized in the manuscript count-based comparison, changed only slightly: D1 MAE 12.58 to 12.39 and r 0.642 to 0.642; D3 MAE 8.14 to 8.05 and r 0.588 to 0.590.

## Working interpretation

The exact >24-hour sensitivity produces no material change in the scientific conclusions of the Center 1 count-based validation. The historical 6,582-row cohort should therefore remain the regression target for reproducibility. Replacing the main analysis with the strict >24-hour sensitivity would create a new analysis rather than reproduce the one that generated the manuscript results.

The remaining manuscript task is to make the eligibility wording accurately describe the operational cohort rule. Before finalizing that wording, confirm whether Centers 2-4 implemented an exact elapsed >24-hour threshold or another local operational rule. If their implementations differ, the Methods should describe the common intent and site-specific operationalization rather than state a universal exact >24-hour rule.

The strict >24-hour result should remain documented as a sensitivity analysis rather than replace the historical primary analysis unless the study team deliberately chooses to redefine eligibility across all centers.
