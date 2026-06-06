from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ANALYZER = (ROOT/'project'/'analyzer.py').read_text().lower()
NORMALIZER = (ROOT/'project'/'date_normalizer.py').read_text().lower()
WRITER = (ROOT/'project'/'erp_writer.py').read_text().lower()
CHECK = (ROOT/'project'/'consistency_check.py').read_text().lower()
def test_process_four_step_pipeline_exists():
    assert 'def extract' in ANALYZER and 'normalize_invoice_date' in ANALYZER and 'write_rows' in ANALYZER and 'validat' in ANALYZER
def test_process_consistency_validation_exists():
    assert 'totals_match' in ANALYZER or 'sum(' in CHECK
def test_process_erp_contract_modules_exist():
    assert 'yyyy-mm-dd' not in NORMALIZER or 'normalize' in NORMALIZER
    assert 'invoice_date' in WRITER and 'item_description' in WRITER


def test_process_marks_normalized_stage_in_report():
    assert "'normalized': true" in ANALYZER or '"normalized": true' in ANALYZER
