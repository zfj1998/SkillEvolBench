import json
from pathlib import Path
from pypdf import PdfReader

from charge_policy import total_cost
from quote_parser import parse_quote_text

ROOT = Path(__file__).resolve().parent

def read_pdf(path):
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def compare(a, b):
    better = 'A' if a['total_cost'] <= b['total_cost'] else 'B'
    return {
        'recommended_supplier': better,
        'basis': 'lower visible quoted total',
        'quote_a_total_cost': a['total_cost'],
        'quote_b_total_cost': b['total_cost'],
        'result_exists': True,
    }

def main():
    a = parse_quote_text(read_pdf(ROOT/'supplier_a_quote.pdf'), 'A')
    b = parse_quote_text(read_pdf(ROOT/'supplier_b_quote.pdf'), 'B')
    a['total_cost'] = total_cost(a)
    b['total_cost'] = total_cost(b)
    print(json.dumps({'quote_a': a, 'quote_b': b, 'comparison': compare(a,b)}, indent=2))

if __name__ == '__main__':
    main()
