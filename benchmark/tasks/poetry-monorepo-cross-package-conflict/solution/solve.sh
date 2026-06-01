#!/usr/bin/env bash
set -euo pipefail

TASK_ROOT="${TASK_ROOT:-/root/task}"
PROJECT_ROOT="${PROJECT_ROOT:-/root/task/monorepo}"
MONOREPO_DIR="$PROJECT_ROOT"

cd "$MONOREPO_DIR"

python - <<'PY'
from pathlib import Path

api_pyproject = Path("packages/api/pyproject.toml")
text = api_pyproject.read_text()
text = text.replace('fastapi = "==0.95.0"', 'fastapi = ">=0.100.0,<0.101.0"')
api_pyproject.write_text(text)

app_py = Path("packages/api/api_pkg/app.py")
app_py.write_text(
"""from fastapi import FastAPI
from pydantic import BaseModel, field_validator


app = FastAPI()


class JobRequest(BaseModel):
    name: str
    priority: int

    @field_validator("name")
    def normalize_name(value):
        return value.strip().title()

    def to_payload(self) -> dict:
        return self.model_dump()


@app.post("/jobs")
def create_job(name: str, priority: int = 1) -> dict:
    req = JobRequest(name=name, priority=priority)
    return req.to_payload()


def get_api_payload(name: str = "  batch sync  ", priority: int = 2) -> dict:
    req = JobRequest(name=name, priority=priority)
    return req.to_payload()
"""
)
PY

./poetry install
./poetry run python -c "from worker_pkg import run_worker; out = run_worker(); assert out['core']['name'] == 'WORKER'; assert out['api']['name'] == 'Worker Queue'; print(out)"
