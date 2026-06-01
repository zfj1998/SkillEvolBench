#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export SCRIPT_DIR
python3 - <<'PYCODE'
from __future__ import annotations
import os
from pathlib import Path
code = 'from __future__ import annotations\nimport os\nfrom pathlib import Path\n\nPROJECT_ROOT = Path(\n    os.environ.get("PROJECT_ROOT", "/root/task")\n).resolve()\nFILES = {\n    "dimension_weights.py": "WEIGHTS = {\\"relevance\\": 0.40, \\"evidence\\": 0.35, \\"recency\\": 0.25}\\n",\n"ranking_policy.py": "from __future__ import annotations\\nfrom dimension_weights import WEIGHTS\\n\\ndef score(source: dict) -> float:\\n    tags = {t.lower() for t in source.get(\\"tags\\", [])}\\n    relevance = 0.0\\n    if \\"medical diagnosis\\" in tags:\\n        relevance = 1.0\\n    elif \\"healthcare\\" in tags:\\n        relevance = 0.55\\n    elif \\"medical diagnosis\\" not in tags and \\"healthcare\\" not in tags:\\n        relevance = 0.1\\n    evidence = {\\"high\\": 1.0, \\"medium\\": 0.6, \\"low\\": 0.2}.get(source.get(\\"evidence_strength\\"), 0.1)\\n    recency = max(0.1, min(1.0, (source[\\"year\\"] - 2018) / 7))\\n    if source.get(\\"tier\\") == \\"irrelevant\\":\\n        relevance = 0.0\\n    return relevance * WEIGHTS[\\"relevance\\"] + evidence * WEIGHTS[\\"evidence\\"] + recency * WEIGHTS[\\"recency\\"]\\n",\n"multi_factor_pipeline.py": "from __future__ import annotations\\nimport json\\nfrom pathlib import Path\\nfrom source_loader import load_sources\\nfrom ranking_policy import score\\n\\nROOT = Path(__file__).resolve().parent\\nOUTPUT = ROOT / \\"output\\"\\nOUTPUT.mkdir(exist_ok=True)\\n\\ndef main():\\n    ranked = sorted(load_sources(), key=score, reverse=True)[:5]\\n    result = {\\"selected\\": [s[\\"id\\"] for s in ranked], \\"dimensions\\": [\\"relevance\\", \\"evidence\\", \\"recency\\"]}\\n    (OUTPUT / \\"selection.json\\").write_text(json.dumps(result, indent=2), encoding=\\"utf-8\\")\\n    (OUTPUT / \\"summary.md\\").write_text(\\n        \\"# Summary\\\\n\\\\nSelected sources balance topical fit, evidence quality, and recency.\\\\n\\",\\n        encoding=\\"utf-8\\",\\n    )\\n\\nif __name__ == \\"__main__\\":\\n    main()\\n"\n}\n\ndef main():\n    for name, content in FILES.items():\n        (PROJECT_ROOT / name).write_text(content, encoding="utf-8")\n\nif __name__ == "__main__":\n    main()\n'
globals_dict = {
    "__name__": "__main__",
    "__file__": str(Path(os.environ["SCRIPT_DIR"]) / "solve.py"),
}
exec(compile(code, globals_dict["__file__"], "exec"), globals_dict)
PYCODE
