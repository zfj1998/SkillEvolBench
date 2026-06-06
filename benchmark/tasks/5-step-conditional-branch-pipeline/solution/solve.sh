#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "offers_pipeline.py": dedent("""
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
    """),
    "offer_router.py": dedent("""
        from __future__ import annotations


        def choose_offer_endpoint(user: dict[str, object]) -> str:
            return 'premium' if user['status'] == 'premium' else 'standard'
    """),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"Wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
