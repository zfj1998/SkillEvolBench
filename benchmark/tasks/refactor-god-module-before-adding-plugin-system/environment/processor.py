import csv
import io
import json
import xml.etree.ElementTree as ET

from fake_sink_adapter import FakeSinkAdapter

ACTIVE_OUTPUT = "memory"
ACTIVE_FORMAT = "json"
LAST_ERROR = None
TRANSFORM_COUNT = 0
AUDIT_LOG = []
FILTERED_ROWS = 0
LAST_INPUT_SIGNATURE = ""
LAST_DESTINATION_PAYLOAD = {}


def _parse_xml(raw_data):
    root = ET.fromstring(raw_data)
    rows = []
    for row in root.findall("row"):
        rows.append({child.tag: child.text for child in row})
    return rows


def _coerce_amount(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_row(row):
    normalized = {}
    for key, value in row.items():
        normalized[key] = value.strip() if isinstance(value, str) else value
    return normalized


def _build_input_signature(rows, input_format):
    preview_keys = []
    if rows:
        preview_keys = sorted(rows[0].keys())
    return f"{input_format}:{len(rows)}:{','.join(preview_keys)}"


def _resolve_destination_payload(destination, transformed):
    if destination == "api":
        adapter = FakeSinkAdapter()
        return adapter.flush(transformed)
    return {"sent": len(transformed), "rows": transformed}


def _track_audit(status, **details):
    entry = {"status": status, **details}
    AUDIT_LOG.append(entry)
    return entry


def parse_input(raw_data, input_format="json"):
    global ACTIVE_FORMAT
    ACTIVE_FORMAT = input_format
    if input_format == "json":
        rows = json.loads(raw_data)
        return [_normalize_row(row) for row in rows]
    if input_format == "csv":
        reader = csv.DictReader(io.StringIO(raw_data))
        return [_normalize_row(row) for row in reader]
    if input_format == "xml":
        return [_normalize_row(row) for row in _parse_xml(raw_data)]
    raise ValueError(f"unsupported format: {input_format}")


def transform_data(parsed, mode="identity"):
    global FILTERED_ROWS, TRANSFORM_COUNT
    TRANSFORM_COUNT += 1
    transformed = []
    for row in parsed:
        item = dict(row)
        if mode == "uppercase":
            for key, value in list(item.items()):
                if isinstance(value, str):
                    item[key] = value.upper()
        if mode == "filter-positive" and "amount" in item:
            amount = _coerce_amount(item["amount"])
            if amount <= 0:
                FILTERED_ROWS += 1
                continue
        if "amount" in item:
            item["amount"] = _coerce_amount(item["amount"])
        transformed.append(item)
    return transformed


def output_results(transformed, destination="memory", output_file=None):
    global ACTIVE_OUTPUT, LAST_DESTINATION_PAYLOAD
    ACTIVE_OUTPUT = destination
    if destination == "memory":
        return transformed
    if destination == "json":
        return json.dumps(transformed, sort_keys=True)
    if destination == "api":
        LAST_DESTINATION_PAYLOAD = _resolve_destination_payload(destination, transformed)
        return LAST_DESTINATION_PAYLOAD
    if destination == "file":
        if not output_file:
            raise ValueError("output_file required for file destination")
        with open(output_file, "w", encoding="utf-8") as handle:
            json.dump(transformed, handle, sort_keys=True)
        return output_file
    raise ValueError(f"unsupported destination: {destination}")


def handle_errors(exception):
    global LAST_ERROR
    LAST_ERROR = str(exception)
    _track_audit("error", message=str(exception))
    return {"status": "error", "message": str(exception)}


def process(raw_data, input_format="json", mode="identity", destination="memory", output_file=None):
    global LAST_INPUT_SIGNATURE
    try:
        parsed = parse_input(raw_data, input_format=input_format)
        LAST_INPUT_SIGNATURE = _build_input_signature(parsed, input_format)
        transformed = transform_data(parsed, mode=mode)
        result = output_results(transformed, destination=destination, output_file=output_file)
        _track_audit(
            "ok",
            rows=len(transformed),
            filtered=FILTERED_ROWS,
            destination=destination,
            signature=LAST_INPUT_SIGNATURE,
        )
        return {"status": "ok", "result": result}
    except Exception as exc:  # pragma: no cover - public behavior
        return handle_errors(exc)
