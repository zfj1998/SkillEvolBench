import csv, json
from pathlib import Path
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'project'
CSV_PATH = ROOT/'project'/'filled_erp.csv'
REPORT_PATH = ROOT/'project'/'pipeline_report.json'
@pytest.fixture(scope='module')
def rows():
    if CSV_PATH.exists():
        CSV_PATH.unlink()
    if REPORT_PATH.exists():
        REPORT_PATH.unlink()
    subprocess.run(['bash', str(PROJECT / 'run_analysis.sh')], check=True, cwd=PROJECT)
    assert CSV_PATH.exists(), 'filled_erp.csv missing after running run_analysis.sh'
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        return list(csv.reader(f))
@pytest.fixture(scope='module')
def report():
    return json.loads(REPORT_PATH.read_text())
def test_hidden_csv_exists_and_has_format(rows):
    assert len(rows) >= 2
def test_hidden_csv_row_count_matches_pdf_items(rows):
    assert len(rows)-1 == 3
def test_hidden_csv_sum_matches_pdf_total(rows, report):
    total = sum(float(r[4]) for r in rows[1:])
    assert abs(total - report['pdf_total']) <= 0.01
def test_hidden_dates_are_normalized(rows):
    dates = [r[1] for r in rows[1:]]
    assert all(len(d) == 10 and d[4] == '-' and d[7] == '-' for d in dates)
def test_hidden_column_order_matches_template(rows):
    assert rows[0] == ['invoice_id','invoice_date','customer','item_description','amount']


def test_hidden_report_marks_normalization_complete(report):
    assert report['normalized'] is True


def test_hidden_report_retains_normalized_invoice_date(report):
    assert report['invoice_date'] == '2026-04-13'
