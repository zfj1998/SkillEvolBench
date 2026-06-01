import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from clause_index import index_sources
from reference_patterns import extract_reference_candidates


def extract_references(text: str) -> List[dict]:
    indexed_sources = index_sources(text)
    refs: List[dict] = []

    for lineno, line in enumerate(text.splitlines(), start=1):
        source = indexed_sources[lineno]
        # BUG: appendix and schedule extraction is still disabled in the starter.
        for candidate in extract_reference_candidates(line, include_appendix_and_schedule=False):
            refs.append({"source": source, **candidate})
    return refs


def build_graph(references: List[dict]) -> Dict[str, List[str]]:
    graph = defaultdict(list)
    for ref in references:
        graph[ref["source"]].append(ref["target"])
    return dict(graph)


def detect_cycles(references: List[dict]) -> List[List[str]]:
    # Bug: not implemented.
    return []


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
