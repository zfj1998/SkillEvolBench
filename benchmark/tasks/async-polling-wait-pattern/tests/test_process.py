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

SOURCE = PROJECT / 'report_workflow.py'
STATUS_GATE = PROJECT / 'status_gate.py'
POLLING_POLICY = PROJECT / 'polling_policy.py'
OUTPUT = PROJECT / 'report_output.json'


def _run_trace():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t3_report_process', SOURCE)
    module.run(OUTPUT)
    return list(mock_api.TRACE)


def _polling_loop_present():
    tree = ast.parse(read_text(SOURCE))
    assert any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)), 'missing polling loop'
    return 'loop found'


def _sleep_present():
    tree = ast.parse(read_text(POLLING_POLICY))
    assert any(
        isinstance(node, ast.Call)
        and (
            getattr(node.func, 'id', None) == 'sleep'
            or getattr(node.func, 'attr', None) == 'sleep'
        )
        for node in ast.walk(tree)
    ), 'missing sleep/wait between polls'
    return 'sleep found'


def _status_before_result():
    trace = _run_trace()
    endpoints = [item['endpoint'] for item in trace]
    assert any(endpoint.endswith('/status') for endpoint in endpoints), 'no status polling happened'
    assert endpoints[-1].endswith('/result'), f'last endpoint should be result, got {endpoints[-1]}'
    gate_text = read_text(STATUS_GATE)
    assert 'completed' in gate_text, 'status gate should explicitly wait for completed'
    return endpoints


def run():
    public = run_checks('public', [('polling_loop_present', _polling_loop_present)])
    hidden = run_checks('hidden', [('sleep_present', _sleep_present), ('status_before_result', _status_before_result)])
    return emit_report('E2-LS4-T3', public, hidden)


if __name__ == '__main__':
    print_report(run())
