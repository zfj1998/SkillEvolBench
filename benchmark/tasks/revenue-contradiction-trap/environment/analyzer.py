import json
from pathlib import Path
from pypdf import PdfReader
from conflict_policy import summarize_revenue_conflict
from revenue_sources import extract_revenue_evidence
ROOT = Path(__file__).resolve().parent

def read_pdf(path):
    reader = PdfReader(str(path))
    return [page.extract_text() or '' for page in reader.pages]

def main():
    pages = read_pdf(ROOT/'annual_report.pdf')
    evidence = extract_revenue_evidence(pages)
    print(json.dumps(summarize_revenue_conflict(evidence), indent=2))
if __name__ == '__main__':
    main()
