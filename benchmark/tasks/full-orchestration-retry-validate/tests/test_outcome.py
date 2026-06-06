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

SOURCE = PROJECT / 'full_workflow.py'
OUTPUT = PROJECT / 'validated_result.json'


def _execute():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t6_full', SOURCE)
    result = module.run(OUTPUT)
    saved = json.loads(OUTPUT.read_text(encoding='utf-8'))
    return result, saved, list(mock_api.TRACE)


def run():
    public = run_checks('public', [])
    hidden = run_checks('hidden', [
        ('all_six_steps', lambda: {'/auth', '/users/user_1', '/premium/spec', '/jobs', '/jobs/job-001/status', '/jobs/job-001/result'} <= {item['endpoint'] for item in _execute()[2]} or (_ for _ in ()).throw(AssertionError(f'missing workflow step in trace: {_execute()[2]}'))),
        ('correct_branch', lambda: any(item['endpoint'] == '/premium/spec' for item in _execute()[2]) and all(item['endpoint'] != '/standard/spec' for item in _execute()[2]) or (_ for _ in ()).throw(AssertionError('wrong branch used'))),
        ('premium_job_submitted', lambda: any(item['endpoint'] == '/jobs' and item['extra'].get('job_kind') == 'priority-review' for item in _execute()[2]) or (_ for _ in ()).throw(AssertionError('submitted job should use the premium job kind'))),
        ('status_503_retried', lambda: any(item['endpoint'] == '/jobs/job-001/status' and item['status'] == 503 for item in _execute()[2]) and sum(1 for item in _execute()[2] if item['endpoint'] == '/jobs/job-001/status' and item['status'] == 200) >= 2 or (_ for _ in ()).throw(AssertionError('503 retry pattern missing'))),
        ('polls_until_completed', lambda: [item for item in _execute()[2] if item['endpoint'] == '/jobs/job-001/status' and item['status'] == 200][-1]['response']['status'] == 'completed' or (_ for _ in ()).throw(AssertionError('did not poll until completed'))),
        ('validated_saved_result', lambda: _execute()[1]['approved'] is True and _execute()[1]['checksum'] == 'chk-premium' and _execute()[1]['tier'] == 'premium' or (_ for _ in ()).throw(AssertionError('final saved result is not validated premium output'))),
    ])
    return emit_report('E2-LS4-T6', public, hidden)


if __name__ == '__main__':
    print_report(run())
