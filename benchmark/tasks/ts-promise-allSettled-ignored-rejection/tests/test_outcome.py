"""
Outcome verifier for E1-LS1-T3: ts-promise-allSettled-ignored-rejection
"""

import json, os, subprocess, tempfile
import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..', 'project')

def _run(period='2025-05', timeout=200):
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        out = f.name
    r = subprocess.run(
        ['npx', '--no-install', 'ts-node', '--transpile-only', 'src/index.ts',
         '--period', period, '--timeout', str(timeout), '--output', out],
        cwd=PROJECT_DIR, capture_output=True, text=True, timeout=30)
    report = None
    if os.path.exists(out):
        try:
            with open(out) as f: report = json.load(f)
        except Exception: pass
        os.unlink(out)
    return r.returncode, r.stdout, r.stderr, report


class TestPublic:

    def test_p1_all_succeed_nonzero(self):
        _, _, _, rpt = _run(timeout=500)
        assert rpt and len(rpt['sections']) == 5
        for s in rpt['sections']:
            assert s['value'] > 0, f"{s['source']} is zero when all sources succeed"

    def test_p2_structure_valid(self):
        _, _, _, rpt = _run(timeout=500)
        assert rpt
        for k in ('title', 'sections', 'meta'): assert k in rpt
        assert rpt['meta']['sources_requested'] == 5
        required = {
            'source', 'label', 'value', 'display_value', 'unit',
            'breakdown', 'status', 'provenance', 'notes', 'collected_at',
        }
        assert {s['source'] for s in rpt['sections']} == {
            'user_stats', 'orders', 'inventory', 'reviews', 'traffic',
        }
        for s in rpt['sections']:
            assert required.issubset(s.keys()), (
                f"{s.get('source', '<unknown>')} missing schema fields")
            assert s['status'] == 'ok', (
                f"{s['source']} should be status='ok' when all sources succeed")

    def test_p3_failed_source_not_status_ok(self):
        _, _, _, rpt = _run(timeout=200)
        assert rpt
        for s in rpt['sections']:
            if s['source'] in ('inventory', 'reviews'):
                assert s['status'] != 'ok', (
                    f"{s['source']} timed out but still status='ok'")


class TestHiddenCorefix:

    def test_h1_failed_sources_not_ok(self):
        _, _, _, rpt = _run(timeout=200)
        assert rpt
        for sid in ('inventory', 'reviews'):
            sec = next((s for s in rpt['sections'] if s['source'] == sid), None)
            assert sec, f'{sid} section missing'
            assert sec['status'] != 'ok'

    def test_h2_all_fail_no_crash(self):
        code, _, _, rpt = _run(timeout=1)
        assert code == 0 and rpt is not None

    def test_h3_failure_metadata_present(self):
        _, _, stderr, rpt = _run(timeout=200)
        has_stderr = any(w in stderr.lower() for w in ('warn', 'timeout', 'fail'))
        has_meta = rpt and rpt['meta'].get('recoverable_failures', 0) > 0
        has_log = rpt and len(rpt['meta'].get('failure_log', [])) > 0
        has_notes = rpt and any(
            len(s.get('notes', [])) > 0
            for s in rpt['sections'] if s['source'] in ('inventory', 'reviews')
        )
        assert has_stderr or has_meta or has_log or has_notes, (
            'No failure metadata: stderr, recoverable_failures, failure_log, or notes')

    def test_h4_no_misleading_zero_ok(self):
        _, _, _, rpt = _run(timeout=200)
        assert rpt
        for s in rpt['sections']:
            if s['source'] in ('inventory', 'reviews'):
                assert not (s['value'] == 0 and s['status'] == 'ok'), (
                    f"{s['source']}: value=0+status=ok is misleading")


class TestHiddenIsolation:

    def test_h5_fulfilled_unaffected(self):
        _, _, _, r_all = _run(timeout=500)
        _, _, _, r_part = _run(timeout=200)
        assert r_all and r_part
        for sid in ('user_stats', 'orders', 'traffic'):
            v1 = next(s['value'] for s in r_all['sections'] if s['source'] == sid)
            v2 = next(s['value'] for s in r_part['sections'] if s['source'] == sid)
            assert v1 == v2

    def test_h6_no_crash_tiny_timeout(self):
        code, _, _, _ = _run(timeout=1)
        assert code == 0

    def test_h7_failure_count_matches(self):
        _, _, _, rpt = _run(timeout=200)
        assert rpt
        non_ok = sum(1 for s in rpt['sections'] if s['status'] != 'ok')
        reported = rpt['meta'].get('recoverable_failures', 0)
        assert non_ok == reported, f'sections non-ok={non_ok} but meta says {reported}'
