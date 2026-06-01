"""Shared test fixtures."""
import pytest
from app.database import clear_events


@pytest.fixture(autouse=True)
def reset_events():
    """Clear event store between tests."""
    clear_events()
    yield
    clear_events()
