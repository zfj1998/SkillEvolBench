from __future__ import annotations

import json
from pathlib import Path

import mock_api
from offer_formatter import build_offer_row
from offer_router import choose_offer_endpoint

USERS_FILE = Path(__file__).with_name('users.json')


def run(output_path: str | Path = 'offers_output.json'):
    user_ids = json.loads(USERS_FILE.read_text(encoding='utf-8'))['user_ids']
    results = []
    for user_id in user_ids:
        user = mock_api.get_user(user_id)
        endpoint = choose_offer_endpoint(user)
        if endpoint == 'premium':
            offers = mock_api.get_premium_offers(user['user_id'])
        else:
            offers = mock_api.get_standard_offers(user['user_id'])
        results.append(build_offer_row(user, offers))
    Path(output_path).write_text(json.dumps(results, indent=2), encoding='utf-8')
    return results


if __name__ == '__main__':
    run()
