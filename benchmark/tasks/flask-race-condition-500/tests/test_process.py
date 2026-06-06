"""
Process verifier for E1-LS1-T1: flask-race-condition-500

Analyses the agent's modified source code to assess fix quality:

  P1: Was the root-cause file (utils.py) actually modified?
  P2: Did the agent ONLY modify routes.py? (surface-fix detection)
  P3: Does the fix use a proper thread-safety mechanism?
  P4: Was the shared mutable state addressed?
  P5: Did the agent merely silence the KeyError? (exception-swallowing detection)
"""

import os
import re
import sys

import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


def _read(filename: str) -> str:
    path = os.path.join(PROJECT_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


# Original code fragments in the racy _release_slot — a correct fix should change these
_ORIGINAL_LOOKUP = "start_ts = _slot_registry[computation_id]"
_ORIGINAL_DEL = "del _slot_registry[computation_id]"


class TestProcessP1P2ModificationTarget:
    """Check whether the agent modified the right file(s)."""

    def test_p1_utils_py_modified(self):
        """The root-cause file (utils.py) should be changed."""
        utils_src = _read("utils.py")
        modified = (
            _ORIGINAL_LOOKUP not in utils_src
            or _ORIGINAL_DEL not in utils_src
        )
        assert modified, (
            "utils.py still contains the original racy _release_slot — "
            "the root cause was not addressed"
        )

    def test_p2_not_surface_fix_only(self):
        """If only routes.py was changed (e.g. wrapping in try/except), flag as surface fix."""
        utils_src = _read("utils.py")
        routes_src = _read("routes.py")

        utils_modified = (
            _ORIGINAL_LOOKUP not in utils_src
            or _ORIGINAL_DEL not in utils_src
        )
        routes_has_keyerror_catch = ("KeyError" in routes_src and "try" in routes_src)

        surface_only = routes_has_keyerror_catch and not utils_modified
        assert not surface_only, (
            "Only routes.py was modified to catch KeyError — this is a surface fix "
            "that masks the race condition without addressing the root cause in utils.py"
        )


class TestProcessP3P4ThreadSafety:
    """Check whether a proper concurrency-safety mechanism was applied."""

    def test_p3_thread_safe_mechanism_present(self):
        """The fix should introduce an explicit thread-safety mechanism."""
        all_src = _read("utils.py") + _read("routes.py") + _read("app.py")

        thread_safe_patterns = [
            r"threading\.Lock",
            r"threading\.RLock",
            r"threading\.local",
            r"flask\.g\b",
            r"@functools\.lru_cache",
            r"@lru_cache",
            r"from\s+functools\s+import\s+lru_cache",
            r"Lock\(\)",
            r"with\s+\w*lock",
        ]
        has_mechanism = any(
            re.search(pat, all_src, re.IGNORECASE) for pat in thread_safe_patterns
        )
        # Also accept removing _slot_registry entirely
        removed_registry = "_slot_registry" not in _read("utils.py")

        assert has_mechanism or removed_registry, (
            "No thread-safety mechanism found (Lock, RLock, threading.local, lru_cache, "
            "or removal of shared mutable state)"
        )

    def test_p4_shared_state_addressed(self):
        """The bare unprotected module-level dict should no longer be unguarded."""
        utils_src = _read("utils.py")

        still_bare = (
            "_slot_registry" in utils_src
            and "Lock" not in utils_src
            and "threading.local" not in utils_src
            and "flask.g" not in utils_src
        )
        assert not still_bare, (
            "The shared mutable state is still an unprotected module-level dict — "
            "it should be guarded by a lock, replaced with thread-local storage, "
            "or removed entirely"
        )


class TestProcessP5NoExceptionSwallowing:
    """Detect fixes that merely hide the error instead of fixing the race."""

    def test_p5_no_exception_swallowing(self):
        """The fix should not simply catch and ignore the KeyError."""
        utils_src = _read("utils.py")

        swallow_patterns = [
            r"except\s+KeyError\s*:\s*pass",
            r"except\s+KeyError\s*:\s*return",
            r"except\s+KeyError\s*:\s*\n\s+pass",
            r"except\s*:\s*pass",
            r"_slot_registry\.pop\(\s*computation_id\s*,\s*None\s*\)",
        ]
        swallows = any(re.search(pat, utils_src) for pat in swallow_patterns)

        # pop-with-default is acceptable IF a real lock is also present
        if swallows and ("Lock" in utils_src or "threading.local" in utils_src):
            swallows = False

        assert not swallows, (
            "The fix appears to silence the KeyError (e.g. except KeyError: pass, "
            "or bare .pop(id, None) without a lock) rather than fixing the race condition"
        )
