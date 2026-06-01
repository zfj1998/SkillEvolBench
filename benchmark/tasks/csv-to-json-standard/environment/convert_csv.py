
import csv
import json
from pathlib import Path

from type_inference import infer_value

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "transactions.csv"
OUTPUT = ROOT / "output.json"

def convert():
    rows = []
    with INPUT.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: infer_value(k, v) for k, v in row.items()})
    OUTPUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")

if __name__ == "__main__":
    convert()
