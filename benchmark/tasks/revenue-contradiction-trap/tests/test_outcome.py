import json
from pathlib import Path
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'project'
OUT = ROOT/'output.json'
@pytest.fixture(scope='module')
def data():
    if OUT.exists():
        OUT.unlink()
    subprocess.run(['bash', str(PROJECT / 'run_analysis.sh')], check=True, cwd=PROJECT)
    assert OUT.exists(), 'output.json not found after running run_analysis.sh'
    return json.loads(OUT.read_text())
def test_public_has_revenue_value(data):
    assert 'annual_revenue' in data or 'revenues' in data
def test_hidden_contains_both_values(data):
    assert 'revenues' in data and len(data['revenues']) == 2
    values = sorted(round(x['value']) for x in data['revenues'])
    assert values == [2300000, 2500000]
def test_hidden_contains_sources(data):
    for x in data['revenues']:
        assert x.get('source')
def test_hidden_conflict_marker(data):
    lowered = json.dumps(data).lower()
    assert 'conflict' in lowered or 'discrepancy' in lowered
def test_hidden_no_single_corrected_value(data):
    lowered = json.dumps(data).lower()
    assert 'corrected revenue' not in lowered
    if 'annual_revenue' in data:
        assert 'conflict' in lowered or 'discrepancy' in lowered
