import json

from input_contracts import (
    is_transport_dict,
    is_transport_empty_string,
    normalize_transport_value,
)
from legacy_formatter import maybe_wrap
from stage_runtime import prepare_stage_input, remember_stage
from stage_contracts import default_marker, default_structure, empty_render, should_skip_transform


def parse(value):
    remember_stage("parse", value)
    value = normalize_transport_value(prepare_stage_input(value))
    if value is None:
        return default_structure()
    if is_transport_empty_string(value):
        return default_structure()
    if isinstance(value, str):
        return json.loads(value)
    if is_transport_dict(value):
        return value
    raise TypeError("unsupported input")


def transform(value):
    remember_stage("transform", value)
    if should_skip_transform(value):
        return None
    if value == {}:
        return default_marker()
    return {**value, "_transformed": True}


def format_output(value):
    remember_stage("format_output", value)
    if value is None:
        return empty_render()
    return maybe_wrap(json.dumps(value, sort_keys=True))


def run_pipeline(value):
    parsed = parse(value)
    transformed = transform(parsed)
    return format_output(transformed)
