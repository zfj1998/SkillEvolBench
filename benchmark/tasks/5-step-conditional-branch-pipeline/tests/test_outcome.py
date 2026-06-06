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

SOURCE = PROJECT / 'offers_pipeline.py'
OUTPUT = PROJECT / 'offers_output.json'


def _execute():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t2_pipeline', SOURCE)
    result = module.run(OUTPUT)
    saved = json.loads(OUTPUT.read_text(encoding='utf-8'))
    return result, saved, list(mock_api.TRACE)


def _rows_by_user():
    return {row['user_id']: row for row in _execute()[1]}


def run():
    public = run_checks('public', [
        ('three_results', lambda: len(_execute()[1]) == 3 or (_ for _ in ()).throw(AssertionError('expected three user rows'))),
        ('result_format', lambda: all({'user_id', 'status', 'offers', 'total_value'} <= set(row) for row in _execute()[1]) or (_ for _ in ()).throw(AssertionError('unexpected result format'))),
    ])
    hidden = run_checks('hidden', [
        ('premium_branch_user_1', lambda: any(item['endpoint'] == '/premium/offers' and item['user_id'] == 'user_1' for item in _execute()[2]) or (_ for _ in ()).throw(AssertionError('user_1 did not hit premium endpoint'))),
        ('standard_branch_user_2', lambda: any(item['endpoint'] == '/standard/offers' and item['user_id'] == 'user_2' for item in _execute()[2]) or (_ for _ in ()).throw(AssertionError('user_2 did not hit standard endpoint'))),
        ('premium_branch_user_3', lambda: any(item['endpoint'] == '/premium/offers' and item['user_id'] == 'user_3' for item in _execute()[2]) or (_ for _ in ()).throw(AssertionError('user_3 did not hit premium endpoint'))),
        ('no_wrong_premium_for_user_2', lambda: all(not (item['endpoint'] == '/premium/offers' and item['user_id'] == 'user_2') for item in _execute()[2]) or (_ for _ in ()).throw(AssertionError('user_2 incorrectly hit premium endpoint'))),
        ('no_wrong_standard_for_user_3', lambda: all(not (item['endpoint'] == '/standard/offers' and item['user_id'] == 'user_3') for item in _execute()[2]) or (_ for _ in ()).throw(AssertionError('user_3 incorrectly hit standard endpoint'))),
        ('branch_outputs_differ', lambda: _rows_by_user()['user_1']['offers'] != _rows_by_user()['user_2']['offers'] != _rows_by_user()['user_3']['offers'] or (_ for _ in ()).throw(AssertionError('branch outputs should differ by user status'))),
    ])
    return emit_report('E2-LS4-T2', public, hidden)


if __name__ == '__main__':
    print_report(run())
