#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/flatten_policy.py" <<'__SKILL_EVOL_REFERENCE_FLATTEN_POLICY_PY_0__'
from __future__ import annotations

import json


def encode_scalar(value):
    if isinstance(value, list):
        return json.dumps(value)
    if value is None:
        return "__NULL__"
    if isinstance(value, bool):
        return "__BOOL_TRUE__" if value else "__BOOL_FALSE__"
    if isinstance(value, int):
        return f"__INT__:{value}"
    if isinstance(value, float):
        return f"__FLOAT__:{value}"
    return str(value)


def decode_scalar(value: str):
    if value == "__NULL__":
        return None
    if value == "__BOOL_TRUE__":
        return True
    if value == "__BOOL_FALSE__":
        return False
    if value.startswith("__INT__:"):
        return int(value.split(":", 1)[1])
    if value.startswith("__FLOAT__:"):
        return float(value.split(":", 1)[1])
    if value.startswith("[") and value.endswith("]"):
        return json.loads(value)
    return value
__SKILL_EVOL_REFERENCE_FLATTEN_POLICY_PY_0__
cat > "$PROJECT_ROOT/roundtrip.py" <<'__SKILL_EVOL_REFERENCE_ROUNDTRIP_PY_0__'
import csv
import json
from pathlib import Path

from flatten_policy import decode_scalar, encode_scalar
from roundtrip_check import is_lossless

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input.json"
CSV_OUT = ROOT / "flattened.csv"
ROUNDTRIP_OUT = ROOT / "roundtrip.json"
VERIFY_OUT = ROOT / "verification.json"


def flatten(value, prefix="", out=None):
    if out is None:
        out = {}
    if isinstance(value, dict):
        for k, v in value.items():
            flatten(v, f"{prefix}.{k}" if prefix else k, out)
    elif isinstance(value, list):
        out[prefix] = encode_scalar(value)
    else:
        out[prefix] = encode_scalar(value)
    return out


def unflatten(flat):
    root = {}
    for key, value in flat.items():
        parts = key.split(".")
        cur = root
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = decode_scalar(value)
    return root


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    flat = flatten(data)
    with CSV_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat.keys()))
        writer.writeheader()
        writer.writerow(flat)

    with CSV_OUT.open("r", encoding="utf-8", newline="") as f:
        row = next(csv.DictReader(f))
    restored = unflatten(row)
    ROUNDTRIP_OUT.write_text(json.dumps(restored, indent=2), encoding="utf-8")
    VERIFY_OUT.write_text(
        json.dumps({"lossless": is_lossless(data, restored), "exact_match": restored == data}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_ROUNDTRIP_PY_0__
