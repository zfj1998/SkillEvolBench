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

SOURCE = PROJECT / 'latest_data.py'
OUTPUT = PROJECT / 'latest_data.json'


def _execute():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t5_latest_data', SOURCE)
    result = module.run(OUTPUT)
    saved = json.loads(OUTPUT.read_text(encoding='utf-8'))
    return result, saved, list(mock_api.TRACE)


def run():
    public = run_checks('public', [
        ('data_saved', lambda: OUTPUT.exists() if _execute() else (_ for _ in ()).throw(AssertionError('latest_data.json missing'))),
        ('format_valid', lambda: {'version', 'records'} <= set(_execute()[1]) or (_ for _ in ()).throw(AssertionError('unexpected output shape'))),
    ])
    hidden = run_checks('hidden', [
        ('latest_year_data', lambda: all(record['date'].startswith('2024') for record in _execute()[1]['records']) or (_ for _ in ()).throw(AssertionError('output still uses stale 2023 data'))),
        ('uses_v2_endpoint', lambda: any(item['endpoint'].startswith('/v2/data') for item in _execute()[2]) or (_ for _ in ()).throw(AssertionError('trace missing v2 endpoint call'))),
        ('no_v1_after_config', lambda: all(not item['endpoint'].startswith('/v1/data') for item in _execute()[2][1:]) or (_ for _ in ()).throw(AssertionError('trace still uses old v1 endpoint after config'))),
    ])
    return emit_report('E2-LS4-T5', public, hidden)


if __name__ == '__main__':
    print_report(run())
