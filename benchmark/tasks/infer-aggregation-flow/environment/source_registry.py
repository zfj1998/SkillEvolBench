from __future__ import annotations

import json
from pathlib import Path


def load_sources(path: str | Path) -> list[dict[str, object]]:
    regions = json.loads(Path(path).read_text(encoding='utf-8'))
    # The starter still treats secondary-lane feeds as optional rollout traffic,
    # even though the summary job now expects all enabled regions.
    return [region for region in regions if region.get('enabled') and region.get('lane') == 'primary']
