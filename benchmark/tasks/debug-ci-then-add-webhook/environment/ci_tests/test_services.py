"""Failing CI test 2: test assumes DATABASE_URL exists in CI."""

from app.services import get_active_users


def test_active_users_count():
    active = get_active_users()
    assert len(active) == 3
    assert {u['username'] for u in active} == {'alice', 'bob', 'dave'}
