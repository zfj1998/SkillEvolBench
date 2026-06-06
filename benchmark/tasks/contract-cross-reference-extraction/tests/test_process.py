from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = (ROOT / "project" / "analyzer.py").read_text(encoding="utf-8")
INDEX = (ROOT / "project" / "clause_index.py").read_text(encoding="utf-8")
PATTERNS = (ROOT / "project" / "reference_patterns.py").read_text(encoding="utf-8")


def test_process_uses_graph_representation():
    assert "build_graph" in ANALYZER
    assert "defaultdict" in ANALYZER or "graph = {}" in ANALYZER


def test_process_has_clause_index_and_pattern_modules():
    assert "index_sources" in ANALYZER
    assert "extract_reference_candidates" in ANALYZER
    assert "normalize_node" in INDEX
    assert "SCHEDULE_REF_RE" in PATTERNS


def test_process_has_cycle_detection_algorithm():
    text = ANALYZER.lower()
    keywords = ["dfs", "visited", "visiting", "stack", "recursion", "topological"]
    assert any(keyword in text for keyword in keywords), (
        "Expected a cycle detection implementation such as DFS or topological analysis"
    )
