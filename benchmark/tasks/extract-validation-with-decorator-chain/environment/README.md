# Fixture Plan: E1-LS3-T1

Role: `canonical`
Gap focus: `No gap exposure; the v0 skill should work.`

Scenario:
A FastAPI service contains four handlers with similar validation code. Each handler has different required fields and a few specialized checks, but the overall structure is duplicated.

Intended fixture files:
- `app.py`
- `routes/users.py`
- `routes/products.py`
- `routes/orders.py`
- `routes/reviews.py`
- `public_tests/test_handlers.py`

Key design notes:
The fixture should make the four handlers look similar but not identical. The shared abstraction must support required vs optional fields, type checks, ranges, enum checks, length checks, and email validation.

Public checks:
- All four handlers accept valid input and return success.
- The extracted abstraction does not break existing routes.
- Validation failures still produce HTTP 400.

Hidden checks:
- Missing required fields fail for all handlers.
- Wrong types fail for both required and optional fields.
- Boundary checks reject age=-1, price=0, quantity=101, rating=6.
- Email format and category enum validation remain intact.
- Optional fields may be omitted but still validate when present.

Process checks:
- Handlers now use a decorator or decorator factory.
- Validation logic exists in one parameterized abstraction rather than four copies.
- 400 error payload shape is consistent across handlers.
