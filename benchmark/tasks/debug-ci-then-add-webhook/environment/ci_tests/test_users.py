"""Failing CI test 1: stale schema import after refactor."""

from app.models import UserSchema
from app.database import get_user


def test_user_schema_from_record_uses_new_schema():
    row = get_user(1)
    schema = UserSchema.from_record(row)
    payload = schema.to_api_dict()
    assert payload['display_name'] == 'alice'
    assert payload['email'] == 'alice@corp.io'
