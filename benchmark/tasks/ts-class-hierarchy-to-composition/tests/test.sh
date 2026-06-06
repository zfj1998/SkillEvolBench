#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$LOG_DIR"
export SCRIPT_DIR PROJECT_ROOT LOG_DIR

"$PYTHON_BIN" -m pip install --break-system-packages --no-cache-dir pytest==8.3.5 pytest-json-report==1.5.0 PyYAML==6.0.2 >/dev/null 2>&1 || \
"$PYTHON_BIN" -m pip install --no-cache-dir pytest==8.3.5 pytest-json-report==1.5.0 PyYAML==6.0.2 >/dev/null

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"]).resolve()
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()
LOG_DIR = Path(os.environ.get("LOG_DIR", "/logs/verifier")).resolve()


def _copy_test_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    test_sh = dst / "test.sh"
    if test_sh.exists():
        test_sh.unlink()


def _write_runtime_support(base: Path) -> Path:
    pkg = base / "verifier_lib"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    runtime_text = '''from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


def emit_report(task_id, public, hidden, notes=None):
    return {
        "task_id": task_id,
        "public": public,
        "hidden": hidden,
        "notes": notes or [],
    }


def print_report(report):
    print(json.dumps(report, ensure_ascii=True))


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def run_subprocess(command, cwd):
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def run_checks(section, checks):
    results = []
    for name, fn in checks:
        try:
            detail = fn()
            passed = detail is not False
            error = None
        except AssertionError as exc:
            detail = None
            passed = False
            error = str(exc)
        except Exception as exc:
            detail = None
            passed = False
            error = f"{type(exc).__name__}: {exc}"
        results.append({
            "name": name,
            "passed": passed,
            "detail": detail,
            "error": error,
        })
    return {
        "section": section,
        "results": results,
        "passed": sum(1 for item in results if item["passed"]),
        "total": len(results),
    }
'''
    (pkg / "runtime.py").write_text(runtime_text, encoding="utf-8")
    yaml_text = '''from __future__ import annotations


def _parse_scalar(value: str):
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    try:
        if any(ch in value for ch in [".", "e", "E"]):
            return float(value)
        return int(value)
    except ValueError:
        return value


def safe_load(stream):
    text = stream.read() if hasattr(stream, "read") else str(stream)
    raw_lines = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        raw_lines.append(line.rstrip())

    index = 0

    def parse_block(indent: int):
        nonlocal index
        mapping = {}
        sequence = []
        mode = None
        while index < len(raw_lines):
            line = raw_lines[index]
            current_indent = len(line) - len(line.lstrip(" "))
            if current_indent < indent:
                break
            if current_indent > indent:
                break

            stripped = line.strip()
            if stripped.startswith("- "):
                mode = mode or "list"
                item_text = stripped[2:].strip()
                index += 1
                if ":" in item_text:
                    key, value = item_text.split(":", 1)
                    item = {key.strip(): _parse_scalar(value.strip()) if value.strip() else None}
                    if index < len(raw_lines):
                        next_indent = len(raw_lines[index]) - len(raw_lines[index].lstrip(" "))
                        if next_indent > current_indent:
                            nested = parse_block(current_indent + 2)
                            if isinstance(nested, dict):
                                item.update(nested)
                    sequence.append(item)
                elif item_text:
                    sequence.append(_parse_scalar(item_text))
                else:
                    sequence.append(parse_block(current_indent + 2))
                continue

            mode = mode or "dict"
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            index += 1
            if value:
                mapping[key] = _parse_scalar(value)
            else:
                mapping[key] = parse_block(current_indent + 2)

        return sequence if mode == "list" else mapping

    return parse_block(0)
'''
    (base / "yaml.py").write_text(yaml_text, encoding="utf-8")
    return base


def _run_pytest(target: Path, report_path: Path, cwd: Path, pytest_config: Path | None) -> int:
    command = [
        sys.executable,
        "-m",
        "pytest",
        str(target),
        "-rA",
        "-v",
        "--json-report",
        f"--json-report-file={report_path}",
    ]
    if pytest_config is not None:
        command.extend(["-c", str(pytest_config)])
    result = subprocess.run(command, cwd=cwd, check=False, env=os.environ.copy())
    return result.returncode


def _load_pytest_results(path: Path) -> dict[str, bool]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {test["nodeid"]: test["outcome"] == "passed" for test in data.get("tests", [])}


