from __future__ import annotations

import json
from pathlib import Path

import mock_api
from currency_policy import to_usd
from sales_adapter import normalize_rows
from source_registry import load_sources

REGIONS_FILE = Path(__file__).with_name('regions.json')
RATES_FILE = Path(__file__).with_name('exchange_rates.json')


def run(output_path: str | Path = 'summary.json'):
    regions = load_sources(REGIONS_FILE)
    exchange_rates = json.loads(RATES_FILE.read_text(encoding='utf-8'))
    aggregated: dict[str, float] = {}
    for region in regions:
        payload = mock_api.fetch_sales(region['endpoint'])
        for row in normalize_rows(payload):
            usd_value = to_usd(row['amount'], row['currency'], exchange_rates)
            aggregated[row['product_line']] = round(aggregated.get(row['product_line'], 0.0) + usd_value, 2)
    lines = [{'product_line': key, 'total_usd': aggregated[key]} for key in sorted(aggregated)]
    summary = {'currency': 'USD', 'lines': lines, 'grand_total_usd': round(sum(aggregated.values()), 2)}
    Path(output_path).write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    run()
