from __future__ import annotations

import json
from pathlib import Path


def write_loss_report(output_dir: Path, notes: list[dict]) -> None:
    (output_dir / "loss_report.json").write_text(json.dumps(notes, indent=2), encoding="utf-8")
