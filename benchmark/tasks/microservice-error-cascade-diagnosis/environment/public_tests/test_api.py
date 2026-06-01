"""API integration tests for ProfileHub."""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import db_client
from api_gateway import handle_request


@pytest.fixture(autouse=True)
def reset_state():
    db_client.reset_connection()
    yield
    db_client.reset_connection()


def _login(user='alice', pwd='alice_pass_123'):
    _, body = handle_request('POST', '/api/login', body={'username': user, 'password': pwd})
    return body['token']


class TestPublicAPI:
    def test_login_and_profile_success(self):
        token = _login()
        code, body = handle_request('GET', '/api/profile', headers={'Authorization': f'Bearer {token}'})
        assert code == 200
        profile = body.get('profile', {})
        assert profile.get('display_name')
        assert profile.get('email')

    def test_wrong_password(self):
        code, _ = handle_request('POST', '/api/login', body={'username': 'alice', 'password': 'wrong'})
        assert code == 401

    def test_missing_login_fields_400(self):
        for body in ({'username': 'alice'}, {'password': 'alice_pass_123'}, {}):
            code, _ = handle_request('POST', '/api/login', body=body)
            assert code == 400

    def test_nonexistent_user_404(self):
        token = _login()
        code, body = handle_request('GET', '/api/profile/999', headers={'Authorization': f'Bearer {token}'})
        assert code == 404
        assert body == {'error': 'user not found'}
