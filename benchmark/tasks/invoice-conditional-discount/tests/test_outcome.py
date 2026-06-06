import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'project'
OUTPUT = ROOT / 'output.json'


def run_extractor():
    if OUTPUT.exists():
        OUTPUT.unlink()
    subprocess.run(['bash', str(PROJECT / 'run_analysis.sh')], check=True, cwd=PROJECT)
    assert OUTPUT.exists(), 'output.json was not created'
    return json.loads(OUTPUT.read_text())


def approx(a, b, tol=1e-2):
    return abs(a - b) <= tol


def get_invoices(data):
    assert 'invoices' in data and isinstance(data['invoices'], list), 'top-level invoices list missing'
    by_id = {inv['invoice_number']: inv for inv in data['invoices']}
    assert 'INV-1001' in by_id and 'INV-1002' in by_id, 'both invoices must be present'
    return by_id


def test_public_line_items_len_20():
    inv = get_invoices(run_extractor())['INV-1001']
    assert len(inv['line_items']) == 20


def test_public_subtotal_1250():
    inv = get_invoices(run_extractor())['INV-1001']
    assert approx(inv['subtotal'], 1250.00)


def test_public_schema_basic():
    inv = get_invoices(run_extractor())['INV-1001']
    assert isinstance(inv['line_items'], list)
    assert 'discount' in inv and 'tax' in inv and 'total' in inv


def test_hidden_page2_items_15_to_20_present():
    inv = get_invoices(run_extractor())['INV-1001']
    idxs = [x['index'] for x in inv['line_items']]
    assert idxs[-6:] == [15, 16, 17, 18, 19, 20]


def test_hidden_discount_applied_amount():
    inv = get_invoices(run_extractor())['INV-1001']
    assert approx(inv['discount']['amount'], 62.50)
    assert inv['discount']['applied'] is True


def test_hidden_boundary_invoice_discount_false():
    inv = get_invoices(run_extractor())['INV-1002']
    assert inv['discount']['applied'] is False


def test_hidden_tax_base_post_discount():
    inv = get_invoices(run_extractor())['INV-1001']
    assert approx(inv['tax']['state']['base'], 1187.50)


def test_hidden_currency_present_for_each_item():
    inv = get_invoices(run_extractor())['INV-1001']
    currencies = [x.get('currency') for x in inv['line_items']]
    assert all(c in {'USD', 'EUR', 'JPY'} for c in currencies)
    assert currencies[14] == 'USD' and currencies[15] == 'EUR' and currencies[-1] == 'JPY'


def test_hidden_no_header_footer_pollution():
    inv = get_invoices(run_extractor())['INV-1001']
    descriptions = ' '.join(x['description'] for x in inv['line_items'])
    assert 'Thank you for your business' not in descriptions
    assert 'Page 1 of 2' not in descriptions
    assert 'ACME SUPPLY CO.' not in descriptions


def test_hidden_total_consistency():
    inv = get_invoices(run_extractor())['INV-1001']
    tax_sum = inv['tax']['state']['amount'] + inv['tax']['federal']['amount']
    expected = inv['subtotal'] - inv['discount']['amount'] + tax_sum
    assert approx(inv['total'], expected)
