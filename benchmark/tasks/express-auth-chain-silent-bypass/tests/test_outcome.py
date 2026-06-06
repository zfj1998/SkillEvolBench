"""
Outcome verifier for E1-LS1-T2: express-auth-chain-silent-bypass

Starts the Node.js server, runs HTTP requests, checks responses.

Public (P1-P4):  legitimate auth flows
Hidden (H1-H8):  bypass detection, role enforcement, data leakage, audit
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error

import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..', 'project')
PORT = 3399  # Use non-standard port to avoid conflicts


# ═══════════════════════════════════════════════════════════════════════
# Server management
# ═══════════════════════════════════════════════════════════════════════

_server_proc = None  # module-level ref for H7 log test

@pytest.fixture(scope='module')
def server():
    """Start the Node.js server and yield its base URL."""
    global _server_proc
    env = os.environ.copy()
    env['PORT'] = str(PORT)
    proc = subprocess.Popen(
        ['node', 'app.js'],
        cwd=PROJECT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _server_proc = proc
    # Wait for server to be ready
    base = f'http://127.0.0.1:{PORT}'
    for _ in range(30):
        time.sleep(0.2)
        try:
            urllib.request.urlopen(f'{base}/api/health', timeout=1)
            break
        except Exception:
            pass
    else:
        proc.kill()
        raise RuntimeError('Server failed to start')
    yield base
    os.kill(proc.pid, signal.SIGTERM)
    proc.wait(timeout=5)


def _sign_token(project_dir, payload_json):
    """Use the fixture's signToken to create a valid token."""
    script = f'''
    const t = require('./middleware/tokenValidator');
    console.log(t.signToken({payload_json}));
    '''
    result = subprocess.run(
        ['node', '-e', script],
        cwd=project_dir,
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip()


def _http(base, method, path, token=None):
    """Make an HTTP request and return (status, body_dict)."""
    url = base + path
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        body = json.loads(resp.read().decode())
        return resp.status, body
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode()) if e.readable() else {}
        return e.code, body


# ═══════════════════════════════════════════════════════════════════════
# Tokens
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='module')
def admin_token():
    return _sign_token(PROJECT_DIR, '{sub:1,role:"admin",username:"alice.chen"}')

@pytest.fixture(scope='module')
def viewer_token():
    return _sign_token(PROJECT_DIR, '{sub:3,role:"viewer",username:"carol"}')

@pytest.fixture(scope='module')
def analyst_token():
    return _sign_token(PROJECT_DIR, '{sub:2,role:"analyst",username:"bob"}')

@pytest.fixture(scope='module')
def expired_token():
    return _sign_token(PROJECT_DIR, '{sub:1,role:"admin",exp:1000000}')

CRAFTED_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOjEsInJvbGUiOiJhZG1pbiJ9.invalid+signature/with=padding'
MALFORMED_TOKEN = 'not-a-jwt-at-all'
EMPTY_PAYLOAD_TOKEN = 'eyJhbGciOiJIUzI1NiJ9..fakesig'


# ═══════════════════════════════════════════════════════════════════════
# Public tests (P1-P4) — visible to agent
# ═══════════════════════════════════════════════════════════════════════

class TestPublic:
    """Basic auth flow correctness — these are provided to the agent."""

    def test_p1_valid_admin_token_returns_200(self, server, admin_token):
        """A correctly signed admin token should access the admin endpoint."""
        status, body = _http(server, 'GET', '/api/admin/users', admin_token)
        assert status == 200
        assert body['count'] == 5

    def test_p2_no_token_returns_401(self, server):
        """A request without any Authorization header must be rejected."""
        status, body = _http(server, 'GET', '/api/admin/users')
        assert status == 401
        assert 'error' in body

    def test_p3_expired_token_returns_401(self, server, expired_token):
        """An expired token must be rejected."""
        status, body = _http(server, 'GET', '/api/admin/users', expired_token)
        assert status == 401

    def test_p4_wrong_signature_returns_401(self, server):
        """A token with an invalid but properly-formatted signature must be rejected."""
        # Create a token with valid structure but wrong HMAC
        bad_sig = _sign_token(PROJECT_DIR, '{sub:1,role:"admin"}')
        # Corrupt the last few characters of the signature
        bad_sig = bad_sig[:-4] + 'XXXX'
        status, body = _http(server, 'GET', '/api/admin/users', bad_sig)
        assert status == 401


# ═══════════════════════════════════════════════════════════════════════
# Hidden tests (H1-H8) — NOT visible to agent
# ═══════════════════════════════════════════════════════════════════════

