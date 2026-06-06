from __future__ import annotations

import json
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, run_checks, run_subprocess


def _node_eval(source: str):
    result = run_subprocess(["node", "--input-type=module", "-e", source], PROJECT)
    assert result.returncode == 0, result.stderr.strip() or result.stdout.strip()
    return json.loads(result.stdout.strip())


def _run_public_suite():
    result = run_subprocess(["node", "--test", "public_tests/processEvent.test.js"], PROJECT)
    assert result.returncode == 0, result.stdout + result.stderr
    return "node tests pass"


def _user_login_fallthrough():
    payload = _node_eval(
        "import {createLogger} from './src/logger.js';"
        "import {createEmitter} from './src/events.js';"
        "import {processEvent} from './src/processEvent.js';"
        "const logger=createLogger(); const emitter=createEmitter(); const updates=[];"
        "const result=processEvent('USER_LOGIN',{userId:1},{logger,emitter,updates});"
        "console.log(JSON.stringify({processed:result.processed, updates, calls:logger.calls}));"
    )
    assert "activity" in payload["processed"], "USER_LOGIN must retain activity fallthrough"
    assert len(payload["updates"]) == 1, "USER_LOGIN should update last active"
    return payload


def _purchase_start_fallthrough():
    payload = _node_eval(
        "import {createLogger} from './src/logger.js';"
        "import {processEvent} from './src/processEvent.js';"
        "const logger=createLogger();"
        "const result=processEvent('PURCHASE_START',{orderId:5},{logger});"
        "console.log(JSON.stringify({processed:result.processed, calls:logger.calls}));"
    )
    assert "purchase" in payload["processed"], "PURCHASE_START should run purchase logic"
    return payload


def _error_and_warning_levels():
    payload = _node_eval(
        "import {createLogger} from './src/logger.js';"
        "import {processEvent} from './src/processEvent.js';"
        "const logger=createLogger();"
        "const errorResult=processEvent('ERROR',{message:'boom'},{logger});"
        "const warningResult=processEvent('WARNING',{message:'careful'},{logger});"
        "console.log(JSON.stringify({errorLevel:errorResult.level, warningLevel:warningResult.level,"
        "errorProcessed:errorResult.processed,warningProcessed:warningResult.processed}));"
    )
    assert payload["errorLevel"] == "high", "ERROR should map to high level"
    assert payload["warningLevel"] == "low", "WARNING should map to low level"
    assert "alert" in payload["errorProcessed"], "ERROR should include alert processing"
    assert "alert" in payload["warningProcessed"], "WARNING should include alert processing"
    return payload


def _default_warns():
    payload = _node_eval(
        "import {createLogger} from './src/logger.js';"
        "import {processEvent} from './src/processEvent.js';"
        "const logger=createLogger();"
        "const result=processEvent('OTHER',{},{logger});"
        "console.log(JSON.stringify({result, calls:logger.calls}));"
    )
    assert payload["calls"][0]["level"] == "warn", "default branch should warn"
    assert payload["result"]["originalType"] == "OTHER", "default branch should preserve original type"
    return payload


def run():
    public = run_checks("public", [("node_public_suite", _run_public_suite)])
    hidden = run_checks(
        "hidden",
        [
            ("user_login_fallthrough", _user_login_fallthrough),
            ("purchase_start_fallthrough", _purchase_start_fallthrough),
            ("error_and_warning_levels", _error_and_warning_levels),
            ("default_warns", _default_warns),
            ("user_activity_no_login_log", lambda: ("info" not in [call["level"] for call in _node_eval("import {createLogger} from './src/logger.js';import {processEvent} from './src/processEvent.js';const logger=createLogger();const result=processEvent('USER_ACTIVITY',{userId:2},{logger});console.log(JSON.stringify({calls:logger.calls,result}));")["calls"]]) or (_ for _ in ()).throw(AssertionError("USER_ACTIVITY should not log login info"))),
        ],
    )
    return emit_report("E1-LS3-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
