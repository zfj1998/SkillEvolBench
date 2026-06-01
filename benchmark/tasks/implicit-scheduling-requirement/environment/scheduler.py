from __future__ import annotations
import json
from pathlib import Path

import scheduling_policy
from calendar_loader import load_context

ROOT = Path(__file__).resolve().parent

def main() -> None:
    result = scheduling_policy.recommend_schedule(load_context())
    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "schedule.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
