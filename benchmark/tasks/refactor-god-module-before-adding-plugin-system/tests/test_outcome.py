from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from verifier_lib.runtime import emit_report, print_report, run_checks
import processor


def _json_identity():
    result = processor.process(json.dumps([{"name": "alice", "amount": "5.0"}]))
    assert result["status"] == "ok", "json identity should succeed"
    return result


def _csv_uppercase():
    result = processor.process("name,amount\nalice,3\n", input_format="csv", mode="uppercase")
    assert result["result"][0]["name"] == "ALICE", "csv uppercase flow broken"
    return result


def _file_output():
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "result.json"
        result = processor.process(json.dumps([{"name": "alice", "amount": "5.0"}]), destination="file", output_file=str(output_path))
        assert result["status"] == "ok", "file output should succeed"
        assert output_path.exists(), "output file missing"
        return {"path": str(output_path)}


def _plugin_support_detected():
    names = {path.name for path in PROJECT.glob("*.py")}
    text = "\n".join(path.read_text(encoding="utf-8") for path in PROJECT.glob("*.py"))
    assert "register_plugin" in text or "load_plugins" in text or "plugin" in names, "plugin support not implemented"
    return "plugin support markers detected"


def _broken_plugin_does_not_crash():
    plugin_dir = PROJECT / "plugins"
    plugin_dir.mkdir(exist_ok=True)
    broken = plugin_dir / "zz_broken_plugin.py"
    broken.write_text("def not_valid(:\n", encoding="utf-8")
    result = processor.process(json.dumps([{"name": "alice", "amount": "5.0"}]))
    assert result["status"] == "ok", "broken plugin should not take down processing"
    return result


def _registered_plugin_executes():
    if not hasattr(processor, "register_plugin"):
        return "register_plugin unavailable; load-based plugin behavior checked separately"

    def add_marker(row):
        item = dict(row)
        item["plugin_marker"] = "seen"
        return item

    processor.register_plugin(add_marker, name="marker", order=10)
    result = processor.process(json.dumps([{"name": "alice", "amount": "5.0"}]))
    assert result["result"][0].get("plugin_marker") == "seen", "registered plugin did not execute"
    return result


def _xml_parse_available():
    raw = "<rows><row><name>alice</name><amount>5</amount></row></rows>"
    result = processor.process(raw, input_format="xml")
    assert result["status"] == "ok", "xml input path should still work after refactor"
    return result


def run():
    public = run_checks(
        "public",
        [
            ("json_identity", _json_identity),
            ("csv_uppercase", _csv_uppercase),
            ("file_output", _file_output),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("plugin_support_detected", _plugin_support_detected),
            ("registered_plugin_executes", _registered_plugin_executes),
            ("broken_plugin_does_not_crash", _broken_plugin_does_not_crash),
            ("xml_parse_available", _xml_parse_available),
        ],
    )
    return emit_report("E1-LS3-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
