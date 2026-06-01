"""Backend error response helpers."""


def server_error_payload(message):
    return {"status": "error", "message": message, "data": None}


def not_found_payload():
    return {"status": "error", "message": "User not found", "data": None}
