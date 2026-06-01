from __future__ import annotations

import time

POLL_INTERVAL_SECONDS = 1.05


def wait_for_next_poll() -> None:
    time.sleep(POLL_INTERVAL_SECONDS)
