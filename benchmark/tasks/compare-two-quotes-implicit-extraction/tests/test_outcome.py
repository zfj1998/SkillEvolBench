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
def test_public_comparison_result_exists(data):
    assert data['comparison']['recommended_supplier'] in {'A','B'}
def test_hidden_both_quotes_extracted(data):
    for key in ['quote_a','quote_b']:
        for field in ['item','qty','unit_price','delivery','warranty']:
            assert field in data[key]
def test_hidden_total_cost_includes_shipping(data):
    assert abs(data['quote_a']['total_cost'] - 1200.0) < 1e-6
    assert abs(data['quote_b']['total_cost'] - 1280.0) < 1e-6
def test_hidden_recommendation_based_on_total_cost(data):
    assert data['comparison']['recommended_supplier'] == 'A'
def test_hidden_mentions_shipping_difference(data):
    comp = json.dumps(data['comparison']).lower()
    assert 'shipping' in comp or 'freight' in comp
