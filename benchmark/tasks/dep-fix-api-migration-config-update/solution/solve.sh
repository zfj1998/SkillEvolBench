#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task/project}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
P="$PROJECT_ROOT"
LOCAL_INDEX="$TASK_ROOT/local_index"
cd "$P"
python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('requirements.txt')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('sqlalchemy>=2.0\nalembic>=1.12\n', encoding='utf-8')
PYWRITE_1
python3 - <<'PYWRITE_2'
from pathlib import Path
target = Path('src/config.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Application configuration."""\n\nDATABASE_URL = "postgresql://user:pass@localhost:5432/appdb"\n', encoding='utf-8')
PYWRITE_2
python3 - <<'PYWRITE_3'
from pathlib import Path
target = Path('src/database.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Database initialization — SQLAlchemy 2.0 style."""\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import sessionmaker\nfrom config import DATABASE_URL\nengine = create_engine(DATABASE_URL)\nSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)\n', encoding='utf-8')
PYWRITE_3
python3 - <<'PYWRITE_4'
from pathlib import Path
target = Path('src/migrations/env.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Migration environment for alembic upgrade head."""\nfrom sqlalchemy import text\nfrom database import engine\n\ndef run_migrations():\n    engine.store.clear()\n    with engine.begin() as conn:\n        conn.execute(text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)"))\n        conn.execute(text("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER)"))\n    return {"status": "ok", "revision": "head"}\n', encoding='utf-8')
PYWRITE_4
python3 - <<'PYWRITE_5'
from pathlib import Path
target = Path('src/app.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Application entry point."""\nfrom alembic import run_upgrade\nfrom database import SessionLocal\n\ndef initialize():\n    return run_upgrade()\n\ndef get_db():\n    return SessionLocal()\n', encoding='utf-8')
PYWRITE_5
python3 - <<'PYWRITE_6'
from pathlib import Path
target = Path('src/services/user_service.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""User service — SQLAlchemy 2.0 session.execute API."""\nfrom sqlalchemy import text\nfrom database import SessionLocal\n\ndef create_user(user_id, name, email):\n    with SessionLocal() as session:\n        session.execute(text("INSERT INTO users (id, name, email) VALUES (:id, :name, :email)"), {"id": user_id, "name": name, "email": email})\n        session.commit()\n    return {"id": user_id, "name": name, "email": email}\n\ndef get_user(user_id):\n    with SessionLocal() as session:\n        row = session.execute(text("SELECT id, name, email FROM users WHERE id = :id"), {"id": user_id}).fetchone()\n    return None if not row else {"id": row[0], "name": row[1], "email": row[2]}\n\ndef list_users():\n    with SessionLocal() as session:\n        rows = session.execute(text("SELECT id, name, email FROM users")).fetchall()\n    return sorted([{"id": r[0], "name": r[1], "email": r[2]} for r in rows], key=lambda x: x[\'id\'])\n', encoding='utf-8')
PYWRITE_6
python3 - <<'PYWRITE_7'
from pathlib import Path
target = Path('src/services/order_service.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Order service — SQLAlchemy 2.0 session.execute API."""\nfrom sqlalchemy import text\nfrom database import SessionLocal\n\ndef create_order(order_id, user_id, amount):\n    with SessionLocal() as session:\n        session.execute(text("INSERT INTO orders (id, user_id, amount) VALUES (:id, :uid, :amt)"), {"id": order_id, "uid": user_id, "amt": amount})\n        session.commit()\n    return {"id": order_id, "user_id": user_id, "amount": amount}\n\ndef get_order(order_id):\n    with SessionLocal() as session:\n        row = session.execute(text("SELECT id, user_id, amount FROM orders WHERE id = :id"), {"id": order_id}).fetchone()\n    return None if not row else {"id": row[0], "user_id": row[1], "amount": row[2]}\n\ndef update_order_amount(order_id, new_amount):\n    with SessionLocal() as session:\n        session.execute(text("UPDATE orders SET amount = :amt WHERE id = :id"), {"amt": new_amount, "id": order_id})\n        session.commit()\n', encoding='utf-8')
PYWRITE_7
python3 - <<'PYWRITE_8'
from pathlib import Path
target = Path('src/services/report_service.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Report service — SQLAlchemy 2.0 session.execute API."""\nfrom sqlalchemy import text\nfrom database import SessionLocal\n\ndef count_users():\n    with SessionLocal() as session:\n        return session.execute(text("SELECT COUNT(*) FROM users")).scalar()\n\ndef count_orders():\n    with SessionLocal() as session:\n        return session.execute(text("SELECT COUNT(*) FROM orders")).scalar()\n\ndef total_amount_for_user(user_id):\n    with SessionLocal() as session:\n        rows = session.execute(text("SELECT amount FROM orders WHERE user_id = :uid"), {"uid": user_id}).fetchall()\n    return sum(r[0] for r in rows)\n', encoding='utf-8')
PYWRITE_8
TMP=$(mktemp -d)
SITE="$TMP/site"
mkdir -p "$SITE"
PIP_NO_INDEX=1 PIP_FIND_LINKS="$LOCAL_INDEX" python3 -m pip install --target "$SITE" -r requirements.txt >/dev/null
export PYTHONPATH="$SITE:$P/src"
export PATH="$SITE/bin:$PATH"
python3 - <<'VERIFY'
from app import initialize
from services.user_service import create_user, get_user
from services.order_service import create_order, get_order, update_order_amount
from services.report_service import count_users, count_orders, total_amount_for_user
result = initialize(); assert result['status'] == 'ok'
create_user(1, 'alice', 'a@example.com'); create_user(2, 'bob', 'b@example.com')
create_order(10, 1, 120); create_order(11, 1, 80); update_order_amount(10, 150)
assert get_user(1)['name'] == 'alice'; assert get_order(10)['amount'] == 150
assert count_users() == 2; assert count_orders() == 2; assert total_amount_for_user(1) == 230
print('oracle smoke ok')
VERIFY
alembic upgrade head >/dev/null
rm -rf "$TMP"
echo "Oracle solution applied successfully."
