#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('parser_utils.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('import csv\nimport io\nimport json\nimport xml.etree.ElementTree as ET\n\n\ndef parse_xml(raw_data):\n    root = ET.fromstring(raw_data)\n    return [{child.tag: child.text for child in row} for row in root.findall("row")]\n\n\ndef parse_input(raw_data, input_format="json"):\n    if input_format == "json":\n        return json.loads(raw_data)\n    if input_format == "csv":\n        return list(csv.DictReader(io.StringIO(raw_data)))\n    if input_format == "xml":\n        return parse_xml(raw_data)\n    raise ValueError(f"unsupported format: {input_format}")\n', encoding='utf-8')
PYWRITE_1

python3 - <<'PYWRITE_2'
from pathlib import Path
target = Path('transform_utils.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('from dataclasses import dataclass\n\n\n@dataclass\nclass TransformState:\n    filtered_rows: int = 0\n    transform_count: int = 0\n\n\ndef coerce_amount(value):\n    try:\n        return float(value)\n    except (TypeError, ValueError):\n        return 0.0\n\n\ndef transform_data(parsed, mode="identity", state=None, plugins=None):\n    state = state or TransformState()\n    plugins = plugins or []\n    state.transform_count += 1\n    transformed = []\n    for row in parsed:\n        item = dict(row)\n        if mode == "uppercase":\n            for key, value in list(item.items()):\n                if isinstance(value, str):\n                    item[key] = value.upper()\n        if mode == "filter-positive" and "amount" in item:\n            amount = coerce_amount(item["amount"])\n            if amount <= 0:\n                state.filtered_rows += 1\n                continue\n        if "amount" in item:\n            item["amount"] = coerce_amount(item["amount"])\n        for plugin in plugins:\n            item = plugin(item)\n        transformed.append(item)\n    return transformed\n', encoding='utf-8')
PYWRITE_2

python3 - <<'PYWRITE_3'
from pathlib import Path
target = Path('output_utils.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('import json\n\n\ndef output_results(transformed, destination="memory", output_file=None):\n    if destination == "memory":\n        return transformed\n    if destination == "json":\n        return json.dumps(transformed, sort_keys=True)\n    if destination == "api":\n        return {"sent": len(transformed), "rows": transformed}\n    if destination == "file":\n        if not output_file:\n            raise ValueError("output_file required for file destination")\n        with open(output_file, "w", encoding="utf-8") as handle:\n            json.dump(transformed, handle, sort_keys=True)\n        return output_file\n    raise ValueError(f"unsupported destination: {destination}")\n', encoding='utf-8')
PYWRITE_3

python3 - <<'PYWRITE_4'
from pathlib import Path
target = Path('plugin_runtime.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('PLUGIN_REGISTRY = []\n\n\ndef register_plugin(plugin=None, *, name=None, order=0):\n    def _register(func):\n        PLUGIN_REGISTRY.append({\"name\": name or func.__name__, \"order\": order, \"plugin\": func})\n        PLUGIN_REGISTRY.sort(key=lambda entry: entry[\"order\"])\n        return func\n    if plugin is None:\n        return _register\n    return _register(plugin)\n\n\ndef load_plugins():\n    return [entry[\"plugin\"] for entry in sorted(PLUGIN_REGISTRY, key=lambda entry: entry[\"order\"])]\n', encoding='utf-8')
PYWRITE_4

python3 - <<'PYWRITE_5'
from pathlib import Path
target = Path('processor.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('from dataclasses import dataclass, field\n\nfrom output_utils import output_results\nfrom parser_utils import parse_input\nfrom plugin_runtime import load_plugins, register_plugin\nfrom transform_utils import TransformState, transform_data\n\n\n@dataclass\nclass AuditState:\n    output: str = "memory"\n    input_format: str = "json"\n    last_error: str | None = None\n    log: list[dict] = field(default_factory=list)\n\n    def track(self, status, **details):\n        entry = {"status": status, **details}\n        self.log.append(entry)\n        return entry\n\n\n@register_plugin\ndef identity_plugin(item):\n    return item\n\n\ndef handle_errors(exception, state: AuditState):\n    state.last_error = str(exception)\n    state.track("error", message=str(exception))\n    return {"status": "error", "message": str(exception)}\n\n\ndef process(raw_data, input_format="json", mode="identity", destination="memory", output_file=None):\n    state = AuditState(output=destination, input_format=input_format)\n    transform_state = TransformState()\n    try:\n        parsed = parse_input(raw_data, input_format=input_format)\n        transformed = transform_data(parsed, mode=mode, state=transform_state, plugins=load_plugins())\n        result = output_results(transformed, destination=destination, output_file=output_file)\n        state.track("ok", rows=len(transformed), filtered=transform_state.filtered_rows, destination=destination)\n        return {"status": "ok", "result": result}\n    except Exception as exc:  # pragma: no cover\n        return handle_errors(exc, state)\n', encoding='utf-8')
PYWRITE_5
