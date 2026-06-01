from __future__ import annotations

import json
from pathlib import Path


def load_credentials(path: str | Path) -> dict[str, str]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def authenticate_session(api, credentials: dict[str, str]) -> dict[str, object]:
    auth_payload = api.authenticate(credentials["username"], credentials["password"])
    token = auth_payload["access_token"]
    token_type = auth_payload.get("token_type", "Bearer")
    return {
        "token": token,
        "token_type": token_type,
        "headers": {"Authorization": f"{token_type} {token}"},
    }
