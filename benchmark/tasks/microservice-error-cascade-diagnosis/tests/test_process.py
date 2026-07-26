"""Process verifier for E1-LS1-T6."""

import os
import sys
from urllib.parse import unquote_plus, urlparse
from unittest.mock import patch

import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..', 'project')
sys.path.insert(0, PROJECT_DIR)

import db_client


def _read(rel: str) -> str:
    path = os.path.join(PROJECT_DIR, rel)
    return open(path).read() if os.path.exists(path) else ''


class TestProcessP1:
    def test_p1_four_core_files_modified(self):
        from api_gateway import handle_request
        from config import get_connection_string

        parsed = urlparse(get_connection_string())
        assert parsed.scheme == 'postgresql'
        assert unquote_plus(parsed.password or '') == 'p@ss#word!$'
        code, body = handle_request(
            'POST', '/api/login',
            body={'username': 'alice', 'password': 'alice_pass_123'},
        )
        assert code == 200 and body.get('token')


class TestProcessP2:
    def test_p2_config_uses_quote_plus(self):
        from config import get_connection_string
        parsed = urlparse(get_connection_string())
        assert parsed.hostname == 'localhost'
        assert parsed.port == 5432
        assert unquote_plus(parsed.password or '') == 'p@ss#word!$'


class TestProcessP3:
    def test_p3_user_service_no_silent_empty_return(self):
        from user_service import get_user_profile
        with patch(
            'db_client.fetch_user_profile',
            side_effect=db_client.OperationalError('db down'),
        ):
            with pytest.raises(db_client.OperationalError):
                get_user_profile(1)


class TestProcessP4:
    def test_p4_gateway_distinguishes_404_and_500(self):
        from api_gateway import handle_request
        _, login = handle_request(
            'POST', '/api/login',
            body={'username': 'alice', 'password': 'alice_pass_123'},
        )
        headers = {'Authorization': f"Bearer {login['token']}"}
        code, body = handle_request('GET', '/api/profile/999', headers=headers)
        assert code == 404 and body == {'error': 'user not found'}
        with patch(
            'db_client.fetch_user_profile',
            side_effect=db_client.OperationalError('db down'),
        ):
            code, body = handle_request('GET', '/api/profile', headers=headers)
        assert code in (500, 503)
        assert body.get('profile') != {}


class TestProcessP5:
    def test_p5_no_silent_chain(self):
        from user_service import get_user_profile
        with patch(
            'db_client.fetch_user_profile',
            side_effect=db_client.OperationalError('timeout'),
        ):
            with pytest.raises(db_client.OperationalError):
                get_user_profile(1)
