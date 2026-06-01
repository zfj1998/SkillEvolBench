from routes.orders import create_order
from routes.products import create_product
from routes.reviews import create_review
from routes.users import create_user


def test_create_user_happy_path():
    response = create_user({"name": "Alice", "email": "alice@example.com", "age": 30})
    assert response["status"] == 200


def test_create_product_happy_path():
    response = create_product({"title": "Book", "price": 12.5, "category": "book"})
    assert response["status"] == 200


def test_create_order_happy_path():
    response = create_order({"user_id": 1, "product_ids": [10, 11], "quantity": 2})
    assert response["status"] == 200


def test_create_review_happy_path():
    response = create_review({"user_id": 1, "product_id": 10, "rating": 5, "comment": "great"})
    assert response["status"] == 200
