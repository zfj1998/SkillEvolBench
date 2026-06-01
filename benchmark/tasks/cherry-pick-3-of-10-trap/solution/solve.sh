#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export SCRIPT_DIR
python3 - <<'PYCODE'
from __future__ import annotations
import os
from pathlib import Path
code = 'from __future__ import annotations\nimport os\nfrom pathlib import Path\n\nPROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()\nFILES = {\n    "cherry_pick_guard.py": "from __future__ import annotations\\ndef select_dimensions(all_dimensions):\\n    return list(all_dimensions)\\n"\n}\n\ndef main():\n    for name, content in FILES.items():\n        (PROJECT_ROOT / name).write_text(content, encoding="utf-8")\n\nif __name__ == "__main__":\n    main()\n'
globals_dict = {
    "__name__": "__main__",
    "__file__": str(Path(os.environ["SCRIPT_DIR"]) / "solve.py"),
}
exec(compile(code, globals_dict["__file__"], "exec"), globals_dict)
PYCODE
