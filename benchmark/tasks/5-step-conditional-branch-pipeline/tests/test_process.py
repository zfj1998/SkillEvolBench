from __future__ import annotations

import ast
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / 'project'
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import mock_api
from verifier_lib.runtime import emit_report, load_module, print_report, read_text, run_checks

SOURCE = PROJECT / 'offers_pipeline.py'
ROUTER = PROJECT / 'offer_router.py'
OUTPUT = PROJECT / 'offers_output.json'


def _run_trace():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t2_process_pipeline', SOURCE)
    module.run(OUTPUT)
    return list(mock_api.TRACE)


def _has_condition():
    tree = ast.parse(read_text(SOURCE))
    assert any(isinstance(node, ast.If) for node in ast.walk(tree)), 'expected a conditional branch in source'
    return 'if statement found'


def _endpoint_matches_status():
    trace = _run_trace()
    status_by_user = {item['user_id']: item['status'] for item in trace if item['endpoint'] == '/user'}
    branch_hits = {item['user_id']: item['endpoint'] for item in trace if item['endpoint'] in {'/premium/offers', '/standard/offers'}}
    assert branch_hits['user_1'] == '/premium/offers', 'premium user should use premium endpoint'
    assert branch_hits['user_2'] == '/standard/offers', 'standard user should use standard endpoint'
    assert status_by_user['user_3'] == 'premium' and branch_hits['user_3'] == '/premium/offers', 'user_3 branch mismatch'
    return branch_hits


def _router_uses_status():
    text = read_text(ROUTER)
    assert 'status' in text, 'router should branch on the current status field'
    assert 'billing_tier' not in text, 'router should not rely on the stale billing-tier field'
    return 'router uses runtime status'


def run():
    public = run_checks('public', [('has_condition', _has_condition)])
    hidden = run_checks('hidden', [('endpoint_matches_status', _endpoint_matches_status), ('router_uses_status', _router_uses_status)])
    return emit_report('E2-LS4-T2', public, hidden)


if __name__ == '__main__':
    print_report(run())
