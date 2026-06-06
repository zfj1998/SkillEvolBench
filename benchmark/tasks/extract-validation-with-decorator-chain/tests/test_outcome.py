from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from verifier_lib.runtime import emit_report, print_report, run_checks
from routes.orders import create_order
from routes.products import create_product
from routes.reviews import create_review
from routes.users import create_user


def run():
    public = run_checks(
        "public",
        [
            ("user_happy_path", lambda: create_user({"name": "Alice", "email": "alice@example.com", "age": 30})["status"] == 200 or (_ for _ in ()).throw(AssertionError("user should succeed"))),
            ("product_happy_path", lambda: create_product({"title": "Book", "price": 9.9, "category": "book"})["status"] == 200 or (_ for _ in ()).throw(AssertionError("product should succeed"))),
            ("order_happy_path", lambda: create_order({"user_id": 1, "product_ids": [1], "quantity": 2})["status"] == 200 or (_ for _ in ()).throw(AssertionError("order should succeed"))),
            ("review_happy_path", lambda: create_review({"user_id": 1, "product_id": 2, "rating": 5})["status"] == 200 or (_ for _ in ()).throw(AssertionError("review should succeed"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("missing_required_field", lambda: create_user({"email": "alice@example.com"})["status"] == 400 or (_ for _ in ()).throw(AssertionError("missing name should fail"))),
            ("invalid_email", lambda: create_user({"name": "Alice", "email": "bad"})["status"] == 400 or (_ for _ in ()).throw(AssertionError("invalid email should fail"))),
            ("product_category_enum", lambda: create_product({"title": "Book", "price": 9.9, "category": "invalid"})["status"] == 400 or (_ for _ in ()).throw(AssertionError("invalid category should fail"))),
            ("order_quantity_range", lambda: create_order({"user_id": 1, "product_ids": [1], "quantity": 101})["status"] == 400 or (_ for _ in ()).throw(AssertionError("quantity out of range should fail"))),
            ("user_age_lower_bound", lambda: create_user({"name": "Alice", "email": "alice@example.com", "age": -1})["status"] == 400 or (_ for _ in ()).throw(AssertionError("age lower bound should fail"))),
            ("review_rating_upper_bound", lambda: create_review({"user_id": 1, "product_id": 2, "rating": 6})["status"] == 400 or (_ for _ in ()).throw(AssertionError("rating upper bound should fail"))),
            ("review_optional_type", lambda: create_review({"user_id": 1, "product_id": 2, "rating": 5, "comment": 123})["status"] == 400 or (_ for _ in ()).throw(AssertionError("comment type should fail"))),
            ("optional_fields_can_be_omitted", lambda: create_review({"user_id": 1, "product_id": 2, "rating": 5})["status"] == 200 or (_ for _ in ()).throw(AssertionError("optional comment should be omittable"))),
            ("uniform_error_shape", lambda: {"field", "message"} <= create_product({"title": "Book", "price": 0, "category": "book"})["error"].keys() or (_ for _ in ()).throw(AssertionError("error payload shape changed"))),
        ],
    )
    return emit_report("E1-LS3-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
