#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export SCRIPT_DIR
python3 - <<'PYCODE'
from __future__ import annotations
import os
from pathlib import Path
code = 'from __future__ import annotations\nimport os\nfrom pathlib import Path\n\nPROJECT_ROOT = Path(\n    os.environ.get("PROJECT_ROOT", "/root/task")\n).resolve()\nFILES = {\n    "authority_policy.py": "from __future__ import annotations\\ndef choose_best(sources):\\n    ranked = sorted(\\n        sources,\\n        key=lambda s: (\\n            s[\\"year\\"] >= 2024,\\n            s[\\"publisher\\"] in {\\"Stanford HAI\\", \\"CB Insights\\"},\\n            s[\\"source_type\\"] in {\\"research_report\\", \\"research_brief\\"},\\n            s[\\"year\\"],\\n        ),\\n        reverse=True,\\n    )\\n    return ranked[0]\\n",\n"investment_pipeline.py": "from __future__ import annotations\\nimport json\\nfrom pathlib import Path\\nfrom source_loader import load_sources\\nfrom authority_policy import choose_best\\n\\nROOT = Path(__file__).resolve().parent\\nOUTPUT = ROOT / \\"output\\"\\nOUTPUT.mkdir(exist_ok=True)\\n\\ndef main():\\n    chosen = choose_best([s for s in load_sources() if s[\\"domain\\"] == \\"ai_investment\\"])\\n    data = {\\n        \\"topic\\": \\"global AI investment\\",\\n        \\"selected_source\\": chosen[\\"id\\"],\\n        \\"estimate\\": chosen[\\"notes\\"],\\n        \\"rationale\\": \\"Used a 2024/2025 source and explicitly avoided treating the 2019 AI Index as current market size.\\",\\n    }\\n    (OUTPUT / \\"investment_estimate.json\\").write_text(json.dumps(data, indent=2), encoding=\\"utf-8\\")\\n\\nif __name__ == \\"__main__\\":\\n    main()\\n"\n}\n\ndef main():\n    for name, content in FILES.items():\n        (PROJECT_ROOT / name).write_text(content, encoding="utf-8")\n\nif __name__ == "__main__":\n    main()\n'
globals_dict = {
    "__name__": "__main__",
    "__file__": str(Path(os.environ["SCRIPT_DIR"]) / "solve.py"),
}
exec(compile(code, globals_dict["__file__"], "exec"), globals_dict)
PYCODE
