#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cat > "$PROJECT_ROOT/analyzer.py" <<'__SKILL_EVOL_REFERENCE_ANALYZER_PY_0__'
import json
import sys
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from clause_index import index_sources
from reference_patterns import extract_reference_candidates

CLAUSE_RE = re.compile(r"^(\d+\.\d+(?:\([a-z]\))?)\s+")
SUBCLAUSE_RE = re.compile(r"^\(([a-z])\)\s+")


def extract_references(text: str) -> List[dict]:
    refs: List[dict] = []
    source_by_line = index_sources(text)
    current_parent_clause = None
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        current_source = source_by_line[lineno]
        if current_source == "document:root":
            continue
        if match := CLAUSE_RE.match(line):
            current_parent_clause = match.group(1).split("(", 1)[0]
            current_source = f"section:{match.group(1)}"
        elif match := SUBCLAUSE_RE.match(line):
            if current_parent_clause:
                current_source = f"section:{current_parent_clause}({match.group(1)})"
        for candidate in extract_reference_candidates(line, include_appendix_and_schedule=True):
            if candidate["target"] == current_source:
                continue
            refs.append(
                {
                    "source": current_source,
                    "target": candidate["target"],
                    "target_type": candidate["target_type"],
                }
            )
    return refs


def build_graph(references: List[dict]) -> Dict[str, List[str]]:
    graph = defaultdict(list)
    for ref in references:
        graph[ref["source"]].append(ref["target"])
    return dict(graph)


def detect_cycles(references: List[dict]) -> List[List[str]]:
    graph = build_graph(references)
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        visiting.add(node)
        stack.append(node)
        for neighbor in graph.get(node, []):
            if neighbor in visiting:
                idx = stack.index(neighbor)
                cycles.append(stack[idx:].copy())
            elif neighbor not in visited:
                dfs(neighbor)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        if node not in visited:
            dfs(node)
    return cycles


def analyze_contract(contract_path: str) -> dict:
    text = Path(contract_path).read_text(encoding="utf-8")
    references = extract_references(text)
    cycles = detect_cycles(references)
    return {"references": references, "cycles": cycles}


def main() -> None:
    contract_path = Path(__file__).with_name("contract.txt")
    result = analyze_contract(str(contract_path))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_ANALYZER_PY_0__
