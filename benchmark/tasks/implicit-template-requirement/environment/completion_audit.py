from __future__ import annotations

from pathlib import Path


def write_replaced_keys(path: Path, replaced_keys: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(replaced_keys) + ("\n" if replaced_keys else ""), encoding="utf-8")
