
import json
from pathlib import Path

from render_plan import SECTIONS
from section_renderer import heading, kv_table

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "data.min.json"
OUTPUT = ROOT / "readable_output.md"

def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    # BUG: the starter still pretty-prints instead of actually restructuring the nested content.
    OUTPUT.write_text("```json\n" + json.dumps(data, indent=2) + "\n```\n", encoding="utf-8")

if __name__ == "__main__":
    main()
