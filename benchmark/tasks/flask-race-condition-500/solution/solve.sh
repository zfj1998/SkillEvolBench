#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PATCH'
with open("utils.py", "r", encoding="utf-8") as f:
    src = f.read()

if "import threading" not in src:
    src = src.replace("import hashlib", "import hashlib\nimport threading")

if "_slot_lock" not in src:
    src = src.replace(
        "_slot_registry: Dict[str, float] = {}",
        "_slot_registry: Dict[str, float] = {}\n_slot_lock = threading.Lock()",
    )

old_acquire = """def _acquire_slot(computation_id: str) -> None:
    \"\"\"Mark a computation as active.\"\"\"
    _slot_registry[computation_id] = time.time()"""

new_acquire = """def _acquire_slot(computation_id: str) -> None:
    \"\"\"Mark a computation as active.\"\"\"
    with _slot_lock:
        _slot_registry[computation_id] = time.time()"""

src = src.replace(old_acquire, new_acquire)

old_release = """def _release_slot(computation_id: str) -> None:
    \"\"\"Finalize a computation: record elapsed time and free the slot.\"\"\"
    start_ts = _slot_registry[computation_id]
    elapsed = time.time() - start_ts
    del _slot_registry[computation_id]
    logger.debug(\"Completed %s in %.1fms\", computation_id, elapsed * 1000)"""

new_release = """def _release_slot(computation_id: str) -> None:
    \"\"\"Finalize a computation: record elapsed time and free the slot.\"\"\"
    with _slot_lock:
        start_ts = _slot_registry.pop(computation_id, None)
    elapsed = (time.time() - start_ts) if start_ts is not None else 0
    logger.debug(\"Completed %s in %.1fms\", computation_id, elapsed * 1000)"""

src = src.replace(old_release, new_release)

with open("utils.py", "w", encoding="utf-8") as f:
    f.write(src)
PATCH
