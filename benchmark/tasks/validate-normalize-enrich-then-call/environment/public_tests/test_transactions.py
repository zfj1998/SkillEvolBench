from pathlib import Path

from transactions import process_transactions


def test_transactions_are_sent():
    result = process_transactions(Path(__file__).resolve().parents[1] / "requests.json")
    # All four valid requests are sent.  u3 intentionally has no profile and
    # exercises the documented system-default fallback.
    assert len(result["results"]) == 4


def test_profile_is_queried():
    result = process_transactions(Path(__file__).resolve().parents[1] / "requests.json")
    assert result["profile_trace"]
