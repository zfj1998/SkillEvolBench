from __future__ import annotations

import json


def encode_scalar(value):
    if isinstance(value, list):
        return json.dumps(value)
    if value is None:
        return ""
    return str(value)


def decode_scalar(value: str):
    if value.startswith("[") and value.endswith("]"):
        return json.loads(value)
    # BUG: booleans and nulls still roundtrip as strings.
    return value
