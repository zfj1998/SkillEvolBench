from __future__ import annotations


def build_offer_row(user: dict[str, object], offers: list[dict[str, object]]) -> dict[str, object]:
    return {
        'user_id': user['user_id'],
        'status': user['status'],
        'offers': [item['offer'] for item in offers],
        'total_value': sum(item['value'] for item in offers),
    }
