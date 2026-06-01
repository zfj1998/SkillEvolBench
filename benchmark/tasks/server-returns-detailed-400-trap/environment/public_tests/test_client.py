from pathlib import Path

from client import process_requests


def test_valid_requests_succeed():
    result = process_requests(Path(__file__).resolve().parents[1] / "requests.json")
    assert result["successes"]


def test_invalid_requests_are_reported():
    result = process_requests(Path(__file__).resolve().parents[1] / "requests.json")
    assert result["failures"]
