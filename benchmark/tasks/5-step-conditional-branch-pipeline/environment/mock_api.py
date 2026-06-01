from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRACE: list[dict[str, Any]] = []
USERS = {
    'user_1': {'status': 'premium', 'billing_tier': 'premium', 'name': 'Ada'},
    'user_2': {'status': 'standard', 'billing_tier': 'standard', 'name': 'Ben'},
    'user_3': {'status': 'premium', 'billing_tier': 'legacy-premium', 'name': 'Cora'},
}
PREMIUM = {
    'user_1': [{'offer': 'vip-support', 'value': 300}, {'offer': 'priority-shipping', 'value': 120}],
    'user_3': [{'offer': 'concierge', 'value': 400}, {'offer': 'insider-discount', 'value': 90}],
}
STANDARD = {
    'user_1': [{'offer': 'starter-discount', 'value': 25}],
    'user_2': [{'offer': 'starter-discount', 'value': 25}, {'offer': 'shipping-credit', 'value': 15}],
    'user_3': [{'offer': 'starter-discount', 'value': 25}],
}


def reset_state() -> None:
    TRACE.clear()


def _record(endpoint: str, payload: dict[str, Any]) -> None:
    TRACE.append({'endpoint': endpoint, **payload})


def get_user(user_id: str) -> dict[str, Any]:
    data = {'user_id': user_id, **USERS[user_id]}
    _record('/user', {'user_id': user_id, 'status': data['status']})
    return data


def get_premium_offers(user_id: str) -> list[dict[str, Any]]:
    offers = PREMIUM[user_id]
    _record('/premium/offers', {'user_id': user_id, 'offer_names': [item['offer'] for item in offers]})
    return offers


def get_standard_offers(user_id: str) -> list[dict[str, Any]]:
    offers = STANDARD[user_id]
    _record('/standard/offers', {'user_id': user_id, 'offer_names': [item['offer'] for item in offers]})
    return offers


def save_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding='utf-8')
