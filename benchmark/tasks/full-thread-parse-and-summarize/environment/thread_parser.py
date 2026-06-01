from __future__ import annotations

import json
from pathlib import Path

from context_loader import load_items
from extraction_policy import classify_item
from summary_writer import build_summary, status_summary


def main() -> None:
    items = load_items()
    actions: list[dict] = []
    non_actions: list[dict] = []
    classifications: list[dict] = []

    for item in items:
        classified = classify_item(item)
        classifications.append(classified)
        if classified.get("label") == "action":
            actions.append(classified)
        else:
            non_actions.append(classified)

    payload = {
        "actions": actions,
        "action_items": actions,
        "non_actions": non_actions,
        "classifications": classifications,
        "processed_count": len(items),
        "source_count": len(items),
        "status_summary": status_summary(actions),
        "summary": build_summary(actions, non_actions, items),
    }
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "thread_actions.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
