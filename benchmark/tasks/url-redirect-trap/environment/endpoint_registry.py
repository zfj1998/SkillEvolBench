from __future__ import annotations


def resolve_data_endpoint(config: dict[str, str]) -> str:
    # The starter still prefers the legacy endpoint during the old dual-read
    # migration mode instead of following the current endpoint from /config.
    if config.get('migration_state') != 'cutover' and config.get('deprecated_endpoint'):
        return config['deprecated_endpoint']
    return config['data_endpoint']
