#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/make_readable.py" <<'__SKILL_EVOL_REFERENCE_MAKE_READABLE_PY_0__'
import json
from pathlib import Path

from render_plan import SECTIONS
from section_renderer import heading, kv_table

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "data.min.json"
OUTPUT = ROOT / "readable_output.md"


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    parts = ["# Configuration Snapshot", ""]
    company = data.get("company", {})
    parts.extend([heading("Company"), kv_table([(k, str(v)) for k, v in company.items()]), ""])
    teams = data.get("teams", [])
    parts.extend([heading("Teams")])
    for team in teams:
        parts.append(kv_table([(k, str(v)) for k, v in team.items()]))
        parts.append("")
    services = data.get("services", [])
    parts.extend([heading("Services")])
    for svc in services:
        parts.append(kv_table([(k, str(v)) for k, v in svc.items()]))
        parts.append("")
    settings = data.get("settings", {})
    parts.extend([heading("Settings"), kv_table([(k, str(v)) for k, v in settings.items()]), ""])
    summary = data.get("summary", {})
    parts.extend([heading("Summary"), kv_table([(k, str(v)) for k, v in summary.items()]), ""])
    OUTPUT.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_MAKE_READABLE_PY_0__
