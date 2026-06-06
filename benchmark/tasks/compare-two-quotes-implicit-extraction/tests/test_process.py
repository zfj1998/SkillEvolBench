from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ANALYZER = (ROOT/'project'/'analyzer.py').read_text().lower()
PARSER = (ROOT/'project'/'quote_parser.py').read_text().lower()
POLICY = (ROOT/'project'/'charge_policy.py').read_text().lower()
def test_process_both_pdfs_are_parsed():
    assert 'supplier_a_quote.pdf' in ANALYZER and 'supplier_b_quote.pdf' in ANALYZER
def test_process_total_cost_or_shipping_calculation_exists():
    assert 'shipping' in PARSER and 'total_cost' in ANALYZER and 'quoted_total' in POLICY


def test_process_compare_uses_total_cost_not_visible_quote_only():
    compare_block = ANALYZER.split('def compare', 1)[1]
    assert 'total_cost' in compare_block
    assert 'quoted_total' not in compare_block


def test_process_basis_mentions_shipping_or_freight():
    assert 'shipping' in ANALYZER or 'freight' in ANALYZER
