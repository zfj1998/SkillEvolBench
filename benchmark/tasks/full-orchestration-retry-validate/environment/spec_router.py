from __future__ import annotations


def fetch_spec_for_user(api, profile: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
    # The starter still trusts a stale execution-path hint captured earlier in
    # the rollout instead of routing from the current tier.
    hint = profile.get('execution_path_hint')
    if hint == 'premium':
        return api.get_premium_spec(profile['user_id'], headers)
    if hint == 'standard':
        return api.get_standard_spec(profile['user_id'], headers)
    if profile['tier'] == 'premium':
        return api.get_premium_spec(profile['user_id'], headers)
    return api.get_standard_spec(profile['user_id'], headers)
