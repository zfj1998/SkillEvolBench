"""Process verifier for E1-LS1-T4."""

import os

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..', 'project')


def _read(rel: str) -> str:
    path = os.path.join(PROJECT_DIR, rel)
    return open(path).read() if os.path.exists(path) else ''


class TestProcessP1AllFixed:
    def test_p1_three_bug_classes_fixed(self):
        users_test = _read('ci_tests/test_users.py')
        services_test = _read('ci_tests/test_services.py')
        utils_src = _read('app/utils.py')
        assert 'UserSchema' not in users_test
        assert 'patch.dict' in services_test
        assert 'return date_a < date_b' not in utils_src


class TestProcessP2ImportFix:
    def test_p2_correct_new_name_used(self):
        users_test = _read('ci_tests/test_users.py')
        assert 'UserResponseSchema' in users_test
        assert 'UserSchema = UserResponseSchema' not in users_test
        assert 'from app.models import UserResponseSchema' in users_test


class TestProcessP3DatabaseMock:
    def test_p3_uses_unittest_mock_patch(self):
        services_test = _read('ci_tests/test_services.py')
        assert 'from unittest.mock import patch' in services_test or 'import unittest.mock' in services_test
        assert 'patch.dict' in services_test or 'patch(' in services_test
        assert 'sqlite:///:memory:' in services_test


class TestProcessP4DateFix:
    def test_p4_uses_datetime_objects(self):
        src = _read('app/utils.py')
        idx = src.find('def is_before')
        end = src.find('\ndef ', idx + 1)
        tail = src[idx:end] if end != -1 else src[idx:]
        assert 'parse_date' in tail or 'datetime' in tail
        assert 'date_a < date_b' not in tail


class TestProcessP5Webhook:
    def test_p5_hmac_compare_digest(self):
        wh = _read('app/routers/webhooks.py')
        assert 'compare_digest' in wh
        assert 'NotImplementedError' not in wh
