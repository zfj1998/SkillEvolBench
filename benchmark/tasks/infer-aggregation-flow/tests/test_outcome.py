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

SOURCE = PROJECT / 'aggregation.py'
OUTPUT = PROJECT / 'summary.json'
EXPECTED = {
    'hardware': 2190.0,
    'software': 2150.0,
    'services': 1580.0,
}


def _execute():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t4_aggregation', SOURCE)
    result = module.run(OUTPUT)
    saved = json.loads(OUTPUT.read_text(encoding='utf-8'))
    return result, saved, list(mock_api.TRACE)


def _line_map():
    return {line['product_line']: line['total_usd'] for line in _execute()[1]['lines']}


def run():
    public = run_checks('public', [])
    hidden = run_checks('hidden', [
        ('all_region_apis_called', lambda: {item['endpoint'] for item in _execute()[2]} == {'/sales/us', '/sales/eu', '/sales/apac'} or (_ for _ in ()).throw(AssertionError(f'incomplete source coverage: {_execute()[2]}'))),
        ('currency_normalized', lambda: _execute()[1]['currency'] == 'USD' or (_ for _ in ()).throw(AssertionError('summary currency should be USD'))),
        ('grouped_by_product_line', lambda: _line_map() == EXPECTED or (_ for _ in ()).throw(AssertionError(f'aggregated totals mismatch: {_line_map()}'))),
        ('grand_total_correct', lambda: abs(_execute()[1]['grand_total_usd'] - sum(EXPECTED.values())) < 1e-9 or (_ for _ in ()).throw(AssertionError('grand total mismatch'))),
    ])
    return emit_report('E2-LS4-T4', public, hidden)


if __name__ == '__main__':
    print_report(run())
