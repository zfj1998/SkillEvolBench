# Contract Cross-Reference Fixture

This fixture models a legal-review utility that indexes references inside a contract.

Relevant files:
- `contract.txt`: contract body with section, appendix, and schedule references
- `clause_index.py`: identifies the current source node while scanning lines
- `reference_patterns.py`: finds supported reference targets
- `analyzer.py`: assembles the graph and reports cycles

Starter limitations:
- appendix and schedule references are not fully surfaced
- subsection letters like `3.2(b)` are fragile
- the graph is built, but cycle detection is still missing
