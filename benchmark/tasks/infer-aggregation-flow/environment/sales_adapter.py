from __future__ import annotations


def normalize_rows(payload: dict[str, object]) -> list[dict[str, float | str]]:
    currency = payload['currency']
    if 'sales' in payload:
        return [{'currency': currency, 'product_line': row['product_line'], 'amount': row['amount']} for row in payload['sales']]
    if 'records' in payload:
        return [{'currency': currency, 'product_line': row['line'], 'amount': row['revenue']} for row in payload['records']]
    return [{'currency': currency, 'product_line': row['product'], 'amount': row['total']} for row in payload['rows']]
