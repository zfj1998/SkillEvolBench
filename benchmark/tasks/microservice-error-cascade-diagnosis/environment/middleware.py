"""Request middleware for ProfileHub."""

import sys
from datetime import datetime


_request_log = []


def log_request(method: str, path: str) -> None:
    """Log an incoming request."""
    entry = {
        'method': method,
        'path': path,
        'timestamp': datetime.now().isoformat(),
    }
    _request_log.append(entry)


def validate_content_type(headers: dict, expected: str = 'application/json') -> bool:
    """Check Content-Type header."""
    ct = headers.get('Content-Type', headers.get('content-type', ''))
    return expected in ct


def get_request_log() -> list:
    return list(_request_log)


def clear_request_log() -> None:
    _request_log.clear()
