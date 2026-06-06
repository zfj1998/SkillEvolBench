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

SOURCE = PROJECT / 'workflow.py'
OUTPUT = PROJECT / 'output.json'


def _execute():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t1_workflow', SOURCE)
    result = module.run(OUTPUT)
    saved = json.loads(OUTPUT.read_text(encoding='utf-8'))
    return result, saved, list(mock_api.TRACE)


def run():
    public = run_checks('public', [
        ('output_exists', lambda: _execute()[1] and OUTPUT.exists() or (_ for _ in ()).throw(AssertionError('output.json missing'))),
        ('five_rows_saved', lambda: len(_execute()[1]) == 5 or (_ for _ in ()).throw(AssertionError(f'expected 5 rows, got {len(_execute()[1])}'))),
    ])
    hidden = run_checks('hidden', [
        ('details_complete', lambda: all({'id', 'name', 'category', 'score', 'source'} <= set(row) for row in _execute()[1]) or (_ for _ in ()).throw(AssertionError('missing detail fields'))),
        ('bearer_token_used', lambda: all(call['headers'].get('Authorization') == f'Bearer {mock_api.TOKEN}' for call in _execute()[2] if call['endpoint'] != '/auth') or (_ for _ in ()).throw(AssertionError('bearer token missing from downstream calls'))),
        ('no_401', lambda: all(call['status'] != 401 for call in _execute()[2]) or (_ for _ in ()).throw(AssertionError('saw unauthorized request in trace'))),
        ('no_429', lambda: all(call['status'] != 429 for call in _execute()[2]) or (_ for _ in ()).throw(AssertionError('detail endpoint hit rate limit'))),
    ])
    return emit_report('E2-LS4-T1', public, hidden)


if __name__ == '__main__':
    print_report(run())
