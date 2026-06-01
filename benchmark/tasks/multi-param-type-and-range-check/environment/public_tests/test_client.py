from pathlib import Path

from client import process_requests


def test_only_valid_requests_are_sent():
    result = process_requests(Path(__file__).resolve().parents[1] / "requests.json")
    assert len(result["successes"]) == 4


def test_failures_are_reported():
    result = process_requests(Path(__file__).resolve().parents[1] / "requests.json")
    assert result["failures"]
    assert "param" in result["failures"][0]["errors"][0]
