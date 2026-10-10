# Center 1 first-event sensitivity analysis

This optional local analysis tests whether Center 1's monthly D0-D8 phenotype rankings depend on the order of selecting a patient's first retained stroke encounter and applying the Center 1 facility filter. It also supports two additional sensitivity questions when the corresponding protected inputs have been verified: ICD diagnosis position and shared observed lookback.

**Status:** Code prepared and tested with synthetic data. The scientific sensitivity results have **not** been calculated using the protected Center 1 data. Do not cite these scenarios as results until the baseline regression check passes locally and the analysis is reviewed.

## Inputs and privacy

Run inside the protected Center 1 environment. Neither inputs nor patient-level intermediate outputs should be committed or uploaded to GitHub.

Required:

- `outcomes/df_phen_details.csv` **before** first-event deduplication, with columns `PATID`, `ENCOUNTERID`, `FACILITYID`, `ADMIT_DATE`, `MRI-2`, `MRI-ENC`, `CT-2`, `CT-ENC`, `lip`, `phy`. The existing raw-source reconstruction can recreate this table using `scripts/01_prepare_center1_features.py --legacy-details-out ...`. Do **not** provide the already deduplicated `center1_features.csv`.
- `outcomes/PS_conditions.csv` with a month/date column, `SR` and `D0`-`D8` for December 2016 to December 2023.
- The **local** Center 1 facility substring used in the original count-generation script. The exact value must remain outside Git.

Optional:

- `--primary-map <file>`: a protected encounter-level CSV with `PATID`, `ENCOUNTERID`, `primary_ischemic_dx` (`1` or `0`). Create this mapping from the original diagnosis table and its primary-diagnosis-position field using the study's stroke diagnosis code lists; the historical phenotype detail table by itself does not contain diagnosis position. A missing/unknown flag must **not** be silently treated as negative.
- `--registry-events <file> --registry-date-column <column> --lookback-start YYYY-MM-DD`: protected rows containing `MRN`, `Type`, `Diagnosis`, and the **date used to define the registry monthly admission counts**. Choose the shared source-coverage starting date only after confirming source availability; it must be no later than December 2016 for the full-window analysis. The default `StrokeDate` is a placeholder; **supply the actual registry date column** (usually the admission date) if different.

## Run the priority analysis

From the `reproducible-analysis-pipeline` repository checkout:

```bash
python scripts/07_center1_first_event_sensitivity.py \
  --legacy-details ../outcomes/df_phen_details.csv \
  --historical-monthly ../outcomes/PS_conditions.csv \
  --facility-contains '<LOCAL CENTER 1 FACILITY SUBSTRING>' \
  --out-dir outputs/center1_first_event_sensitivity
```

The script will stop with an error if (1) the stored 85-month reference totals differ from the manuscript or (2) the reconstructed monthly D0-D8 baseline differs **in any month** from the historical file. The verified full-period checkpoints are D0 6,582, D1 4,953, D3 4,320, and SR 4,000 (the script also checks the other D0-D8 totals). Do not interpret or circulate results if this check fails.

Then, if the optional local files are prepared:

```bash
python scripts/07_center1_first_event_sensitivity.py \
  --legacy-details ../outcomes/df_phen_details.csv \
  --historical-monthly ../outcomes/PS_conditions.csv \
  --facility-contains '<LOCAL CENTER 1 FACILITY SUBSTRING>' \
  --primary-map /secure/primary_ischemic_encounter_map.csv \
  --registry-events /secure/registry_events.csv \
  --registry-date-column '<VERIFIED REGISTRY ADMISSION DATE COLUMN>' \
  --lookback-start YYYY-MM-DD \
  --out-dir outputs/center1_first_event_sensitivity
```

## Scenarios

| Scenario | EHR first-event selection | Registry benchmark |
|---|---|---|
| `baseline` | First observed stroke encounter across the source pathway, **then** Center 1 facility filter (historical behavior) | Frozen `SR` |
| `facility_filter_first` | Center 1 facility filter **before** first observed encounter per person | Frozen `SR` |
| `primary_diagnosis_only` (optional) | Primary ischemic diagnosis restriction before first-event selection, then facility filter | Frozen `SR` |
| `facility_first_and_primary` (optional) | Facility and primary-diagnosis restrictions before first-event selection | Frozen `SR` |
| `aligned_observed_lookback` (optional) | Exclude pre-start EHR events before selecting first retained event | Registry first primary ischemic stroke event since same validated start |
| `aligned_lookback_and_facility_first` (optional) | Apply shared start and facility restriction before first-event selection | Same reconstructed registry series |

For each scenario, the script writes **only aggregate outputs** to `outputs/center1_first_event_sensitivity/` (ignored by Git):

- `center1_sensitivity_summary.csv`: mean monthly absolute error (MAE), normalized MAE, mean signed error, Pearson r, total counts, MAE rankings and nMAE change from baseline.
- `center1_sensitivity_monthly.csv`: per-month D0-D8 and reference counts for audit.

Compare the full D0-D8 rankings, particularly whether D3 remains Center 1's lowest-nMAE/MAE definition. If rankings change, evaluate how that affects the manuscript's cross-center conclusions. The alternate rules represent **different cohort estimands** and do not automatically establish that the original implementation was incorrect. First-observed encounters cannot be interpreted as first-ever incident strokes without sufficient lookback. These checks do not constitute patient-level sensitivity or specificity estimation.

## Local tests

```bash
pip install -e '.[dev]'
pytest tests/test_center1_first_event_sensitivity.py -q
```

These synthetic tests check code behavior, **not** the real-world sensitivity findings.
