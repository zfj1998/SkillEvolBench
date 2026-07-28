from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / 'project'
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import mock_api
from verifier_lib.runtime import emit_report, load_module, print_report, run_checks

SOURCE = PROJECT / 'full_workflow.py'
ROUTER = PROJECT / 'spec_router.py'
POLLER = PROJECT / 'job_poller.py'
VALIDATOR = PROJECT / 'result_validator.py'
OUTPUT = PROJECT / 'validated_result.json'


def _run_trace():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t6_process', SOURCE)
    module.run(OUTPUT)
    return list(mock_api.TRACE)


def _ordered_steps():
    trace = _run_trace()
    endpoints = [item['endpoint'] for item in trace]
    expected_prefix = ['/auth', '/users/user_1']
    assert endpoints[:2] == expected_prefix, f'workflow order mismatch: {endpoints}'
    assert '/jobs' in endpoints, 'missing job submission step'
    return endpoints


def _token_propagation():
    trace = _run_trace()
    downstream = [item for item in trace if item['endpoint'] != '/auth']
    assert all(item['headers'].get('Authorization') == f'Bearer {mock_api.TOKEN}' for item in downstream), 'token missing in downstream calls'
    return 'token propagated'


def _retry_and_wait_present():
    trace = _run_trace()
    statuses = [item for item in trace if item['endpoint'] == '/jobs/job-001/status']
    assert any(item['status'] == 503 for item in statuses), 'missing 503 during polling'
    success_calls = [item for item in statuses if item['status'] == 200]
    assert len(success_calls) >= 2, 'missing retry after 503'
    assert any((later['ts'] - earlier['ts']) >= mock_api.MIN_POLL_INTERVAL for earlier, later in zip(success_calls, success_calls[1:])), 'missing wait between successful polls'
    return 'retry and wait present'


def _routes_from_tier():
    endpoints = [item['endpoint'] for item in _run_trace()]
    assert '/premium/spec' in endpoints
    assert '/standard/spec' not in endpoints
    return 'runtime routes from the current premium tier'


def _validator_uses_expected_checksum():
    from result_validator import validate_result
    valid = {
        'approved': True,
        'user_id': 'user_1',
        'tier': 'premium',
        'records': [],
        'checksum': 'chk-premium',
    }
    assert validate_result(valid, 'chk-premium') == valid
    try:
        validate_result(valid, 'chk-other')
    except ValueError:
        return 'validator rejects a checksum that only matches the prefix'
    raise AssertionError('validator did not compare the exact expected checksum')


def run():
    public = run_checks('public', [('ordered_steps', _ordered_steps)])
    hidden = run_checks('hidden', [('token_propagation', _token_propagation), ('retry_and_wait_present', _retry_and_wait_present), ('routes_from_tier', _routes_from_tier), ('validator_uses_expected_checksum', _validator_uses_expected_checksum)])
    return emit_report('E2-LS4-T6', public, hidden)


if __name__ == '__main__':
    print_report(run())
