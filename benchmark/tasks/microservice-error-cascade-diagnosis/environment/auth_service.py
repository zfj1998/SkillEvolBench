"""
Authentication service for ProfileHub.

Manages user credentials and session tokens.  Uses an in-memory
credential store for local development; production delegates to
the OAuth2 provider.
"""

import hashlib
import secrets
from typing import Optional

from config import TOKEN_PREFIX

# ── Credential store ─────────────────────────────────────────────────

_CREDENTIALS = {
    'alice':  hashlib.sha256(b'alice_pass_123').hexdigest(),
    'bob':    hashlib.sha256(b'bob_secure_456').hexdigest(),
    'carol':  hashlib.sha256(b'carol_secret_789').hexdigest(),
}

_USER_IDS = {'alice': 1, 'bob': 2, 'carol': 3}

# ── Active sessions ──────────────────────────────────────────────────

_sessions: dict = {}


def authenticate(username: str, password: str) -> Optional[str]:
    """
    Verify credentials and issue a session token.

    Returns the token string on success, None on failure.
    """
    expected = _CREDENTIALS.get(username)
    if expected is None:
        return None

    provided = hashlib.sha256(password.encode()).hexdigest()
    if provided != expected:
        return None

    token = TOKEN_PREFIX + secrets.token_hex(16)
    _sessions[token] = {
        'user_id': _USER_IDS[username],
        'username': username,
    }
    return token


def validate_token(token: str) -> Optional[int]:
    """Return the user_id for a valid token, or None."""
    session = _sessions.get(token)
    return session['user_id'] if session else None


def revoke_token(token: str) -> bool:
    """Revoke a session token. Returns True if it existed."""
    return _sessions.pop(token, None) is not None
