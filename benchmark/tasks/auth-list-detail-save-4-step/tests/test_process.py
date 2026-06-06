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

SOURCE = PROJECT / 'workflow.py'
AUTH_SESSION = PROJECT / 'auth_session.py'
COLLECTOR = PROJECT / 'detail_collector.py'
BUDGET = PROJECT / 'request_budget.py'
OUTPUT = PROJECT / 'output.json'


def _run_and_trace():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t1_process_workflow', SOURCE)
    module.run(OUTPUT)
    return list(mock_api.TRACE)


def _step_order():
    trace = _run_and_trace()
    endpoints = [item['endpoint'] for item in trace]
    assert endpoints[0] == '/auth', f'expected auth first, got {endpoints}'
    assert endpoints[1] == '/items', f'expected list second, got {endpoints}'
    return endpoints


def _token_flow():
    trace = _run_and_trace()
    downstream = [item for item in trace if item['endpoint'] != '/auth']
    assert downstream, 'missing downstream calls'
    assert all(item['headers'].get('Authorization') == f'Bearer {mock_api.TOKEN}' for item in downstream), 'token not propagated'
    workflow_text = read_text(SOURCE)
    session_text = read_text(AUTH_SESSION)
    assert 'authenticate_session' in workflow_text, 'workflow should build an authenticated session'
    assert 'Authorization' in session_text and 'access_token' in session_text, 'auth session helper should build bearer headers from the auth payload'
    return 'token propagated'


def _list_to_detail_ids():
    trace = _run_and_trace()
    listed = ['item-1', 'item-2', 'item-3', 'item-4', 'item-5']
    detail_ids = [item['extra'].get('item_id') for item in trace if item['endpoint'].startswith('/items/')]
    assert detail_ids == listed, f'detail ids did not follow list order: {detail_ids}'
    tree = ast.parse(read_text(COLLECTOR))
    assert any(True for _ in tree.body), 'collector tree empty'
    return detail_ids


def _uses_rate_limit_budget():
    text = read_text(BUDGET)
    assert '1.0' in text or '1.05' in text or 'BATCH_SIZE' in text, 'expected request-budget logic that models the 3/s rate window'
    return 'request budget present'


def run():
    public = run_checks('public', [('step_order', _step_order)])
    hidden = run_checks('hidden', [('token_flow', _token_flow), ('list_to_detail_ids', _list_to_detail_ids), ('uses_rate_limit_budget', _uses_rate_limit_budget)])
    return emit_report('E2-LS4-T1', public, hidden)


if __name__ == '__main__':
    print_report(run())
