"""Process verifier for E1-LS1-T6."""

import os
import re

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..', 'project')


def _read(rel: str) -> str:
    path = os.path.join(PROJECT_DIR, rel)
    return open(path).read() if os.path.exists(path) else ''


class TestProcessP1:
    def test_p1_four_core_files_modified(self):
        cfg = 'quote_plus' in _read('config.py')
        dbc = 'unquote_plus' in _read('db_client.py') or 'urlparse' in _read('db_client.py')
        svc = '_safe_fetch' not in _read('user_service.py') and 'except Exception' not in _read('user_service.py')
        gw = ('503' in _read('api_gateway.py') or '500' in _read('api_gateway.py')) and '404' in _read('api_gateway.py')
        assert all([cfg, dbc, svc, gw])


class TestProcessP2:
    def test_p2_config_uses_quote_plus(self):
        src = _read('config.py')
        assert 'quote_plus' in src


class TestProcessP3:
    def test_p3_user_service_no_silent_empty_return(self):
        src = _read('user_service.py')
        assert '_safe_fetch' not in src
        pattern = re.compile(r'except\s+Exception.*?:\s*\n\s*return\s+(\{\}|\[\]|False)', re.DOTALL)
        assert not pattern.search(src)


class TestProcessP4:
    def test_p4_gateway_distinguishes_404_and_500(self):
        src = _read('api_gateway.py').lower()
        assert '404' in src
        assert '500' in src or '503' in src
        assert "'error': 'user not found'" in _read('api_gateway.py') or 'user not found' in src


class TestProcessP5:
    def test_p5_no_silent_chain(self):
        for rel in ('user_service.py', 'api_gateway.py'):
            src = _read(rel)
            pattern = re.compile(r'except\s+Exception.*?:\s*\n\s*return\s+(\{\}|\[\]|False)', re.DOTALL)
            assert not pattern.search(src), f'{rel} still silently returns empty fallback'
