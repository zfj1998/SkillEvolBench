"""Outcome verifier for E1-LS1-T4."""

import hashlib
import hmac
import json
import os
import sys

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..', 'project')
sys.path.insert(0, PROJECT_DIR)


class TestPublicBugFixes:
    def test_p1_import_updated(self):
        from app.models import UserResponseSchema
        from app.database import get_user
        row = get_user(1)
        schema = UserResponseSchema.from_record(row)
        payload = schema.to_api_dict()
        assert payload['display_name'] == 'alice'
        assert payload['email'] == 'alice@corp.io'

    def test_p2_service_test_uses_db_patch(self):
        import os as _os
        from unittest.mock import patch
        from app.services import get_active_users
        with patch.dict(_os.environ, {'DATABASE_URL': 'sqlite:///:memory:'}, clear=False):
            active = get_active_users()
        assert len(active) == 3
        assert {u['username'] for u in active} == {'alice', 'bob', 'dave'}

    def test_p3_date_compare_fixed(self):
        from app.utils import is_before
        assert is_before('2024-1-9', '2024-01-10') is True
        assert is_before('2024-2-15', '2024-11-15') is True

    def test_p4_user_http_endpoints_return_json(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        all_users = client.get('/api/users')
        active_users = client.get('/api/users/active')
        user_one = client.get('/api/users/1')

        assert all_users.status_code == 200
        assert active_users.status_code == 200
        assert user_one.status_code == 200
        assert isinstance(all_users.json(), list)
        assert {u['username'] for u in active_users.json()} == {'alice', 'bob', 'dave'}
        assert user_one.json()['username'] == 'alice'


def _sign(body: bytes) -> str:
    from app.config import WEBHOOK_SECRET
    return 'sha256=' + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _call_wh(body, headers):
    ns = {'__builtins__': __builtins__}
    exec('import hmac, hashlib, json', ns)
    exec('from typing import Any, Dict, Tuple', ns)
    exec('from app.config import WEBHOOK_SECRET', ns)
    exec('from app.models import WebhookEvent, validate_event_payload', ns)
    exec('from app.database import store_event', ns)
    src = open(os.path.join(PROJECT_DIR, 'app', 'routers', 'webhooks.py')).read()
    idx = src.find('def handle_webhook_request')
    if idx < 0:
        raise RuntimeError('handle_webhook_request not found')
    exec(src[idx:], ns)
    return ns['handle_webhook_request'](body, headers)


class TestHiddenWebhook:
    def setup_method(self):
        from app.database import clear_events
        clear_events()

    def test_h1_valid_signature(self):
        body = json.dumps({'event_id': 'e1', 'event_type': 'order.created', 'data': {'id': 42}}).encode()
        code, resp = _call_wh(body, {'x-hub-signature-256': _sign(body)})
        assert code == 200
        assert resp.get('event_id') == 'e1'

    def test_h2_invalid_signature(self):
        body = json.dumps({'event_id': 'e2', 'event_type': 'test', 'data': {}}).encode()
        code, _ = _call_wh(body, {'x-hub-signature-256': 'sha256=' + '0' * 64})
        assert code == 403

    def test_h3_missing_signature(self):
        body = json.dumps({'event_id': 'e3', 'event_type': 'test', 'data': {}}).encode()
        code, _ = _call_wh(body, {})
        assert code in (400, 401)

    def test_h4_non_json(self):
        body = b'not json'
        code, _ = _call_wh(body, {'x-hub-signature-256': _sign(body)})
        assert code == 400

    def test_h4b_missing_required_field(self):
        body = json.dumps({'event_id': 'e4b', 'data': {'id': 1}}).encode()
        code, resp = _call_wh(body, {'x-hub-signature-256': _sign(body)})
        assert code == 400
        assert 'event_type' in json.dumps(resp).lower()

    def test_h5_event_stored(self):
        from app.database import get_events
        body = json.dumps({'event_id': 'e5', 'event_type': 'user.updated', 'data': {'uid': 7}}).encode()
        _call_wh(body, {'x-hub-signature-256': _sign(body)})
        events = get_events()
        assert len(events) == 1
        assert events[0]['event_id'] == 'e5'
        assert events[0]['verified'] is True
