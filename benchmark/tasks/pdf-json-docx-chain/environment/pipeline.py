
import json
from pathlib import Path

from docx_writer import build_docx
from json_bridge import write_json
from pdf_extract import extract_financials

ROOT = Path(__file__).resolve().parent
PDF = ROOT / "quarterly_report.pdf"
JSON_OUT = ROOT / "extracted.json"
DOCX_OUT = ROOT / "report.docx"

def main():
    data = extract_financials(PDF)
    write_json(JSON_OUT, data)
    build_docx(DOCX_OUT, data)

if __name__ == "__main__":
    main()
