#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export SCRIPT_DIR
python3 - <<'PYCODE'
from __future__ import annotations
import os
from pathlib import Path
code = 'from __future__ import annotations\nimport os\nfrom pathlib import Path\n\nPROJECT_ROOT = Path(\n    os.environ.get("PROJECT_ROOT", "/root/task")\n).resolve()\nFILES = {\n    "authority_policy.py": "from __future__ import annotations\\n\\ndef source_score(source: dict) -> float:\\n    score = 0.0\\n    if source[\\"domain\\"] == \\"ai_chip_market\\":\\n        score += 4.0\\n    if source[\\"year\\"] >= 2024:\\n        score += 4.0\\n    if source[\\"source_type\\"] in {\\"research_summary\\", \\"press_release\\", \\"research_report\\"}:\\n        score += 1.5\\n    if source[\\"publisher\\"] in {\\"Gartner\\", \\"Stanford HAI\\"}:\\n        score += 1.0\\n    if source[\\"year\\"] < 2024:\\n        score -= 4.0\\n    return score\\n",\n"market_pipeline.py": "from __future__ import annotations\\nimport json\\nfrom pathlib import Path\\nfrom source_loader import load_sources\\nfrom authority_policy import source_score\\n\\nROOT = Path(__file__).resolve().parent\\nOUTPUT = ROOT / \\"output\\"\\nOUTPUT.mkdir(exist_ok=True)\\n\\ndef main():\\n    chip_sources = [s for s in load_sources() if s[\\"domain\\"] == \\"ai_chip_market\\"]\\n    sources = sorted(chip_sources, key=source_score, reverse=True)\\n    chosen = sources[0]\\n    data = {\\n        \\"topic\\": \\"current AI chip market size\\",\\n        \\"selected_source\\": chosen[\\"id\\"],\\n        \\"estimate\\": chosen[\\"notes\\"],\\n        \\"reasoning\\": f\\"Prioritized {chosen[\'year\']} source {chosen[\'publisher\']} for current market sizing and explicitly deprioritized older figures.\\",\\n    }\\n    (OUTPUT / \\"market_estimate.json\\").write_text(json.dumps(data, indent=2), encoding=\\"utf-8\\")\\n\\nif __name__ == \\"__main__\\":\\n    main()\\n"\n}\n\ndef main():\n    for name, content in FILES.items():\n        (PROJECT_ROOT / name).write_text(content, encoding="utf-8")\n\nif __name__ == "__main__":\n    main()\n'
globals_dict = {
    "__name__": "__main__",
    "__file__": str(Path(os.environ["SCRIPT_DIR"]) / "solve.py"),
}
exec(compile(code, globals_dict["__file__"], "exec"), globals_dict)
PYCODE
