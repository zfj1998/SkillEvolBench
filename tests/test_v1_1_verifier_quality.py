from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_ROOT = REPO_ROOT / "benchmark" / "tasks"


def _e6_task_roots() -> list[Path]:
    roots: list[Path] = []
    for spec_path in TASKS_ROOT.glob("*/task-spec.yaml"):
        task_id = next(
            (
                line.split(":", 1)[1].strip()
                for line in spec_path.read_text(encoding="utf-8").splitlines()
                if line.startswith("task_id:")
            ),
            "",
        )
        if task_id.startswith("E6-"):
            roots.append(spec_path.parent)
    return sorted(roots)


def test_e6_process_verifiers_do_not_require_hidden_source_markers() -> None:
    task_roots = _e6_task_roots()
    assert len(task_roots) == 30

    marker_test_fragments = (
        "process_markers",
        "expected process marker",
        "expected marker",
        "capability_markers_for_advanced_cases",
        "policy_contains_required_capability_markers",
    )
    offenders: dict[str, list[str]] = {}
    for task_root in task_roots:
        process_text = (task_root / "tests" / "test_process.py").read_text(
            encoding="utf-8"
        )
        matches = [
            fragment for fragment in marker_test_fragments if fragment in process_text
        ]
        if matches:
            offenders[task_root.name] = matches

    assert not offenders, (
        "E6 process verifiers must exercise observable behavior instead of requiring "
        f"unpublished source words: {offenders}"
    )


def test_e6_ground_truth_does_not_publish_unused_source_marker_contracts() -> None:
    offenders: list[str] = []
    for task_root in _e6_task_roots():
        ground_truth_path = task_root / "tests" / "ground_truth.json"
        if not ground_truth_path.exists():
            continue
        payload = json.loads(ground_truth_path.read_text(encoding="utf-8"))
        if "process_markers" in payload:
            offenders.append(task_root.name)

    assert not offenders, (
        "retired source-marker fields should not remain in ground truth: "
        f"{offenders}"
    )


def test_e6_process_verifiers_retain_nonlexical_checks() -> None:
    too_small: dict[str, int] = {}
    for task_root in _e6_task_roots():
        process_text = (task_root / "tests" / "test_process.py").read_text(
            encoding="utf-8"
        )
        test_count = process_text.count("def test_")
        if test_count < 3:
            too_small[task_root.name] = test_count

    assert not too_small, (
        "removing lexical marker checks must not empty the process verifier: "
        f"{too_small}"
    )
