from __future__ import annotations

from pathlib import Path

import sys

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"

if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from inventory_cache import LastGoodPayloadCache
from transport_guard import decode_payload
from verifier_lib.runtime import emit_report, print_report, run_checks


def run():
    class Logger:
        def warning(self, *args, **kwargs):
            pass

    class Response:
        def __init__(self, payload=None, text=""):
            self.payload = payload
            self.text = text

        def json(self):
            if isinstance(self.payload, Exception):
                raise self.payload
            return self.payload

    cache = LastGoodPayloadCache()
    cache.observe({"data": [{"id": 99}]})
    public = run_checks("public", [
        ("json_parse_guard_present", lambda: not decode_payload(Response(ValueError("bad"), "<html>"), cache, Logger()) or (_ for _ in ()).throw(AssertionError("malformed JSON was emitted as inventory data"))),
    ])
    hidden = run_checks("hidden", [
        ("empty_data_handled", lambda: decode_payload(Response({"data": [], "metadata": {"batch_size": 0}}), cache, Logger()).get("data") == [] or (_ for _ in ()).throw(AssertionError("honest empty page is not handled"))),
        ("no_last_good_replay", lambda: decode_payload(Response({"data": [], "metadata": {"batch_size": 5}}), cache, Logger()).get("data") == [] or (_ for _ in ()).throw(AssertionError("lying empty page replays stale inventory"))),
    ])
    return emit_report("E2-LS5-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
