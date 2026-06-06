"""Process verifier for E1-LS2-T6."""
from pathlib import Path
TASK_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TASK_DIR / 'project'
PROJECT = PROJECT_ROOT / 'project' if (PROJECT_ROOT / 'project').exists() else PROJECT_ROOT
SRC = PROJECT / 'src'
SERVICES = SRC / 'services'

def _code(path: Path) -> str:
    return path.read_text()

def test_process_p1_config_uses_postgresql_scheme():
    code = _code(SRC / 'config.py')
    assert 'postgresql://' in code and 'postgres://' not in code

def test_process_p2_services_use_session_execute_text():
    violations = []
    for name in ['user_service.py','order_service.py','report_service.py']:
        code = _code(SERVICES / name)
        if 'engine.execute(' in code: violations.append(f'{name}: engine.execute still present')
        if 'SessionLocal' not in code: violations.append(f'{name}: missing SessionLocal usage')
        if 'text(' not in code: violations.append(f'{name}: missing text(...) wrapper')
    assert not violations, '\n'.join(violations)

def test_process_p3_writes_have_commit():
    for name in ['user_service.py','order_service.py']:
        assert '.commit()' in _code(SERVICES / name)

def test_process_p4_raw_sql_wrapped_in_text():
    for name in ['user_service.py','order_service.py','report_service.py']:
        code = _code(SERVICES / name)
        assert 'text("' in code or "text('" in code

def test_process_p5_no_engine_execute_anywhere_in_src():
    violations=[]
    for path in SRC.rglob('*.py'):
        if 'engine.execute(' in _code(path): violations.append(str(path.relative_to(SRC)))
    assert not violations, f'engine.execute remains in: {violations}'
