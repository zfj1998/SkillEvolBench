from __future__ import annotations

import json
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

SOURCE = PROJECT / 'report_workflow.py'
OUTPUT = PROJECT / 'report_output.json'


def _execute():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t3_report', SOURCE)
    result = module.run(OUTPUT)
    saved = json.loads(OUTPUT.read_text(encoding='utf-8'))
    return result, saved, list(mock_api.TRACE)


def run():
    public = run_checks('public', [
        ('report_saved', lambda: OUTPUT.exists() if _execute() else (_ for _ in ()).throw(AssertionError('report_output.json missing'))),
        ('report_format', lambda: {'month', 'totals', 'segments'} <= set(_execute()[1]) or (_ for _ in ()).throw(AssertionError('report payload missing expected fields'))),
    ])
    hidden = run_checks('hidden', [
        ('post_status_result_flow', lambda: [item['endpoint'] for item in _execute()[2]][0] == '/reports' and _execute()[2][-1]['endpoint'].endswith('/result') and sum(1 for item in _execute()[2] if item['endpoint'].endswith('/status')) >= 4 or (_ for _ in ()).throw(AssertionError('trace does not show POST -> status* -> result'))),
        ('poll_interval_respected', lambda: all((later['ts'] - earlier['ts']) >= mock_api.MIN_POLL_INTERVAL for earlier, later in zip([item for item in _execute()[2] if item['endpoint'].endswith('/status')], [item for item in _execute()[2] if item['endpoint'].endswith('/status')][1:])) or (_ for _ in ()).throw(AssertionError('poll interval too short'))),
        ('result_after_completed', lambda: [item for item in _execute()[2] if item['endpoint'].endswith('/status')][-1]['payload']['status'] == 'completed' or (_ for _ in ()).throw(AssertionError('last status was not completed before result fetch'))),
        ('report_data_correct', lambda: _execute()[1] == mock_api.REPORT_DATA or (_ for _ in ()).throw(AssertionError('report payload mismatch'))),
    ])
    return emit_report('E2-LS4-T3', public, hidden)


if __name__ == '__main__':
    print_report(run())
