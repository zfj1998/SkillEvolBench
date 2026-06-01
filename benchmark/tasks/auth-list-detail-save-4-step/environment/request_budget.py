from __future__ import annotations

import time

# The starter still uses a "smooth pacing" guess from an earlier client. In
# practice 250ms spacing is not enough to stay under a 3 requests / second cap.
DETAIL_SPACING_SECONDS = 0.25


def wait_before_detail(index: int) -> None:
    if index > 1:
        time.sleep(DETAIL_SPACING_SECONDS)