class TestHiddenBypass:
    """Core bypass detection — the crafted token must be rejected."""

    def test_h1_crafted_padding_token_rejected(self, server):
        """A token with Base64 padding characters (+/=) must NOT return 200."""
        status, body = _http(server, 'GET', '/api/admin/users', CRAFTED_TOKEN)
        assert status != 200, (
            f'Bypass still works: crafted token returned {status} with '
            f'{body.get("count", "?")} user records'
        )

    def test_h2_malformed_token_rejected(self, server):
        """A completely malformed token string must NOT return 200."""
        status, body = _http(server, 'GET', '/api/admin/users', MALFORMED_TOKEN)
        assert status != 200, f'Malformed token returned {status}'

    def test_h3_empty_payload_token_rejected(self, server):
        """A token with an empty payload segment must NOT return 200."""
        status, body = _http(server, 'GET', '/api/admin/users', EMPTY_PAYLOAD_TOKEN)
        assert status != 200


class TestHiddenRoleEnforcement:
    """Role-based access control after fix."""

    def test_h4_viewer_cannot_access_admin(self, server, viewer_token):
        """A viewer-role token accessing the admin endpoint must get 403."""
        status, body = _http(server, 'GET', '/api/admin/users', viewer_token)
        assert status == 403
        assert {'error', 'code'} <= set(body)

    def test_h5_viewer_response_has_no_pii(self, server, viewer_token):
        """A viewer accessing /api/users must NOT see email/phone/ssn."""
        status, body = _http(server, 'GET', '/api/users', viewer_token)
        assert status == 200
        assert body.get('filtered') is True
        user = body['users'][0]
        assert 'ssn_last4' not in user, 'Viewer can see SSN'
        assert 'phone' not in user, 'Viewer can see phone'

    def test_h6_rejected_request_returns_error_not_data(self, server):
        """A rejected request's body must be an error message, not user data."""
        status, body = _http(server, 'GET', '/api/admin/users', CRAFTED_TOKEN)
        assert 'users' not in body, (
            f'Rejected response still contains user data ({body.get("count", "?")} records)'
        )
        assert {'error', 'code'} <= set(body)

    def test_h6b_analyst_gets_email_but_not_admin(self, server, analyst_token):
        status, body = _http(server, 'GET', '/api/users', analyst_token)
        assert status == 200
        assert body.get('filtered') is True
        assert 'email' in body['users'][0]
        assert 'phone' not in body['users'][0]

        status, body = _http(server, 'GET', '/api/admin/users', analyst_token)
        assert status == 403
        assert {'error', 'code'} <= set(body)


class TestHiddenAuxiliary:
    """Audit logging and middleware integrity."""

    def test_h7_invalid_token_produces_warning_log(self, server):
        """After fix, invalid token attempts should produce a warning on stderr."""
        import select
        import fcntl

        proc = _server_proc
        assert proc is not None, 'Server process not available'

        # Drain any previously buffered stderr
        fd = proc.stderr.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        try:
            while proc.stderr.read(4096):
                pass
        except (BlockingIOError, IOError):
            pass

        # Send crafted token to trigger the rejection path
        _http(server, 'GET', '/api/admin/users', CRAFTED_TOKEN)
        time.sleep(0.3)  # give server time to write log

        # Read stderr output
        stderr_output = b''
        try:
            while True:
                chunk = proc.stderr.read(4096)
                if not chunk:
                    break
                stderr_output += chunk
        except (BlockingIOError, IOError):
            pass
        finally:
            fcntl.fcntl(fd, fcntl.F_SETFL, fl)  # restore blocking mode

        log_text = stderr_output.decode('utf-8', errors='replace').lower()
        has_warning = 'warn' in log_text or 'rejected' in log_text or 'invalid token' in log_text
        assert has_warning, (
            f'Expected a warning log on stderr for rejected token, '
            f'but got: {stderr_output[:200]!r}'
        )

    def test_h8_rate_limiter_still_works(self, server, admin_token):
        """The fix must not break the rate limiter middleware."""
        status, body = _http(server, 'GET', '/api/admin/users', admin_token)
        assert status == 200
        assert body.get('includes_sensitive') is True
        # Health endpoint (public, no auth)
        status2, _ = _http(server, 'GET', '/api/health')
        assert status2 == 200

    def test_h9_version_endpoint_is_public_json(self, server):
        """The version endpoint documented as public should not require auth."""
        status, body = _http(server, 'GET', '/api/version')
        assert status == 200
        assert {'version', 'build', 'environment'} <= set(body)

    def test_h10_missing_claim_token_rejected(self, server):
        """A signed token missing required claims must still be rejected."""
        missing_role = _sign_token(PROJECT_DIR, '{sub:1,username:"alice.chen"}')
        status, body = _http(server, 'GET', '/api/admin/users', missing_role)
        assert status == 401
        assert {'error', 'code'} <= set(body)
        assert 'users' not in body and 'user' not in body
