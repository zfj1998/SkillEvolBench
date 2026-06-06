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

SOURCE = PROJECT / 'latest_data.py'
REGISTRY = PROJECT / 'endpoint_registry.py'
OUTPUT = PROJECT / 'latest_data.json'


def _run_trace():
    mock_api.reset_state()
    if OUTPUT.exists():
        OUTPUT.unlink()
    module = load_module('e2_ls4_t5_process', SOURCE)
    module.run(OUTPUT)
    return list(mock_api.TRACE)


def _extracts_endpoint_from_config():
    trace = _run_trace()
    assert trace[0]['endpoint'] == '/config', f'expected /config first, got {trace}'
    text = read_text(SOURCE)
    assert 'get_config' in text and 'resolve_data_endpoint' in text, 'source does not derive the endpoint from config payload'
    return 'config-driven endpoint present'


def _uses_current_endpoint():
    text = read_text(REGISTRY)
    assert 'data_endpoint' in text, 'registry should use the current endpoint field'
    assert 'deprecated_endpoint' not in text, 'registry should not prefer the deprecated endpoint'
    return 'current endpoint selected'


def run():
    public = run_checks('public', [('extracts_endpoint_from_config', _extracts_endpoint_from_config)])
    hidden = run_checks('hidden', [('uses_current_endpoint', _uses_current_endpoint)])
    return emit_report('E2-LS4-T5', public, hidden)


if __name__ == '__main__':
    print_report(run())
