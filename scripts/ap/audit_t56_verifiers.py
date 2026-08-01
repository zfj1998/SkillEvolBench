#!/usr/bin/env python3
"""Audit verifier structure and optionally join observed task outcomes.

The historical default remains T4--T6 so existing reports stay reproducible.
Use ``--tiers 1,2,3,4,5,6 --output-prefix all_task_verifier_audit`` for a
complete 180-task structural inventory.
"""

from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def call_name(node: ast.Call) -> str:
    target: ast.expr = node.func
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return ".".join(reversed(parts))


def string_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def assigned_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


CODE_SUFFIXES = (".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".sh", ".go", ".rs", ".java")


def contains_code_literal(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Constant)
        and isinstance(item.value, str)
        and item.value.lower().endswith(CODE_SUFFIXES)
        for item in ast.walk(node)
    )


def contains_code_source_read(node: ast.AST, code_path_variables: set[str]) -> bool:
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        name = call_name(item)
        if name == "read_text":
            path_nodes = item.args[:1]
        elif name.endswith(".read_text") or name.endswith(".read"):
            path_nodes = [item.func.value] if isinstance(item.func, ast.Attribute) else []
        else:
            continue
        if any(
            contains_code_literal(path_node)
            or bool(assigned_names(path_node) & code_path_variables)
            for path_node in path_nodes
        ):
            return True
    return False


class StaticSignals(ast.NodeVisitor):
    def __init__(self) -> None:
        self.membership_checks = 0
        self.source_membership_checks = 0
        self.string_index_calls = 0
        self.source_string_index_calls = 0
        self.regex_calls = 0
        self.source_regex_calls = 0
        self.source_reads = 0
        self.file_existence_checks = 0
        self.dynamic_imports = 0
        self.subprocess_calls = 0
        self.json_load_calls = 0
        self.permissive_or_asserts = 0
        self.early_returns_in_tests = 0
        self.test_functions = 0
        self.named_checks: set[str] = set()
        self.run_check_sections: set[str] = set()
        self.function_names: set[str] = set()
        self.imports: set[str] = set()
        self.code_path_variables: set[str] = set()
        self.source_text_variables: set[str] = set()
        self._test_depth = 0

    def source_expression(self, node: ast.AST) -> bool:
        return contains_code_source_read(node, self.code_path_variables) or bool(
            assigned_names(node) & self.source_text_variables
        )

    def source_text_derivation(self, node: ast.AST) -> bool:
        if contains_code_source_read(node, self.code_path_variables):
            return True
        if isinstance(node, ast.Name):
            return node.id in self.source_text_variables
        if isinstance(node, ast.BinOp):
            return self.source_text_derivation(node.left) or self.source_text_derivation(node.right)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.JoinedStr)):
            return any(self.source_text_derivation(item) for item in ast.iter_child_nodes(node))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return (
                node.func.attr in {
                    "lower", "upper", "casefold", "strip", "lstrip", "rstrip",
                    "replace", "split", "splitlines", "join",
                }
                and self.source_text_derivation(node.func.value)
            )
        return False

    def visit_Assign(self, node: ast.Assign) -> None:
        if contains_code_literal(node.value):
            for target in node.targets:
                self.code_path_variables.update(assigned_names(target))
        if self.source_text_derivation(node.value):
            for target in node.targets:
                self.source_text_variables.update(assigned_names(target))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            if contains_code_literal(node.value):
                self.code_path_variables.update(assigned_names(node.target))
            if (
                self.source_text_derivation(node.value)
            ):
                self.source_text_variables.update(assigned_names(node.target))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.update(alias.name for alias in node.names)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_names.add(node.name)
        is_test = node.name.startswith("test_")
        if is_test:
            self.test_functions += 1
            self.named_checks.add(node.name)
            self._test_depth += 1
        self.generic_visit(node)
        if is_test:
            self._test_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Return(self, node: ast.Return) -> None:
        if self._test_depth and node.value is None:
            self.early_returns_in_tests += 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        if isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.Or):
            self.permissive_or_asserts += 1
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            candidates = [node.left, *node.comparators]
            if any(string_value(item) is not None for item in candidates):
                self.membership_checks += 1
                if any(self.source_expression(item) for item in candidates):
                    self.source_membership_checks += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = call_name(node)
        if name.endswith(".index") and node.args and string_value(node.args[0]) is not None:
            self.string_index_calls += 1
            if isinstance(node.func, ast.Attribute) and self.source_expression(node.func.value):
                self.source_string_index_calls += 1
        if name in {"re.search", "re.match", "re.fullmatch", "re.findall", "re.finditer"}:
            self.regex_calls += 1
            if any(self.source_expression(argument) for argument in node.args[1:]):
                self.source_regex_calls += 1
        if name.endswith("read_text") or name == "open" or name.endswith(".open"):
            self.source_reads += 1
        if name.endswith(".exists") or name.endswith(".is_file") or name.endswith(".is_dir"):
            self.file_existence_checks += 1
        if name in {"importlib.import_module", "__import__"}:
            self.dynamic_imports += 1
        if name.startswith("subprocess."):
            self.subprocess_calls += 1
        if name in {"json.load", "json.loads"}:
            self.json_load_calls += 1
        if name.endswith("run_checks") and len(node.args) >= 2 and isinstance(node.args[1], (ast.List, ast.Tuple)):
            section = string_value(node.args[0]) if node.args else None
            if section:
                self.run_check_sections.add(section)
            for item in node.args[1].elts:
                if isinstance(item, (ast.Tuple, ast.List)) and item.elts:
                    label = string_value(item.elts[0])
                    if label:
                        self.named_checks.add(label)
        self.generic_visit(node)

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_count": max(len(self.named_checks), self.test_functions),
            "check_names": sorted(self.named_checks),
            "run_check_sections": sorted(self.run_check_sections),
            "function_names": sorted(self.function_names),
            "membership_checks": self.membership_checks,
            "source_membership_checks": self.source_membership_checks,
            "string_index_calls": self.string_index_calls,
            "source_string_index_calls": self.source_string_index_calls,
            "regex_calls": self.regex_calls,
            "source_regex_calls": self.source_regex_calls,
            "source_reads": self.source_reads,
            "file_existence_checks": self.file_existence_checks,
            "dynamic_imports": self.dynamic_imports,
            "subprocess_calls": self.subprocess_calls,
            "json_load_calls": self.json_load_calls,
            "permissive_or_asserts": self.permissive_or_asserts,
            "early_returns_in_tests": self.early_returns_in_tests,
            "imports": sorted(self.imports),
            "code_path_variables": sorted(self.code_path_variables),
            "source_text_variables": sorted(self.source_text_variables),
        }


