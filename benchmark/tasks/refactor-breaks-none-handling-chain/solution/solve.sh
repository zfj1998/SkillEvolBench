#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))
source = root / "pipeline.py"

source.write_text('''import json


class Pipeline:
    def parse(self, value):
        if value is None:
            return {}
        if value == "":
            return {}
        if isinstance(value, str):
            return json.loads(value)
        if isinstance(value, dict):
            return value
        raise TypeError("unsupported input")

    def transform(self, value):
        if value is None:
            return None
        if value == {}:
            return {"_default": True}
        return {**value, "_transformed": True}

    def format_output(self, value):
        if value is None:
            return ""
        return json.dumps(value, sort_keys=True)

    def run(self, value):
        parsed = self.parse(value)
        transformed = self.transform(parsed)
        return self.format_output(transformed)


_DEFAULT_PIPELINE = Pipeline()


def parse(value):
    return _DEFAULT_PIPELINE.parse(value)


def transform(value):
    return _DEFAULT_PIPELINE.transform(value)


def format_output(value):
    return _DEFAULT_PIPELINE.format_output(value)


def run_pipeline(value):
    return _DEFAULT_PIPELINE.run(value)
''', encoding="utf-8")
PY
