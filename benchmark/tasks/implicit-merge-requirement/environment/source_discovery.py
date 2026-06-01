from __future__ import annotations

from pathlib import Path


KNOWN_FILES = ["crm_export.csv", "event_attendees.csv"]


def discover_sources(base_dir: Path) -> list[Path]:
    # Legacy allowlist misses newsletter_list.csv.
    return [base_dir / name for name in KNOWN_FILES if (base_dir / name).exists()]
