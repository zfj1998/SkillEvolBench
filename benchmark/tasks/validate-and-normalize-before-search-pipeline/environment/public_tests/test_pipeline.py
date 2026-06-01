from pathlib import Path

from pipeline import run_pipeline


def test_pipeline_returns_summary():
    result = run_pipeline(Path(__file__).resolve().parents[1] / "query.txt")
    assert result["count"] == 3


def test_pipeline_returns_rows():
    result = run_pipeline(Path(__file__).resolve().parents[1] / "query.txt")
    assert result["rows"]
