from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = (ROOT / 'project' / 'analyzer.py').read_text()
READER = (ROOT / 'project' / 'invoice_reader.py').read_text()
POLICY = (ROOT / 'project' / 'pricing_policy.py').read_text()


def test_process_uses_reader_and_policy_modules():
    assert 'invoice_reader' in ANALYZER
    assert 'pricing_policy' in ANALYZER


def test_process_currency_field_preserved():
    assert 'currency' in ANALYZER or 'currency' in READER, 'solution should preserve per-line currency in output'
    assert 'currency_code' not in ANALYZER, 'expected the serializer to use the extracted currency key directly'


def test_process_discount_condition_field_present():
    assert 'condition' in ANALYZER and 'DISCOUNT_CONDITION' in POLICY
    assert 'strict=true' in ANALYZER.lower(), 'expected the strict > $1000 threshold to be used'


def test_process_cross_page_continuity_logic():
    assert 'index' in READER and 'rows.append' in READER


def test_process_tax_base_uses_discount_helper():
    assert 'tax_base_after_discount' in ANALYZER
