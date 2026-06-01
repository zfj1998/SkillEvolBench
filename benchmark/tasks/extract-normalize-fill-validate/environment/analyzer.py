import json, re
from pathlib import Path
from pypdf import PdfReader
from consistency_check import totals_match
from date_normalizer import normalize_invoice_date
from erp_writer import write_rows
ROOT = Path(__file__).resolve().parent

def extract_pdf_text(path):
    reader = PdfReader(str(path))
    return '\n'.join(page.extract_text() or '' for page in reader.pages)

def extract(text):
    invoice_id = re.search(r'Invoice (INV-\d+)', text).group(1)
    invoice_date = re.search(r'Invoice Date:\s*(\d{2}/\d{2}/\d{4})', text).group(1)
    customer = re.search(r'Customer:\s*([^\n]+)', text).group(1).strip()
    items = [{'item_description': d.strip(), 'amount': float(a)} for d,a in re.findall(r'\d+\.\s*([^|\n]+)\| Amount:\s*\$(\d+\.\d+)', text)]
    total = float(re.search(r'Total Amount:\s*\$(\d+,?\d*\.\d+)', text).group(1).replace(',',''))
    return {'invoice_id': invoice_id, 'invoice_date': invoice_date, 'customer': customer, 'items': items, 'total': total}

def main():
    data = extract(extract_pdf_text(ROOT/'invoice.pdf'))
    data["invoice_date"] = normalize_invoice_date(data["invoice_date"])
    write_rows(data, ROOT/'filled_erp.csv')
    validated = totals_match(data["total"], data["items"])
    (ROOT/'pipeline_report.json').write_text(json.dumps({'extracted': True, 'normalized': False, 'filled_csv': True, 'validated': validated, 'pdf_total': data['total']}, indent=2))
if __name__ == '__main__':
    main()
