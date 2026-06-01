from pathlib import Path

from batch_import import import_batch


def test_response_has_summary():
    result = import_batch(Path(__file__).resolve().parents[1] / "employees.json")
    assert "summary" in result


def test_failures_are_returned():
    result = import_batch(Path(__file__).resolve().parents[1] / "employees.json")
    assert "failures" in result
