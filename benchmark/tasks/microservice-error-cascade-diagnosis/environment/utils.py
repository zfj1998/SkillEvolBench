"""Utility functions for ProfileHub."""

from datetime import datetime


def format_timestamp(dt: datetime = None) -> str:
    """Format a datetime as ISO 8601."""
    return (dt or datetime.now()).strftime('%Y-%m-%dT%H:%M:%S')


def sanitize_string(s: str) -> str:
    """Basic input sanitization."""
    return s.strip()[:500]


def mask_email(email: str) -> str:
    """Mask an email address for display: alice@example.com → a***@example.com"""
    if '@' not in email:
        return email
    local, domain = email.split('@', 1)
    return f'{local[0]}***@{domain}' if local else f'***@{domain}'


def build_response(status: str, data: dict = None, error: str = None) -> dict:
    """Build a standard response envelope."""
    resp = {'status': status, 'timestamp': format_timestamp()}
    if data is not None:
        resp['data'] = data
    if error is not None:
        resp['error'] = error
    return resp
