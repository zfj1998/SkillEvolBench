"""
Process verifier for E1-LS1-T3

P1: reportGenerator.ts was modified (root cause file)
P2: baseline candidates now carry failure metadata (rejected→baseline without
    metadata pattern is broken)
P3: formatter no longer marks failed-source sections as status='ok'
"""

import os, re
import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..', 'project')

def _read(relpath):
    p = os.path.join(PROJECT_DIR, relpath)
    return open(p, encoding='utf-8').read() if os.path.exists(p) else ''

# Buggy pattern: baseline candidate has no failure field
_BUGGY_BASELINE = "kind: 'baseline' as const,\n      metrics: null,\n    };"


class TestProcessP1P2ReportGenerator:

    def test_p1_report_generator_modified(self):
        """The root-cause file must be changed."""
        rg = _read('src/reportGenerator.ts')
        assert _BUGGY_BASELINE not in rg, (
            'reportGenerator.ts still creates baseline candidates without '
            'failure metadata — rejected settlements are silently discarded'
        )

    def test_p2_failure_metadata_preserved(self):
        """Rejected settlement info must be carried forward, not discarded."""
        rg = _read('src/reportGenerator.ts')
        # The buggy baseline candidate is:
        #   { source, kind:'baseline', metrics:null }  — no failure field.
        # A correct fix must attach rejection info to the candidate.
        # Check that the baseline construction now includes failure data:
        has_failure_on_candidate = (
            # candidate object has a failure/reason field
            re.search(r'failure\s*:', rg) is not None
            or re.search(r'reason\s*:', rg) is not None
            # or accesses settlement.reason
            or '.reason' in rg
        )
        assert has_failure_on_candidate, (
            'reportGenerator.ts does not attach failure metadata to baseline '
            'candidates — rejected settlement reasons are discarded'
        )


class TestProcessP3Formatter:

    def test_p3_baseline_not_ok(self):
        """Formatter must not mark failed-source baselines as status='ok'."""
        fm = _read('src/formatter.ts')
        rg = _read('src/reportGenerator.ts')
        combined = rg + fm

        # Check that there's SOME mechanism to distinguish failed baselines
        # from genuine no-data baselines
        has_distinction = (
            'unavailable' in combined
            or 'failure' in fm.lower()
            or 'failed' in fm.lower()
            or re.search(r"status:\s*['\"](?!ok)[^'\"]+['\"]", fm)  # any non-ok status
        )
        assert has_distinction, (
            'formatter.ts still marks all non-live sections as status=ok '
            'with no way to distinguish actual failures from genuine baselines'
        )
