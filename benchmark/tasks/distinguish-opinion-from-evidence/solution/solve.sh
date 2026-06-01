#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export SCRIPT_DIR
python3 - <<'PYCODE'
from __future__ import annotations
import os
from pathlib import Path
code = 'from __future__ import annotations\nimport os\nfrom pathlib import Path\n\nPROJECT_ROOT = Path(\n    os.environ.get("PROJECT_ROOT", "/root/task")\n).resolve()\nFILES = {\n    "evidence_policy.py": "from __future__ import annotations\\n\\ndef classify(source: dict) -> tuple[str, str]:\\n    source_type = source.get(\\"source_type\\", \\"\\")\\n    text = source[\\"notes\\"].lower()\\n    if source_type in {\\"randomized_controlled_trial\\", \\"working_paper\\", \\"peer_reviewed_article\\", \\"survey\\", \\"research_brief\\"}:\\n        if any(token in text for token in [\\"sample\\", \\"survey\\", \\"field experiment\\", \\"working paper\\", \\"study\\", \\"productivity\\", \\"measur\\"]):\\n            return \\"evidence\\", \\"has explicit method, sample, or study design\\"\\n    if source_type in {\\"opinion_post\\", \\"commentary\\", \\"news_quote\\"}:\\n        return \\"opinion\\", \\"primarily viewpoint or quoted sentiment without formal methodology\\"\\n    if source_type == \\"news_analysis\\":\\n        return \\"opinion\\", \\"mixed journalistic synthesis without standalone methods section\\"\\n    return \\"opinion\\", \\"insufficient methodological grounding\\"\\n"\n}\n\ndef main():\n    for name, content in FILES.items():\n        (PROJECT_ROOT / name).write_text(content, encoding="utf-8")\n\nif __name__ == "__main__":\n    main()\n'
globals_dict = {
    "__name__": "__main__",
    "__file__": str(Path(os.environ["SCRIPT_DIR"]) / "solve.py"),
}
exec(compile(code, globals_dict["__file__"], "exec"), globals_dict)
PYCODE
