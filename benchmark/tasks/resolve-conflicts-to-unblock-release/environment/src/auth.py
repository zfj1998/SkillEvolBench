"""Authentication module."""
import hashlib
import time

<<<<<<< HEAD
def authenticate(username, password):
    """Authenticate user - hotfix: added rate limiting."""
    if not _check_rate_limit(username):
        return {"success": False, "error": "Too many attempts. Please wait."}

    user = _find_user(username)
    if not user:
        return {"success": False, "error": "Invalid credentials"}

    if _verify_password(password, user["password_hash"]):
        return {"success": True, "token": _generate_token(user)}
    return {"success": False, "error": "Invalid credentials"}


def _check_rate_limit(username):
    """Rate limit check - added in hotfix v2.0.1."""
    # Simple in-memory rate limiting (simplified for fixture)
    return True
=======
def authenticate(username, password, remember_me=False):
    """Authenticate user - new: added remember_me option."""
    user = _find_user(username)
    if not user:
        return {"success": False, "error": "Invalid credentials"}

    if _verify_password(password, user["password_hash"]):
        token = _generate_token(user, long_lived=remember_me)
        return {"success": True, "token": token, "remember_me": remember_me}
    return {"success": False, "error": "Invalid credentials"}
>>>>>>> develop


def _find_user(username):
    """Find user in database."""
    USERS = {
        "admin": {"id": 1, "username": "admin",
                  "password_hash": hashlib.sha256(b"admin123").hexdigest()},
        "user1": {"id": 2, "username": "user1",
                  "password_hash": hashlib.sha256(b"pass456").hexdigest()},
    }
    return USERS.get(username)


def _verify_password(password, password_hash):
    """Verify password against hash."""
    return hashlib.sha256(password.encode()).hexdigest() == password_hash


def _generate_token(user, long_lived=False):
    """Generate authentication token."""
    expiry = 86400 * 30 if long_lived else 3600
    return f"token_{user['id']}_{int(time.time())}_{expiry}"
