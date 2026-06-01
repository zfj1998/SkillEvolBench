from __future__ import annotations

import json
from pathlib import Path

from analyzer import analyze_resumes


ROOT = Path(__file__).resolve().parent


def main() -> None:
    output = analyze_resumes(ROOT)
    (ROOT / "output.json").write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
