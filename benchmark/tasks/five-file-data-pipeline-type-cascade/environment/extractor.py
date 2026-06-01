"""Data extractor module - pulls records from database."""
from decimal import Decimal
from amount_audit import attach_snapshot

# Simulated database records
MOCK_DB = [
    {"id": 1, "name": "Order A", "amount": Decimal("100.50")},
    {"id": 2, "name": "Order B", "amount": Decimal("0.30")},
    {"id": 3, "name": "Order C", "amount": Decimal("999999.99")},
    {"id": 4, "name": "Order D", "amount": Decimal("50.10")},
    {"id": 5, "name": "Order E", "amount": Decimal("0.10")},
]

# Historical amounts for comparison (what amounts were last time)
HISTORICAL_DB = {
    1: Decimal("100.50"),
    2: Decimal("0.30"),
    3: Decimal("999999.99"),
    4: Decimal("50.10"),
    5: Decimal("0.10"),
}


def extract_records():
    """Extract records from the database."""
    return [attach_snapshot(dict(r)) for r in MOCK_DB]


def get_historical_amount(record_id):
    """Get the historical amount for a given record ID."""
    return HISTORICAL_DB.get(record_id)
