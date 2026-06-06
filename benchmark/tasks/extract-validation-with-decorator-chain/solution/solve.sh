#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

mkdir -p routes

python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('routes/shared.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('import re\nfrom functools import wraps\n\nEMAIL_RE = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")\nALLOWED_CATEGORIES = {"book", "toy", "food"}\n\n\ndef ok(data):\n    return {"status": 200, "data": data}\n\n\ndef bad_request(field, message):\n    return {"status": 400, "error": {"field": field, "message": message}}\n\n\ndef validated(handler):\n    @wraps(handler)\n    def wrapper(payload):\n        return handler(payload)\n\n    return wrapper\n', encoding='utf-8')
PYWRITE_1

python3 - <<'PYWRITE_2'
from pathlib import Path
target = Path('routes/users.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('from .shared import EMAIL_RE, bad_request as fail, ok, validated\n\n\n@validated\ndef create_user(payload):\n    required = {\n        "name": (str, "name is required", "name must be a string"),\n        "email": (str, "email is required", "email must be a string"),\n    }\n    for field, (expected_type, missing_message, type_message) in required.items():\n        if field not in payload or not payload[field]:\n            return fail(field, missing_message)\n        if not isinstance(payload[field], expected_type):\n            return fail(field, type_message)\n    if not EMAIL_RE.match(payload["email"]):\n        return fail("email", "email format is invalid")\n    if "age" in payload and payload["age"] is not None:\n        if not isinstance(payload["age"], int):\n            return fail("age", "age must be an integer")\n        if payload["age"] < 0 or payload["age"] > 150:\n            return fail("age", "age must be between 0 and 150")\n    return ok({"kind": "user", "payload": payload})\n', encoding='utf-8')
PYWRITE_2

python3 - <<'PYWRITE_3'
from pathlib import Path
target = Path('routes/products.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('from .shared import ALLOWED_CATEGORIES, bad_request as fail, ok, validated\n\n\n@validated\ndef create_product(payload):\n    checks = [\n        ("title", lambda value: isinstance(value, str) and bool(value), "title is required", "title must be a string"),\n        ("price", lambda value: isinstance(value, (int, float)), "price is required", "price must be numeric"),\n        ("category", lambda value: isinstance(value, str) and bool(value), "category is required", "category must be a string"),\n    ]\n    for field, validator, missing_message, type_message in checks:\n        if field not in payload or payload[field] in (None, ""):\n            return fail(field, missing_message)\n        if not validator(payload[field]):\n            return fail(field, type_message)\n    if payload["price"] <= 0:\n        return fail("price", "price must be greater than zero")\n    if payload["category"] not in ALLOWED_CATEGORIES:\n        return fail("category", "category is invalid")\n    return ok({"kind": "product", "payload": payload})\n', encoding='utf-8')
PYWRITE_3

python3 - <<'PYWRITE_4'
from pathlib import Path
target = Path('routes/orders.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('from .shared import bad_request as fail, ok, validated\n\n\n@validated\ndef create_order(payload):\n    validators = [\n        ("user_id", lambda value: isinstance(value, int), "user_id is required", "user_id must be an integer"),\n        ("product_ids", lambda value: isinstance(value, list) and bool(value), "product_ids is required", "product_ids must be a non-empty list"),\n        ("quantity", lambda value: isinstance(value, int), "quantity is required", "quantity must be an integer"),\n    ]\n    for field, validator, missing_message, type_message in validators:\n        if field not in payload:\n            return fail(field, missing_message)\n        if not validator(payload[field]):\n            return fail(field, type_message)\n    if payload["quantity"] < 1 or payload["quantity"] > 100:\n        return fail("quantity", "quantity must be between 1 and 100")\n    return ok({"kind": "order", "payload": payload})\n', encoding='utf-8')
PYWRITE_4

python3 - <<'PYWRITE_5'
from pathlib import Path
target = Path('routes/reviews.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('from .shared import bad_request as fail, ok, validated\n\n\n@validated\ndef create_review(payload):\n    validators = [\n        ("user_id", lambda value: isinstance(value, int), "user_id is required", "user_id must be an integer"),\n        ("product_id", lambda value: isinstance(value, int), "product_id is required", "product_id must be an integer"),\n        ("rating", lambda value: isinstance(value, int), "rating is required", "rating must be an integer"),\n    ]\n    for field, validator, missing_message, type_message in validators:\n        if field not in payload:\n            return fail(field, missing_message)\n        if not validator(payload[field]):\n            return fail(field, type_message)\n    if payload["rating"] < 1 or payload["rating"] > 5:\n        return fail("rating", "rating must be between 1 and 5")\n    if "comment" in payload and payload["comment"] is not None:\n        if not isinstance(payload["comment"], str):\n            return fail("comment", "comment must be a string")\n        if len(payload["comment"]) > 1000:\n            return fail("comment", "comment is too long")\n    return ok({"kind": "review", "payload": payload})\n', encoding='utf-8')
PYWRITE_5
