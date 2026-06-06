#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

python3 - <<'PY'
from pathlib import Path
root = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task"))
path = root / "backoff_profile.py"
text = path.read_text(encoding="utf-8")
text = text.replace(
    '    # This profile still uses a linear warm-up schedule from the old client,\n'
    '    # even though the runbook now expects exponential backoff.\n'
    '    linear_delay = base_delay * (attempt + 1)\n'
    '    jitter = rng.uniform(0.0, base_delay * SERVICE_PROFILE["jitter_window"])\n'
    '    return linear_delay + jitter\n',
    '    exponential_delay = base_delay * (SERVICE_PROFILE["documented_multiplier"] ** attempt)\n'
    '    jitter = rng.uniform(0.0, base_delay)\n'
    '    return exponential_delay + jitter\n',
)
path.write_text(text, encoding="utf-8")

client = root / "retry_client.py"
client_text = client.read_text(encoding="utf-8")
client_text = client_text.replace(
    "from backoff_profile import compute_retry_delay\n",
    "from backoff_profile import SERVICE_PROFILE, compute_retry_delay\n",
)
client_text = client_text.replace(
    "            delay = compute_retry_delay(attempt, base_delay, rng)\n",
    "            exponential_delay = base_delay * (SERVICE_PROFILE[\"documented_multiplier\"] ** attempt)\n"
    "            jitter = rng.uniform(0.0, base_delay)\n"
    "            delay = exponential_delay + jitter\n",
)
client.write_text(client_text, encoding="utf-8")
PY
