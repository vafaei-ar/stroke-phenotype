# Length-of-stay audit

The manuscript states that eligible hospitalizations lasted more than 24 hours. The historical Center 1 preparation notebook did not implement that criterion as an exact elapsed-time comparison. During construction of its intermediate dictionaries, it removed encounters occurring on the same calendar day, and the later feature-building step could reintroduce broader encounter records for patients who remained in the eligible patient set.

Before replacing the legacy extraction code, run `scripts/00_audit_legacy_length_of_stay.py` against the protected historical intermediates. The script reproduces the historical first-event and Center 1 facility-selection order, joins the selected encounters back to the legacy encounter dictionary, and reports only aggregate counts comparing:

- the historical non-same-calendar-day rule;
- exact length of stay greater than 24 hours;
- exact length of stay equal to 24 hours;
- exact length of stay less than 24 hours.

No patient or encounter identifiers are printed or written.

The purpose is to determine whether the manuscript wording (>24 hours) accurately describes the cohort that generated the published/revision-stage results, or whether either the analysis or the Methods wording needs a small correction before the raw-EHR extraction is refactored.
