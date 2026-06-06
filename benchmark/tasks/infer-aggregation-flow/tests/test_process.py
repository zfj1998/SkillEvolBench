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
from verifier_lib.runtime import emit_report, load_module, print_report, read_text, run_checks

SOURCE = PROJECT / 'aggregation.py'
REGISTRY = PROJECT / 'source_registry.py'
OUTPUT = PROJECT / 'summary.json'


def _run_trace():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t4_process', SOURCE)
    module.run(OUTPUT)
    return list(mock_api.TRACE)


def _reads_regions_json():
    text = read_text(SOURCE)
    assert 'regions.json' in text, 'source does not read regions.json'
    return 'regions.json referenced'


def _hits_all_regions():
    endpoints = {item['endpoint'] for item in _run_trace()}
    assert endpoints == {'/sales/us', '/sales/eu', '/sales/apac'}, f'missing region call: {endpoints}'
    return sorted(endpoints)


def _has_currency_conversion():
    text = read_text(SOURCE)
    assert 'exchange_rates.json' in text or 'to_usd' in text, 'missing explicit currency conversion logic'
    return 'currency conversion present'


def _registry_uses_enabled_sources():
    text = read_text(REGISTRY)
    assert 'enabled' in text, 'source registry should respect enabled sources'
    assert "lane') == 'primary'" not in text and 'lane") == "primary"' not in text, 'source registry should not silently drop secondary enabled feeds'
    return 'registry uses enabled sources'


def run():
    public = run_checks('public', [('reads_regions_json', _reads_regions_json)])
    hidden = run_checks('hidden', [('hits_all_regions', _hits_all_regions), ('has_currency_conversion', _has_currency_conversion), ('registry_uses_enabled_sources', _registry_uses_enabled_sources)])
    return emit_report('E2-LS4-T4', public, hidden)


if __name__ == '__main__':
    print_report(run())