def analyze_python(path: Path, project_root: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(text, filename=str(path))
    signals = StaticSignals()
    signals.visit(tree)
    result = signals.as_dict()
    project_module_names = {
        candidate.stem
        for candidate in project_root.rglob("*.py")
        if candidate.name != "__init__.py"
    }
    result["project_imports"] = sorted(
        module
        for module in result["imports"]
        if module.split(".", 1)[0] in project_module_names
    )
    result.update({
        "path": str(path.resolve()),
        "line_count": len(text.splitlines()),
        "sha256": __import__("hashlib").sha256(text.encode()).hexdigest(),
    })
    return result


def sensitivity(process: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    lexical = (
        process["source_membership_checks"]
        + process["source_string_index_calls"]
        + process["source_regex_calls"]
    )
    behavioral = (
        process["dynamic_imports"]
        + process["subprocess_calls"]
        + process["json_load_calls"]
        + len(process["project_imports"])
    )
    if process["source_string_index_calls"]:
        reasons.append("exact source-token ordering")
    if process["source_membership_checks"] or process["source_regex_calls"]:
        reasons.append("literal or regex source-shape checks")
    if process["file_existence_checks"]:
        reasons.append("file/module existence checks")
    if process["permissive_or_asserts"]:
        reasons.append("OR-based process assertions")
    if process["early_returns_in_tests"]:
        reasons.append("conditional early-return in process test")
    if lexical and not behavioral:
        return "high", reasons
    if lexical or process["file_existence_checks"]:
        return "medium", reasons
    return "low", reasons


def rubric(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"present": False, "path": None, "dimensions": []}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    dimensions: list[dict[str, Any]] = []
    if isinstance(value, dict):
        raw = (
            value.get("dimensions")
            or value.get("scoring")
            or value.get("criteria")
            or value.get("rubric")
            or []
        )
        if isinstance(raw, list):
            dimensions = [item for item in raw if isinstance(item, dict)]
        elif isinstance(raw, dict):
            dimensions = [dict({"name": key}, **(item if isinstance(item, dict) else {"value": item})) for key, item in raw.items()]
    normalized: list[dict[str, Any]] = []
    for item in dimensions:
        name = item.get("name", item.get("dimension"))
        weight = item.get("weight")
        normalized.append({**item, "name": name, "weight": weight})
    numeric_weights = [
        float(item["weight"])
        for item in normalized
        if isinstance(item.get("weight"), (int, float))
    ]
    total_weight = sum(numeric_weights)
    declared_process_weight = sum(
        float(item["weight"])
        for item in normalized
        if isinstance(item.get("weight"), (int, float))
        and "process" in str(item.get("name", "")).lower()
    )
    if total_weight and total_weight <= 1.000001:
        declared_process_weight *= 100.0
        total_weight *= 100.0
    return {
        "present": True,
        "path": str(path.resolve()),
        "dimensions": normalized,
        "declared_total_weight": total_weight,
        "declared_process_weight_percent": declared_process_weight,
        "raw": value,
    }


def score_dimensions(path: Path) -> list[dict[str, Any]]:
    """Extract the static ``RUBRIC = [Dim(...)]`` table without importing code."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    dimensions: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "RUBRIC" for target in targets):
            continue
        value = node.value
        if not isinstance(value, (ast.List, ast.Tuple)):
            continue
        for item in value.elts:
            if not isinstance(item, ast.Call) or call_name(item) not in {"Dim", "Dimension"}:
                continue
            try:
                args = [ast.literal_eval(arg) for arg in item.args]
            except (ValueError, TypeError):
                continue
            if len(args) < 3 or not isinstance(args[0], str) or not isinstance(args[1], (int, float)):
                continue
            identifiers = args[2] if isinstance(args[2], (list, tuple)) else []
            identifiers = [str(identifier) for identifier in identifiers]
            name = args[0]
            is_process = "process" in name.lower() or any("process" in identifier.lower() for identifier in identifiers)
            dimensions.append({
                "name": name,
                "weight": float(args[1]),
                "identifiers": identifiers,
                "mode": str(args[3]) if len(args) >= 4 else "proportional",
                "kind": "process" if is_process else "outcome",
            })
    return dimensions


def scoring_path(task_root: Path, process: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    test_sh = task_root / "tests/test.sh"
    text = test_sh.read_text(encoding="utf-8", errors="replace")
    score_py = task_root / "tests/score.py"
    dimensions: list[dict[str, Any]] = []
    script_runtime = "run" in process["function_names"] and "run" in outcome["function_names"]
    if script_runtime:
        mode = "generic_script_groups"
        process_groups = len(process["run_check_sections"])
        outcome_groups = len(outcome["run_check_sections"])
        total_groups = process_groups + outcome_groups
        process_weight = 100.0 * process_groups / total_groups if total_groups else None
    elif score_py.exists():
        mode = "custom_score_py"
        dimensions = score_dimensions(score_py)
        total_weight = sum(dimension["weight"] for dimension in dimensions)
        process_weight = (
            100.0 * sum(
                dimension["weight"]
                for dimension in dimensions
                if dimension["kind"] == "process"
            ) / total_weight
            if total_weight
            else None
        )
    else:
        mode = "generic_pytest_files"
        process_weight = 50.0
    return {
        "mode": mode,
        "test_sh_path": str(test_sh.resolve()),
        "test_sh_sha256": __import__("hashlib").sha256(text.encode()).hexdigest(),
        "rubric_yaml_referenced": "rubric.yaml" in text,
        "score_py_path": str(score_py.resolve()) if score_py.exists() else None,
        "score_dimensions": dimensions if score_py.exists() else [],
        "effective_process_weight_percent": process_weight,
    }


def observed_by_task(evidence_path: Path | None) -> dict[str, list[dict[str, Any]]]:
    if not evidence_path or not evidence_path.exists():
        return {}
    evidence = load_json(evidence_path)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence.get("tasks", []):
        if (
            isinstance(row, dict)
            and row.get("task_id")
            and row.get("selected_run", True)
        ):
            grouped[str(row["task_id"])].append(row)
    return grouped


def build(
    tasks_root: Path,
    evidence_path: Path | None,
    tiers: set[int] | None = None,
) -> dict[str, Any]:
    selected_tiers = tiers if tiers is not None else {4, 5, 6}
    if not selected_tiers or not selected_tiers <= set(range(1, 7)):
        raise ValueError(f"tiers must be a non-empty subset of 1..6: {selected_tiers}")
    observed = observed_by_task(evidence_path)
    tasks: list[dict[str, Any]] = []
    for spec_path in sorted(tasks_root.glob("*/task-spec.yaml")):
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if (
            not isinstance(spec, dict)
            or int(spec.get("task_index", 0)) not in selected_tiers
        ):
            continue
        root = spec_path.parent
        process = analyze_python(root / "tests/test_process.py", root / "environment")
        outcome = analyze_python(root / "tests/test_outcome.py", root / "environment")
        risk, reasons = sensitivity(process)
        observations = observed.get(str(spec["task_id"]), [])
        by_condition: dict[str, dict[str, Any]] = {}
        for condition in sorted({str(row.get("condition")) for row in observations}):
            rows = [row for row in observations if str(row.get("condition")) == condition]
            by_condition[condition] = {
                "n": len(rows),
                "strict_passes": sum(row.get("strict_pass") is True for row in rows),
                "outcome_passes": sum(row.get("outcome_pass") is True for row in rows),
                "process_passes": sum(row.get("process_pass") is True for row in rows),
                "classifications": dict(sorted(Counter(str(row.get("classification")) for row in rows).items())),
            }
        declared_rubric = rubric(root / "tests/rubric.yaml")
        effective_scoring = scoring_path(root, process, outcome)
        tasks.append({
            "task_id": spec["task_id"],
            "task_slug": spec.get("task_slug"),
            "environment_id": spec.get("environment_id"),
            "family_id": spec.get("family_id"),
            "tier": int(spec["task_index"]),
            "role": spec.get("role"),
            "primary_skill": spec.get("primary_skill"),
            "required_skills": spec.get("required_skills") or [],
            "composition_type": spec.get("composition_type"),
            "instruction_path": str((root / "instruction.md").resolve()),
            "instruction": (root / "instruction.md").read_text(encoding="utf-8"),
            "process": process,
            "outcome": outcome,
            "rubric": declared_rubric,
            "effective_scoring": effective_scoring,
            "process_shape_sensitivity": risk,
            "process_shape_reasons": reasons,
            "observed": by_condition,
        })

    summary = {
        "task_count": len(tasks),
        "by_tier": dict(sorted(Counter(f"T{row['tier']}" for row in tasks).items())),
        "by_environment": dict(sorted(Counter(str(row["environment_id"]) for row in tasks).items())),
        "process_shape_sensitivity": dict(sorted(Counter(row["process_shape_sensitivity"] for row in tasks).items())),
        "tasks_with_exact_source_order_checks": sum(row["process"]["source_string_index_calls"] > 0 for row in tasks),
        "tasks_with_literal_or_regex_process_checks": sum(
            row["process"]["source_membership_checks"] + row["process"]["source_regex_calls"] > 0
            for row in tasks
        ),
        "tasks_with_process_early_returns": sum(row["process"]["early_returns_in_tests"] > 0 for row in tasks),
        "tasks_missing_rubric_yaml": sum(not row["rubric"]["present"] for row in tasks),
        "tasks_whose_test_sh_reads_rubric_yaml": sum(row["effective_scoring"]["rubric_yaml_referenced"] for row in tasks),
        "effective_scoring_modes": dict(sorted(Counter(row["effective_scoring"]["mode"] for row in tasks).items())),
        "tasks_with_effective_process_weight_50_percent": sum(row["effective_scoring"]["effective_process_weight_percent"] == 50.0 for row in tasks),
        "tasks_with_unknown_effective_process_weight": sum(row["effective_scoring"]["effective_process_weight_percent"] is None for row in tasks),
        "effective_process_weight_histogram": dict(sorted(Counter(
            str(row["effective_scoring"]["effective_process_weight_percent"])
            for row in tasks
        ).items())),
        "process_checks_total": sum(row["process"]["check_count"] for row in tasks),
        "outcome_checks_total": sum(row["outcome"]["check_count"] for row in tasks),
    }
    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tasks_root": str(tasks_root.resolve()),
        "evidence_path": str(evidence_path.resolve()) if evidence_path else None,
        "summary": summary,
        "tasks": tasks,
    }


def write_csv(path: Path, tasks: list[dict[str, Any]]) -> None:
    columns = [
        "task_id", "environment_id", "family_id", "tier", "role", "task_slug",
        "process_shape_sensitivity", "process_check_count", "outcome_check_count",
        "membership_checks", "string_index_calls", "regex_calls",
        "source_membership_checks", "source_string_index_calls", "source_regex_calls",
        "file_existence_checks", "permissive_or_asserts", "early_returns_in_tests",
        "rubric_present", "instruction_path", "process_path", "outcome_path",
        "effective_scoring_mode", "effective_process_weight_percent",
        "rubric_yaml_referenced",
    ]
    handle = io.StringIO(newline="")
    try:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for task in tasks:
            writer.writerow({
                "task_id": task["task_id"],
                "environment_id": task["environment_id"],
                "family_id": task["family_id"],
                "tier": task["tier"],
                "role": task["role"],
                "task_slug": task["task_slug"],
                "process_shape_sensitivity": task["process_shape_sensitivity"],
                "process_check_count": task["process"]["check_count"],
                "outcome_check_count": task["outcome"]["check_count"],
                "membership_checks": task["process"]["membership_checks"],
                "source_membership_checks": task["process"]["source_membership_checks"],
                "string_index_calls": task["process"]["string_index_calls"],
                "source_string_index_calls": task["process"]["source_string_index_calls"],
                "regex_calls": task["process"]["regex_calls"],
                "source_regex_calls": task["process"]["source_regex_calls"],
                "file_existence_checks": task["process"]["file_existence_checks"],
                "permissive_or_asserts": task["process"]["permissive_or_asserts"],
                "early_returns_in_tests": task["process"]["early_returns_in_tests"],
                "rubric_present": task["rubric"]["present"],
                "effective_scoring_mode": task["effective_scoring"]["mode"],
                "effective_process_weight_percent": task["effective_scoring"]["effective_process_weight_percent"],
                "rubric_yaml_referenced": task["effective_scoring"]["rubric_yaml_referenced"],
                "instruction_path": task["instruction_path"],
                "process_path": task["process"]["path"],
                "outcome_path": task["outcome"]["path"],
            })
        atomic_write_text(path, handle.getvalue())
    finally:
        handle.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, default=Path("benchmark/tasks"))
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--tiers",
        default="4,5,6",
        help="comma-separated task tiers to audit (default: 4,5,6)",
    )
    parser.add_argument(
        "--output-prefix",
        default="t56_verifier_audit",
        help="basename for the emitted JSON and CSV files",
    )
    args = parser.parse_args()
    try:
        tiers = {int(value.strip()) for value in args.tiers.split(",") if value.strip()}
    except ValueError as exc:
        parser.error(f"--tiers must contain integers: {exc}")
    if not tiers or not tiers <= set(range(1, 7)):
        parser.error("--tiers must be a non-empty subset of 1,2,3,4,5,6")
    if not args.output_prefix or Path(args.output_prefix).name != args.output_prefix:
        parser.error("--output-prefix must be a non-empty filename prefix")
    result = build(args.tasks_root, args.evidence, tiers)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.output_prefix}.json"
    csv_path = args.output_dir / f"{args.output_prefix}.csv"
    atomic_write_text(
        json_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    write_csv(csv_path, result["tasks"])
    print(json.dumps({"json": str(json_path.resolve()), "csv": str(csv_path.resolve()), **result["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
