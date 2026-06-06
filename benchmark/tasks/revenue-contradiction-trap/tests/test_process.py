from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ANALYZER = (ROOT/'project'/'analyzer.py').read_text().lower()
POLICY = (ROOT/'project'/'conflict_policy.py').read_text().lower()
SOURCES = (ROOT/'project'/'revenue_sources.py').read_text().lower()
def test_process_multiple_revenues_or_conflict_logic_exists():
    assert 'conflict' in POLICY or 'evidence' in ANALYZER or 'revenues' in POLICY
def test_process_no_average_logic():
    assert 'average' not in ANALYZER
    assert '/ 2' not in ANALYZER and '/2' not in ANALYZER
def test_process_extracts_multiple_sources():
    assert 'executive summary' in SOURCES and 'financial statements' in SOURCES
