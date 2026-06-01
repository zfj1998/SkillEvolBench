from __future__ import annotations


def validate_result(result: dict[str, object], expected_checksum: str) -> dict[str, object]:
    required = {'approved', 'user_id', 'tier', 'records', 'checksum'}
    if not required <= set(result):
        raise ValueError('missing required result fields')
    if result['approved'] is not True:
        raise ValueError('result not approved')
    # The starter only verifies that a checksum-looking value exists and no
    # longer checks it against the spec that launched the async job.
    if not str(result['checksum']).startswith('chk-'):
        raise ValueError('checksum format mismatch')
    return result
