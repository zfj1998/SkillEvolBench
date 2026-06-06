import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "hidden: hidden verifier test (not visible to agent)")
