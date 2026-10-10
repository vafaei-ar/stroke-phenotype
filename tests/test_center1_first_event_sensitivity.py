"""Synthetic-only regression tests for Center 1 sensitivity analysis."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / '07_center1_first_event_sensitivity.py'


def make_inputs(path: Path) -> tuple[Path, Path, Path, Path]:
    path.mkdir(parents=True, exist_ok=True)
    details = path / 'details.csv'
    historical = path / 'historical.csv'
    primary = path / 'primary.csv'
    registry = path / 'registry.csv'
    pd.DataFrame([
        ('A', 'E1', 'other', '2016-11-15', 1, 0, 0, 1, 1, 0),
        ('A', 'E2', 'center1', '2016-12-01', 1, 0, 0, 1, 1, 0),
        ('B', 'E3', 'center1', '2016-12-18', 1, 0, 0, 0, 1, 1),
        ('B', 'E4', 'center1', '2017-01-12', 0, 0, 1, 1, 1, 1),
        ('C', 'E5', 'center1', '2017-01-01', 0, 0, 1, 0, 1, 0),
    ], columns=['PATID','ENCOUNTERID','FACILITYID','ADMIT_DATE','MRI-2',
                'MRI-ENC','CT-2','CT-ENC','lip','phy']).to_csv(details, index=False)
    pd.DataFrame([
        ('2016-12', 1, 1, 1, 1, 1, 1, 1, 1, 1, 0),
        ('2017-01', 1, 1, 1, 1, 0, 0, 1, 0, 0, 1),
        ('2017-02', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ], columns=['month','SR','D0','D1','D2','D3','D4','D5','D6','D7','D8']).to_csv(historical, index=False)
    pd.DataFrame([
        ('A', 'E1', 1), ('A', 'E2', 1), ('B', 'E3', 0),
        ('B', 'E4', 1), ('C', 'E5', 1),
    ], columns=['PATID','ENCOUNTERID','primary_ischemic_dx']).to_csv(primary, index=False)
    pd.DataFrame([
        ('A', 'Ischemic', 'Primary', '2016-12-02'),
        ('B', 'Ischemic', 'Primary', '2016-12-17'),
        ('C', 'Ischemic', 'Primary', '2017-01-01'),
    ], columns=['MRN','Type','Diagnosis','StrokeDate']).to_csv(registry, index=False)
    return details, historical, primary, registry


def run_script(path: Path, *, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    details, historical, primary, registry = make_inputs(path)
    argv = [sys.executable, str(SCRIPT), '--legacy-details', str(details),
            '--historical-monthly', str(historical), '--facility-contains', 'center1',
            '--study-start', '2016-12-01', '--study-end', '2017-02-01',
            '--out-dir', str(path / 'outputs')]
    if extra:
        argv += [arg.replace('$PRIMARY', str(primary)).replace('$REGISTRY', str(registry))
                 for arg in extra]
    return subprocess.run(argv, text=True, capture_output=True, check=False)


def test_facility_filter_order_and_monthly_baseline(tmp_path: Path) -> None:
    run = run_script(tmp_path)
    assert run.returncode == 0, run.stderr
    assert 'EXACT MATCH' in run.stdout
    summary = pd.read_csv(tmp_path/'outputs'/'center1_sensitivity_summary.csv')
    def record(scenario: str, definition: str) -> pd.Series:
        return summary[(summary.scenario == scenario) & (summary.definition == definition)].iloc[0]
    assert record('baseline', 'D0')['total_EHR'] == 2
    assert record('facility_filter_first', 'D0')['total_EHR'] == 3
    assert record('baseline', 'D3')['total_EHR'] == 1
    assert record('facility_filter_first', 'D3')['total_EHR'] == 2


def test_optional_primary_and_lookback_scenarios(tmp_path: Path) -> None:
    run = run_script(tmp_path, extra=[
        '--primary-map', '$PRIMARY', '--registry-events', '$REGISTRY',
        '--lookback-start', '2016-12-01',
    ])
    assert run.returncode == 0, run.stderr
    summary = pd.read_csv(tmp_path/'outputs'/'center1_sensitivity_summary.csv')
    assert summary.scenario.nunique() == 6
    assert summary[(summary.scenario == 'aligned_observed_lookback') &
                   (summary.definition == 'D0')].iloc[0]['total_registry'] == 3


def test_mismatched_baseline_stops_without_writing_outputs(tmp_path: Path) -> None:
    details, historical, _, _ = make_inputs(tmp_path)
    frozen = pd.read_csv(historical)
    frozen.loc[0, 'D0'] = 2
    frozen.to_csv(historical, index=False)
    argv = [sys.executable, str(SCRIPT), '--legacy-details', str(details),
            '--historical-monthly', str(historical), '--facility-contains', 'center1',
            '--study-start', '2016-12-01', '--study-end', '2017-02-01',
            '--out-dir', str(tmp_path / 'outputs')]
    run = subprocess.run(argv, text=True, capture_output=True, check=False)
    assert run.returncode != 0
    assert 'NOT reproduced' in run.stderr
    assert not (tmp_path / 'outputs' / 'center1_sensitivity_summary.csv').exists()


def test_reference_features_facility_selection(tmp_path: Path) -> None:
    details, historical, _, _ = make_inputs(tmp_path)
    reference = tmp_path / 'center1_features_from_raw.csv'
    pd.DataFrame({'facility_id': ['center1', 'CENTER1']}).to_csv(reference, index=False)
    argv = [sys.executable, str(SCRIPT), '--legacy-details', str(details),
            '--historical-monthly', str(historical),
            '--facility-from-features', str(reference),
            '--study-start', '2016-12-01', '--study-end', '2017-02-01',
            '--out-dir', str(tmp_path / 'outputs')]
    run = subprocess.run(argv, text=True, capture_output=True, check=False)
    assert run.returncode == 0, run.stderr
    summary = pd.read_csv(tmp_path / 'outputs' / 'center1_sensitivity_summary.csv')
    orig = summary[(summary.scenario == 'baseline') & (summary.definition == 'D0')].iloc[0]
    alt = summary[(summary.scenario == 'facility_filter_first') & (summary.definition == 'D0')].iloc[0]
    assert orig.total_EHR == 2
    assert alt.total_EHR == 3


def test_wrong_reference_facility_is_rejected(tmp_path: Path) -> None:
    details, historical, _, _ = make_inputs(tmp_path)
    reference = tmp_path / 'wrong_features.csv'
    pd.DataFrame({'facility_id': ['other']}).to_csv(reference, index=False)
    argv = [sys.executable, str(SCRIPT), '--legacy-details', str(details),
            '--historical-monthly', str(historical),
            '--facility-from-features', str(reference),
            '--study-start', '2016-12-01', '--study-end', '2017-02-01',
            '--out-dir', str(tmp_path / 'outputs')]
    run = subprocess.run(argv, text=True, capture_output=True, check=False)
    assert run.returncode != 0
    assert 'NOT reproduced' in run.stderr or 'matched no' in run.stderr
    assert not (tmp_path / 'outputs' / 'center1_sensitivity_summary.csv').exists()
