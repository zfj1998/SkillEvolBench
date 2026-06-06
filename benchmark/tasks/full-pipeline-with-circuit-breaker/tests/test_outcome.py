from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from breaker_client import ResilientClient
from mock_breaker import DownstreamAPI, FakeClock
from verifier_lib.runtime import emit_report, print_report, run_checks

CALL_SCHEDULE = [0, 2, 4, 6, 8, 10, 12, 14, 20, 25, 35, 36]


def _drive_client():
    service = DownstreamAPI()
    clock = FakeClock()
    client = ResilientClient(service, failure_threshold=5, recovery_timeout=15.0)
    results = []
    for ts in CALL_SCHEDULE:
        clock.set(ts)
        results.append({"timestamp": ts, **client.get_resource(clock)})
    return results, service, client


def run():
    public = run_checks(
        "public",
        [
            ("healthy_period_succeeds", lambda: "body" in _drive_client()[0][0] or (_ for _ in ()).throw(AssertionError("healthy request should succeed"))),
            ("recovery_period_succeeds", lambda: _drive_client()[0][-1]["body"]["value"] == "recovered-36" or (_ for _ in ()).throw(AssertionError("recovered request should succeed"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("no_requests_while_open", lambda: len([row for row in _drive_client()[1].trace if 20 <= row["timestamp"] < 35]) == 0 or (_ for _ in ()).throw(AssertionError("breaker should block requests while open"))),
            ("half_open_probe_occurs", lambda: any(row["timestamp"] == 35 for row in _drive_client()[1].trace) or (_ for _ in ()).throw(AssertionError("expected half-open probe at 35"))),
            ("probe_success_closes_immediately", lambda: next(row for row in _drive_client()[0] if row["timestamp"] == 35)["state"] == "closed" or (_ for _ in ()).throw(AssertionError("successful half-open probe should close the circuit immediately"))),
            ("probe_success_recloses_circuit", lambda: _drive_client()[0][-1]["state"] == "closed" or (_ for _ in ()).throw(AssertionError("circuit should close after recovery"))),
            ("503_count_bounded", lambda: len([row for row in _drive_client()[1].trace if row["status"] == 503]) <= 8 or (_ for _ in ()).throw(AssertionError("too many downstream 503 calls"))),
        ],
    )
    return emit_report("E2-LS2-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
