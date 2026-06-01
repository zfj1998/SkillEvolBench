import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_CATEGORIES = {"book", "toy", "food"}


def ok(data):
    return {"status": 200, "data": data}


def bad_request(field, message):
    return {"status": 400, "error": {"field": field, "message": message}}
