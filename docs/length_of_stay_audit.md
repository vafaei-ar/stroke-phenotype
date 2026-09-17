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

## Interpretation

The manuscript phrase `>24 hours` is not an exact description of the historical Center 1 cohort-generation code. This does not by itself establish that the manuscript analysis should be rerun with an exact >24-hour restriction. Before changing either the analysis or the Methods wording, quantify how applying an exact >24-hour rule changes D0-D8 totals, monthly counts, and the manuscript validation metrics. Preserve the historical 6,582-row cohort as the regression target unless a deliberate analytic change is made.
