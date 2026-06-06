"""Outcome verifier for E1-LS1-T6."""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..', 'project')
sys.path.insert(0, PROJECT_DIR)

import db_client


@pytest.fixture(autouse=True)
def reset():
    db_client.reset_connection()
    yield
    db_client.reset_connection()


def _login(user='alice', pwd='alice_pass_123'):
    from api_gateway import handle_request
    _, body = handle_request('POST', '/api/login', body={'username': user, 'password': pwd})
    return body.get('token')


class TestPublic:
    def test_p1_login_profile_success(self):
        from api_gateway import handle_request
        token = _login()
        code, body = handle_request('GET', '/api/profile', headers={'Authorization': f'Bearer {token}'})
        assert code == 200
        profile = body.get('profile', {})
        assert profile.get('display_name')
        assert profile.get('email')

    def test_p2_wrong_password_401(self):
        from api_gateway import handle_request
        code, _ = handle_request('POST', '/api/login', body={'username': 'alice', 'password': 'wrong'})
        assert code == 401

    def test_p2_missing_login_fields_400(self):
        from api_gateway import handle_request
        for body in ({'username': 'alice'}, {'password': 'alice_pass_123'}, {}):
            code, _ = handle_request('POST', '/api/login', body=body)
            assert code == 400

    def test_p3_nonexistent_user_404(self):
        from api_gateway import handle_request
        token = _login()
        code, body = handle_request('GET', '/api/profile/999', headers={'Authorization': f'Bearer {token}'})
        assert code == 404
        assert body == {'error': 'user not found'}


class TestHidden:
    def test_h1_special_char_password_connection(self):
        from api_gateway import handle_request
        token = _login()
        code, body = handle_request('GET', '/api/profile', headers={'Authorization': f'Bearer {token}'})
        assert code == 200
        assert body['profile']['display_name'] == 'Alice Zhang'

    def test_h2_db_timeout_not_200_blank(self):
        from api_gateway import handle_request
        token = _login()
        with patch('db_client.fetch_user_profile', side_effect=db_client.OperationalError('timeout')):
            code, body = handle_request('GET', '/api/profile', headers={'Authorization': f'Bearer {token}'})
        is_blank = body.get('profile') == {} or body.get('has_profile') is False
        assert code in (500, 503)
        assert not is_blank

    def test_h3_not_found_semantics(self):
        from api_gateway import handle_request
        token = _login()
        code, body = handle_request('GET', '/api/profile/999', headers={'Authorization': f'Bearer {token}'})
        assert code == 404
        assert body == {'error': 'user not found'}

    def test_h4_concurrent_requests(self):
        from api_gateway import handle_request
        token = _login()
        headers = {'Authorization': f'Bearer {token}'}
        def one_call(_):
            code, body = handle_request('GET', '/api/profile', headers=headers)
            return code, body['profile']['display_name']
        with ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(one_call, range(10)))
        assert all(code == 200 and name == 'Alice Zhang' for code, name in results)

    def test_h5_connection_string_legal_url(self):
        from config import get_connection_string
        from urllib.parse import urlparse, unquote_plus
        parsed = urlparse(get_connection_string())
        assert parsed.scheme == 'postgresql'
        assert parsed.hostname == 'localhost'
        assert parsed.port == 5432
        assert parsed.username == 'app_user'
        assert unquote_plus(parsed.password or '') == 'p@ss#word!$'

    def test_h6_operational_error_not_empty_dict(self):
        from user_service import get_user_profile
        with patch('db_client.fetch_user_profile', side_effect=db_client.OperationalError('db down')):
            with pytest.raises(db_client.OperationalError):
                get_user_profile(1)
