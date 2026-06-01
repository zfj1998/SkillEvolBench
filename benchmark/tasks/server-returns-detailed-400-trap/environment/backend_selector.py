from __future__ import annotations

import mock_api_v1
import mock_api_v2

from compat_flags import API_BACKEND


def resolve_backend():
    if API_BACKEND == "v2":
        return mock_api_v2
    return mock_api_v1
