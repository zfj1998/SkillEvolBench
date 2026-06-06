"""Outcome verifier for E1-LS2-T6."""
import os, subprocess, tempfile
from pathlib import Path
import pytest
TASK_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TASK_DIR / "project"
PROJECT = PROJECT_ROOT / "project" if (PROJECT_ROOT / "project").exists() else PROJECT_ROOT
LOCAL_INDEX = PROJECT_ROOT / "local_index"

def _install():
    tmp = tempfile.TemporaryDirectory(); site = Path(tmp.name) / "site"; site.mkdir()
    env = os.environ.copy(); env["PIP_NO_INDEX"] = "1"; env["PIP_FIND_LINKS"] = str(LOCAL_INDEX)
    r = subprocess.run(["python3","-m","pip","install","--target",str(site),"-r",str(PROJECT/"requirements.txt")], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
    return tmp, site, r

def _env(site):
    env = os.environ.copy(); env["PYTHONPATH"] = str(site)+os.pathsep+str(PROJECT/"src"); env["PATH"] = str(site/"bin")+os.pathsep+env.get("PATH","")
    return env

def _py(site, code):
    return subprocess.run(["python3","-c",code], env=_env(site), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, cwd=str(PROJECT))

def _cmd(site, args):
    return subprocess.run(args, env=_env(site), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, cwd=str(PROJECT))

class TestPublic:
    def test_public_install(self):
        tmp, site, r = _install();
        try: assert r.returncode == 0, r.stderr
        finally: tmp.cleanup()
    def test_public_db_connect(self):
        tmp, site, r = _install();
        try:
            assert r.returncode == 0, r.stderr
            t = _py(site, "from app import initialize; from database import engine; initialize(); engine.connect().close(); print('ok')")
            assert t.returncode == 0, t.stderr
        finally: tmp.cleanup()
    def test_public_basic_crud(self):
        tmp, site, r = _install();
        try:
            assert r.returncode == 0, r.stderr
            t = _py(site, "from app import initialize; from services.user_service import create_user, get_user; from services.order_service import create_order, get_order; initialize(); create_user(1, 'alice', 'a@example.com'); create_order(10, 1, 100); assert get_user(1)['name'] == 'alice'; assert get_order(10)['amount'] == 100; print('ok')")
            assert t.returncode == 0, t.stderr
        finally: tmp.cleanup()

@pytest.mark.hidden
def test_h1_config_uses_postgresql_scheme():
    config_text = (PROJECT / 'src' / 'config.py').read_text()
    assert 'postgresql://' in config_text and 'postgres://' not in config_text

@pytest.mark.hidden
def test_h2_user_crud_works():
    tmp, site, r = _install();
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, "from app import initialize; from services.user_service import create_user, get_user, list_users; initialize(); create_user(1, 'alice', 'a@example.com'); create_user(2, 'bob', 'b@example.com'); assert get_user(2)['email'] == 'b@example.com'; assert [u['id'] for u in list_users()] == [1, 2]; print('ok')")
        assert t.returncode == 0, t.stderr
    finally: tmp.cleanup()

@pytest.mark.hidden
def test_h3_order_insert_persists_across_sessions():
    tmp, site, r = _install();
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, "from app import initialize; from services.user_service import create_user; from services.order_service import create_order; from database import SessionLocal; from sqlalchemy import text; initialize(); create_user(1, 'alice', 'a@example.com'); create_order(10, 1, 125); s = SessionLocal(); row = s.execute(text('SELECT amount FROM orders WHERE id = :id'), {'id': 10}).fetchone(); s.close(); assert row[0] == 125; print('ok')")
        assert t.returncode == 0, t.stderr
    finally: tmp.cleanup()

@pytest.mark.hidden
def test_h4_report_aggregation_correct():
    tmp, site, r = _install();
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, "from app import initialize; from services.user_service import create_user; from services.order_service import create_order, update_order_amount; from services.report_service import count_users, count_orders, total_amount_for_user; initialize(); create_user(1, 'alice', 'a@example.com'); create_user(2, 'bob', 'b@example.com'); create_order(10, 1, 100); create_order(11, 1, 40); create_order(12, 2, 20); update_order_amount(11, 60); assert count_users() == 2; assert count_orders() == 3; assert total_amount_for_user(1) == 160; print('ok')")
        assert t.returncode == 0, t.stderr
    finally: tmp.cleanup()

@pytest.mark.hidden
def test_h5_multi_session_concurrency():
    tmp, site, r = _install();
    try:
        assert r.returncode == 0, r.stderr
        t = _py(site, "from app import initialize; from services.user_service import create_user; from services.order_service import create_order; from services.report_service import count_users, count_orders; from database import SessionLocal; from sqlalchemy import text; initialize(); create_user(1, 'alice', 'a@example.com'); create_user(2, 'bob', 'b@example.com'); create_order(10, 1, 100); create_order(11, 2, 50); s1=SessionLocal(); s2=SessionLocal(); rows1=s1.execute(text('SELECT id, name FROM users')).fetchall(); rows2=s2.execute(text('SELECT id, amount FROM orders')).fetchall(); s1.close(); s2.close(); assert len(rows1) == 2 and len(rows2) == 2; assert count_users() == 2 and count_orders() == 2; print('ok')")
        assert t.returncode == 0, t.stderr
    finally: tmp.cleanup()

@pytest.mark.hidden
def test_h6_alembic_upgrade_head_succeeds():
    tmp, site, r = _install();
    try:
        assert r.returncode == 0, r.stderr
        t = _cmd(site, ['alembic','upgrade','head'])
        assert t.returncode == 0, t.stderr
    finally: tmp.cleanup()
