#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path

project = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
client = project / "breaker_client.py"
text = client.read_text(encoding="utf-8")
text = text.replace(
    "        self._breaker.next_probe_at = next_probe_time(\n"
    "            clock.time(),\n"
    "            self.recovery_timeout,\n"
    "            success_budget=self._breaker.recent_success_budget,\n"
    "        )",
    "        self._breaker.next_probe_at = next_probe_time(clock.time(), self.recovery_timeout)",
)
text = text.replace(
    "            self._breaker.recent_success_budget = min(self._breaker.recent_success_budget + 5.0, 10.0)\n",
    "",
)
text = text.replace(
    "                self._breaker.recent_success_budget = 0.0\n",
    "",
)
text = text.replace(
    "                self._breaker.probe_in_flight = False\n"
    "                self.state_history.append(snapshot_state(self._breaker))\n"
    "                return {\"state\": self.HALF_OPEN, \"body\": response[\"body\"]}",
    "                self._breaker.mode = self.CLOSED\n"
    "                self._breaker.probe_in_flight = False\n"
    "                self.state_history.append(snapshot_state(self._breaker))\n"
    "                return {\"state\": self.CLOSED, \"body\": response[\"body\"]}",
)
client.write_text(text, encoding="utf-8")

cooldown = project / "cooldown_policy.py"
text = cooldown.read_text(encoding="utf-8")
text = text.replace(
    "def next_probe_time(now: float, recovery_timeout: float, success_budget: float = 0.0) -> float:\n"
    "    # The starter still carries an old rollout heuristic that cuts cooldown after\n"
    "    # a recent stretch of healthy traffic, which is too aggressive for a breaker.\n"
    "    shortened_timeout = recovery_timeout - min(success_budget, recovery_timeout - 5.0)\n"
    "    return now + max(5.0, shortened_timeout)\n",
    "def next_probe_time(now: float, recovery_timeout: float) -> float:\n"
    "    return now + recovery_timeout\n",
)
cooldown.write_text(text, encoding="utf-8")

print("Applied circuit breaker cooldown and half-open transition fixes.")
__SKILL_EVOL_SOLVE_PY_0__