def _generic_pytest_score(outcome_path: Path, process_path: Path) -> dict:
    dimensions = []
    total_score = 0.0
    groups = [("outcome", outcome_path), ("process", process_path)]
    present = [(name, path) for name, path in groups if path.exists()]
    weight = 100.0 / len(present) if present else 100.0
    for name, path in present:
        results = _load_pytest_results(path)
        total = len(results)
        passed = sum(1 for value in results.values() if value)
        ratio = passed / total if total else 0.0
        score = weight * ratio
        total_score += score
        dimensions.append(
            {
                "name": name,
                "weight": round(weight, 2),
                "tests_matched": total,
                "tests_passed": passed,
                "scoring": "proportional",
                "ratio": round(ratio, 3),
                "score": round(score, 2),
            }
        )
    return {
        "total_score": round(total_score, 2),
        "max_score": 100.0,
        "dimensions": dimensions,
    }


def _group_to_dimension(name: str, group: dict, weight: float) -> dict:
    total = int(group.get("total", 0))
    passed = int(group.get("passed", 0))
    ratio = (passed / total) if total else 0.0
    return {
        "name": name,
        "weight": round(weight, 2),
        "tests_matched": total,
        "tests_passed": passed,
        "scoring": "proportional",
        "ratio": round(ratio, 3),
        "score": round(weight * ratio, 2),
    }


def _generic_script_score(outcome_report: dict, process_report: dict) -> dict:
    groups = []
    if outcome_report:
        if "public" in outcome_report:
            groups.append(("outcome_public", outcome_report["public"]))
        if "hidden" in outcome_report:
            groups.append(("outcome_hidden", outcome_report["hidden"]))
    if process_report:
        if "public" in process_report:
            groups.append(("process_public", process_report["public"]))
        if "hidden" in process_report:
            groups.append(("process_hidden", process_report["hidden"]))
    groups = [
        (name, group)
        for name, group in groups
        if isinstance(group, dict) and group.get("total", 0) > 0
    ]
    weight = 100.0 / len(groups) if groups else 100.0
    dimensions = []
    total_score = 0.0
    for name, group in groups:
        dim = _group_to_dimension(name, group, weight)
        total_score += dim["score"]
        dimensions.append(dim)
    return {
        "total_score": round(total_score, 2),
        "max_score": 100.0,
        "dimensions": dimensions,
    }


def _all_script_groups_pass(report: dict) -> bool:
    relevant = [report.get("public"), report.get("hidden")]
    present = [
        group
        for group in relevant
        if isinstance(group, dict) and group.get("total", 0) > 0
    ]
    return all(group.get("passed", 0) == group.get("total", 0) for group in present)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _run_script_report(name: str, path: Path, support_root: Path) -> dict:
    sys.path.insert(0, str(support_root))
    module = _load_module(name, path)
    if not hasattr(module, "run"):
        raise RuntimeError(f"{path} does not expose run()")
    return module.run()


def _run_score(score_script: Path, outcome_path: Path, process_path: Path) -> Path:
    subprocess.run(
        [sys.executable, str(score_script), str(outcome_path), str(process_path)],
        cwd=LOG_DIR,
        check=True,
        env=os.environ.copy(),
    )
    return LOG_DIR / "score_report.json"


def _compute_score_fallback(score_script: Path, outcome_path: Path, process_path: Path) -> dict:
    module = _load_module("legacy_score_module", score_script)
    if hasattr(module, "compute_score"):
        combined_results = {
            **_load_pytest_results(outcome_path),
            **_load_pytest_results(process_path),
        }
        result = module.compute_score(combined_results)
        if isinstance(result, tuple) and len(result) == 2:
            total, dims = result
            return {"total_score": float(total), "max_score": 100.0, "dimensions": dims}
        if isinstance(result, dict):
            total = result.get("total_score", result.get("total", 0.0))
            maximum = result.get("max_score", 100.0)
            dims = result.get("dimensions", result.get("dims", []))
            return {
                "total_score": float(total),
                "max_score": float(maximum),
                "dimensions": dims,
            }
    outcome_data = json.loads(outcome_path.read_text(encoding="utf-8"))
    process_data = json.loads(process_path.read_text(encoding="utf-8"))
    combined_report = {
        "tests": outcome_data.get("tests", []) + process_data.get("tests", []),
    }
    if all(hasattr(module, attr) for attr in ("RUBRIC", "_collect", "_score_dim")):
        passed, failed = module._collect(combined_report)
        total = 0.0
        dimensions = []
        for dim in module.RUBRIC:
            score = float(module._score_dim(dim, passed, failed))
            total += score
            dimensions.append(
                {
                    "name": getattr(dim, "name", "dimension"),
                    "weight": float(getattr(dim, "weight", 0.0)),
                    "score": round(score, 2),
                }
            )
        return {
            "total_score": round(total, 2),
            "max_score": 100.0,
            "dimensions": dimensions,
        }
    raise RuntimeError(f"Unsupported score result from {score_script}")


