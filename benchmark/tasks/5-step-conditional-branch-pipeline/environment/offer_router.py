from __future__ import annotations


def choose_offer_endpoint(user: dict[str, object]) -> str:
    # The starter still trusts the legacy billing tier field instead of the
    # current runtime status returned by the profile service.
    tier = user.get('billing_tier', user['status'])
    return 'premium' if tier == 'premium' else 'standard'
