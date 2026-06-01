import json
from pathlib import Path

from processor import process


def test_process_json_identity():
    raw = json.dumps([{"name": "alice", "amount": "5.0"}])
    result = process(raw)
    assert result["status"] == "ok"
    assert result["result"][0]["name"] == "alice"


def test_process_csv_uppercase(tmp_path: Path):
    raw = "name,amount\nalice,3\n"
    output = process(raw, input_format="csv", mode="uppercase")
    assert output["result"][0]["name"] == "ALICE"


def test_output_file_destination(tmp_path: Path):
    raw = json.dumps([{"name": "alice", "amount": "5.0"}])
    output_file = tmp_path / "out.json"
    result = process(raw, destination="file", output_file=str(output_file))
    assert result["status"] == "ok"
    assert output_file.exists()


def test_invalid_format_returns_error():
    result = process("{}", input_format="xml")
    assert result["status"] == "error"