def _write_reward(score_report: dict, outcome_code: int, process_code: int) -> None:
    total = float(score_report.get("total_score", 0.0))
    maximum = float(score_report.get("max_score", 100.0)) or 100.0
    normalized = total / maximum
    payload = {
        "total_score": total,
        "max_score": maximum,
        "normalized_score": normalized,
        "outcome_passed": 1.0 if outcome_code == 0 else 0.0,
        "process_passed": 1.0 if process_code == 0 else 0.0,
    }
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / "reward.txt").write_text(f"{normalized:.6f}\n", encoding="utf-8")
    (LOG_DIR / "reward.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


if not PROJECT_ROOT.exists():
    raise FileNotFoundError(f"project root not found: {PROJECT_ROOT}")

with tempfile.TemporaryDirectory(prefix="harbor-eval-") as tmpdir:
    runtime_root = Path(tmpdir)
    runtime_task_root = runtime_root / "workspace" / "task"
    project_root = runtime_task_root / "project"
    runtime_test_root = runtime_task_root / "test"
    support_root = runtime_root / "support"

    runtime_task_root.mkdir(parents=True)
    shutil.copytree(PROJECT_ROOT, project_root, symlinks=True)
    _copy_test_tree(SCRIPT_DIR, runtime_test_root)
    task_root = SCRIPT_DIR.parent
    instruction_path = task_root / "instruction.md"
    if instruction_path.exists():
        shutil.copy2(instruction_path, runtime_task_root / "instruction.md")
    _write_runtime_support(support_root)
    os.environ["PYTHONPATH"] = str(support_root) + os.pathsep + os.environ.get("PYTHONPATH", "")
    os.environ["npm_config_cache"] = str(runtime_root / "npm-cache")

    outcome_path = runtime_test_root / "test_outcome.py"
    process_path = runtime_test_root / "test_process.py"
    score_path = runtime_test_root / "score.py"
    pytest_config = runtime_test_root / "pytest.ini"
    pytest_config = pytest_config if pytest_config.exists() else None

    uses_script_runtime = False
    for candidate in (outcome_path, process_path):
        if candidate.exists() and "verifier_lib.runtime" in candidate.read_text(
            encoding="utf-8", errors="ignore"
        ):
            uses_script_runtime = True
            break

    if uses_script_runtime:
        outcome_report = (
            _run_script_report("harbor_outcome", outcome_path, support_root)
            if outcome_path.exists()
            else {}
        )
        process_report = (
            _run_script_report("harbor_process", process_path, support_root)
            if process_path.exists()
            else {}
        )
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / "outcome_report.json").write_text(
            json.dumps(outcome_report, indent=2) + "\n", encoding="utf-8"
        )
        (LOG_DIR / "process_report.json").write_text(
            json.dumps(process_report, indent=2) + "\n", encoding="utf-8"
        )
        outcome_code = 0 if _all_script_groups_pass(outcome_report) else 1
        process_code = 0 if _all_script_groups_pass(process_report) else 1
        score_report = _generic_script_score(outcome_report, process_report)
        (LOG_DIR / "score_report.json").write_text(
            json.dumps(score_report, indent=2) + "\n", encoding="utf-8"
        )
        _write_reward(score_report, outcome_code, process_code)
        raise SystemExit(0 if outcome_code == 0 and process_code == 0 else 1)

    outcome_json = runtime_root / "outcome.json"
    process_json = runtime_root / "process.json"
    outcome_code = _run_pytest(outcome_path, outcome_json, runtime_task_root, pytest_config)
    process_code = _run_pytest(process_path, process_json, runtime_task_root, pytest_config)

    if score_path.exists():
        try:
            score_report_path = _run_score(score_path, outcome_json, process_json)
        except subprocess.CalledProcessError:
            score_report = _compute_score_fallback(score_path, outcome_json, process_json)
            score_report_path = LOG_DIR / "score_report.json"
            score_report_path.write_text(
                json.dumps(score_report, indent=2) + "\n", encoding="utf-8"
            )
        if score_report_path.exists():
            score_report = json.loads(score_report_path.read_text(encoding="utf-8"))
        else:
            score_report = _compute_score_fallback(score_path, outcome_json, process_json)
            score_report_path.write_text(
                json.dumps(score_report, indent=2) + "\n", encoding="utf-8"
            )
    else:
        score_report = _generic_pytest_score(outcome_json, process_json)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / "score_report.json").write_text(
            json.dumps(score_report, indent=2) + "\n", encoding="utf-8"
        )

    _write_reward(score_report, outcome_code, process_code)
    raise SystemExit(0 if outcome_code == 0 and process_code == 0 else 1)
PY

if [ ! -f "$LOG_DIR/reward.txt" ]; then
  echo 0 > "$LOG_DIR/reward.txt"
fi

exit 0
