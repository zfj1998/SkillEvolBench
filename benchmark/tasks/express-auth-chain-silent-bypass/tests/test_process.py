"""
Process verifier for E1-LS1-T2: express-auth-chain-silent-bypass

Analyses the agent's modified source files:

  P1: tokenValidator.js was modified (root cause file)
  P2: The catch fallthrough next() was replaced with a rejection
  P3: roleChecker.js was hardened (!req.user on protected → 401)
  P4: Only roleChecker changed, not tokenValidator → downstream-only flag
  P5: catch block sends 200 with error body → still leaks status code
"""

import os
import re

import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..', 'project')


def _read(relpath):
    path = os.path.join(PROJECT_DIR, relpath)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


# Original buggy fragments — these should be gone after a correct fix
_ORIGINAL_TV_FALLTHROUGH = 'Non-critical token issue'
_ORIGINAL_RC_PASSTHROUGH = 'No authenticated user context on this request'


class TestProcessP1P2TokenValidator:
    """Check whether tokenValidator.js was properly fixed."""

    def test_p1_token_validator_modified(self):
        """The root-cause file tokenValidator.js should be changed."""
        src = _read('middleware/tokenValidator.js')
        modified = _ORIGINAL_TV_FALLTHROUGH not in src
        assert modified, (
            'tokenValidator.js still contains the original catch fallthrough — '
            'the code path that silently calls next() for unrecognized token '
            'errors was not addressed'
        )

    def test_p2_catch_sends_rejection(self):
        """The catch block should now send a 401 response instead of calling next()."""
        src = _read('middleware/tokenValidator.js')

        # Find the catch block region
        # Look for patterns that indicate a proper rejection:
        #   res.statusCode = 401  /  res.status(401)  /  res.json({error:...})
        has_401_in_catch = bool(
            re.search(r'401', src)
            and (
                re.search(r'res\.statusCode\s*=\s*401', src)
                or re.search(r'res\.status\(\s*401\s*\)', src)
            )
        )

        # Also check that the fallthrough next() is gone
        # The original has 'next();' as the last line of the catch block
        # after the "authorization layer" comment
        fallthrough_gone = _ORIGINAL_TV_FALLTHROUGH not in src

        assert has_401_in_catch and fallthrough_gone, (
            'The catch block should reject with 401 instead of calling next(). '
            f'Has 401 response: {has_401_in_catch}, fallthrough removed: {fallthrough_gone}'
        )


class TestProcessP3RoleChecker:
    """Check whether roleChecker.js was defensively hardened."""

    def test_p3_role_checker_rejects_unauthenticated(self):
        """roleChecker.js should reject unauthenticated requests on protected routes."""
        src = _read('middleware/roleChecker.js')

        # The fix should: when !req.user AND route is protected → 401/403
        # Check for the pattern: !req.user combined with a status code response
        original_passthrough_gone = _ORIGINAL_RC_PASSTHROUGH not in src

        # Look for evidence of authentication check when !req.user
        has_auth_check = bool(
            re.search(r'!req\.user', src)
            and (
                re.search(r'40[13]', src)  # 401 or 403
                or re.search(r'[Aa]uthentication\s+required', src)
            )
        )

        assert original_passthrough_gone or has_auth_check, (
            'roleChecker.js should reject unauthenticated requests on protected '
            'routes instead of passing them through'
        )


class TestProcessP4DownstreamOnly:
    """Detect incomplete fix where only roleChecker was changed."""

    def test_p4_not_downstream_only_fix(self):
        """Changing only roleChecker without fixing tokenValidator is incomplete."""
        tv_src = _read('middleware/tokenValidator.js')
        rc_src = _read('middleware/roleChecker.js')

        tv_modified = _ORIGINAL_TV_FALLTHROUGH not in tv_src
        rc_modified = _ORIGINAL_RC_PASSTHROUGH not in rc_src

        downstream_only = rc_modified and not tv_modified

        assert not downstream_only, (
            'Only roleChecker.js was modified — this is a downstream band-aid. '
            'The root cause in tokenValidator.js (catch block calling next()) '
            'must also be fixed.'
        )


class TestProcessP5StatusCode:
    """Detect fixes that send error info with 200 status."""

    def test_p5_rejection_not_200(self):
        """The rejection response must NOT use status 200."""
        src = _read('middleware/tokenValidator.js')

        # Look for pattern: in catch block, res.status(200) or res.statusCode = 200
        # combined with error response
        sends_200_error = bool(
            re.search(r'res\.status\(\s*200\s*\)', src)
            or re.search(r'res\.statusCode\s*=\s*200', src)
        )

        # This is only a problem if it's in/near the catch block
        # (not in the success path where 200 is correct)
        # Rough heuristic: check if 200 appears after 'catch'
        catch_idx = src.find('catch')
        if catch_idx > 0:
            after_catch = src[catch_idx:]
            sends_200_in_catch = bool(
                re.search(r'res\.status\(\s*200\s*\)', after_catch)
                or re.search(r'statusCode\s*=\s*200', after_catch)
            )
        else:
            sends_200_in_catch = False

        assert not sends_200_in_catch, (
            'The catch block sends a 200 status with an error body — '
            'rejected requests must use 401 or 403, not 200'
        )
