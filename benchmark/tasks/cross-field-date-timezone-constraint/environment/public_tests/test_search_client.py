from pathlib import Path

from search_client import process_queries


def test_obviously_invalid_query_is_rejected():
    result = process_queries(Path(__file__).resolve().parents[1] / "queries.json")
    assert result["rejected"]


def test_valid_queries_are_sent():
    result = process_queries(Path(__file__).resolve().parents[1] / "queries.json")
    assert result["accepted"]
