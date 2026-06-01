from __future__ import annotations

import json
from pathlib import Path

import mock_api
from auth_session import authenticate_session, load_credentials
from detail_collector import collect_details

CREDENTIALS_FILE = Path(__file__).with_name("credentials.json")


def run(output_path: str | Path = "output.json"):
    credentials = load_credentials(CREDENTIALS_FILE)
    session = authenticate_session(mock_api, credentials)
    items = mock_api.list_items(session["headers"])["items"]
    details = collect_details(mock_api, items, session)
    Path(output_path).write_text(json.dumps(details, indent=2), encoding="utf-8")
    return details


if __name__ == "__main__":
    run()
