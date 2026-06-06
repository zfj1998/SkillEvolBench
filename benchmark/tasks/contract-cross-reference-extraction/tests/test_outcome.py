import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
ANALYZER = PROJECT / "analyzer.py"
CONTRACT = PROJECT / "contract.txt"

EXPECTED_EDGES = {
    ("section:1.1", "schedule:A", "schedule"),
    ("section:1.2", "section:7.2", "section"),
    ("section:2.1", "section:3.2(b)", "section"),
    ("section:2.2", "section:4.3", "section"),
    ("section:3.2(b)", "section:5.1", "section"),
    ("section:4.2", "appendix:I", "appendix"),
    ("section:4.3", "schedule:B", "schedule"),
    ("section:5.1", "section:2.1", "section"),
    ("section:5.2", "section:9.4", "section"),
    ("section:6.2", "section:9.2", "section"),
    ("section:7.2", "appendix:II", "appendix"),
    ("section:8.2", "schedule:C", "schedule"),
    ("section:9.4", "appendix:I", "appendix"),
    ("section:9.4", "schedule:A", "schedule"),
}

PUBLIC_MIN_EDGES = {
    ("section:2.1", "section:3.2(b)"),
    ("section:5.1", "section:2.1"),
}

CYCLE_NODES = {"section:2.1", "section:3.2(b)", "section:5.1"}


def _load_module():
    spec = importlib.util.spec_from_file_location("task_analyzer", ANALYZER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_analysis():
    module = _load_module()
    return module.analyze_contract(str(CONTRACT))


def _edges(result):
    return {
        (ref["source"], ref["target"], ref.get("target_type"))
        for ref in result["references"]
    }


def test_public_has_reference_list_and_fields():
    result = _run_analysis()
    assert "references" in result
    assert isinstance(result["references"], list)
    assert result["references"], "references should not be empty"
    sample = result["references"][0]
    assert "source" in sample and "target" in sample


def test_public_finds_core_cycle_related_edges():
    result = _run_analysis()
    seen = {(ref["source"], ref["target"]) for ref in result["references"]}
    for edge in PUBLIC_MIN_EDGES:
        assert edge in seen


def test_hidden_identifies_all_expected_references():
    result = _run_analysis()
    edges = _edges(result)
    missing = EXPECTED_EDGES - edges
    assert not missing, f"Missing references: {sorted(missing)}"


def test_hidden_reference_objects_have_complete_structure():
    result = _run_analysis()
    for ref in result["references"]:
        assert set(ref).issuperset({"source", "target", "target_type"})
        assert ref["target_type"] in {"section", "appendix", "schedule"}


def test_hidden_references_do_not_contain_duplicate_pairs():
    result = _run_analysis()
    triples = [(ref["source"], ref["target"], ref.get("target_type")) for ref in result["references"]]
    assert len(triples) == len(set(triples)), "duplicate source/target/type references found"


def test_hidden_detects_expected_cycle():
    result = _run_analysis()
    cycles = result.get("cycles", [])
    assert cycles, "Expected at least one cycle"
    normalized = [set(cycle) for cycle in cycles]
    assert any(CYCLE_NODES == nodes for nodes in normalized), cycles


def test_hidden_appendix_and_schedule_refs_classified_correctly():
    result = _run_analysis()
    edges = _edges(result)
    appendix_edges = {edge for edge in edges if edge[2] == "appendix"}
    schedule_edges = {edge for edge in edges if edge[2] == "schedule"}
    assert ("section:4.2", "appendix:I", "appendix") in appendix_edges
    assert ("section:8.2", "schedule:C", "schedule") in schedule_edges


def test_hidden_avoids_false_positive_section_word_mentions():
    result = _run_analysis()
    bad_pairs = {
        ("section:9.3", "section:headers"),
        ("section:8.1", "section:used"),
    }
    seen_pairs = {(ref["source"], ref["target"]) for ref in result["references"]}
    for pair in bad_pairs:
        assert pair not in seen_pairs
