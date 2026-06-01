#!/bin/bash
# Oracle solution for E1-LS4-T6
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

# Fix 1: models/order.py - use Decimal
python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('models/order.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Order ORM model (simulated SQLAlchemy) - Fixed: uses Decimal."""\nfrom decimal import Decimal\n\n\nclass Order:\n    def __init__(self, id, customer, items_count, unit_price, total_amount):\n        self.id = id\n        self.customer = customer\n        self.items_count = items_count\n        self.unit_price = unit_price\n        self.total_amount = Decimal(str(total_amount))\n\n    def to_dict(self):\n        return {\n            "id": self.id,\n            "customer": self.customer,\n            "items_count": self.items_count,\n            "unit_price": self.unit_price,\n            "total_amount": str(self.total_amount),\n        }\n\nORDERS = {\n    "ORD-1001": Order("ORD-1001", "Alice", 7, 7.141428571428571, 49.99),\n    "ORD-1002": Order("ORD-1002", "Bob", 1, 100.00, 100.00),\n    "ORD-1003": Order("ORD-1003", "Charlie", 3, 0.10, 0.30),\n    "ORD-1004": Order("ORD-1004", "Diana", 10, 9.99, 99.90),\n}\n', encoding='utf-8')
PYWRITE_1

# Fix 2: Add integration tests
python3 - <<'PYWRITE_2'
from pathlib import Path
baseline = Path('public_tests/test_orders.py')
baseline.parent.mkdir(parents=True, exist_ok=True)
baseline.write_text('"""Baseline order route tests retained for the integration suite."""\nimport json\nimport os\nimport sys\n\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))\nfrom api.routes import handle_get_order\n\n\ndef test_get_known_order():\n    body, status = handle_get_order("ORD-1002")\n    assert status == 200\n    data = json.loads(body)\n    assert data["id"] == "ORD-1002"\n', encoding='utf-8')
target = Path('public_tests/test_integration.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Integration tests for order precision."""\nimport sys, os, json\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))\nfrom api.routes import handle_get_order\n\ndef test_precision_ord_1001():\n    body, _ = handle_get_order("ORD-1001")\n    data = json.loads(body)\n    assert data["total_amount"] == "49.99"\n\ndef test_precision_ord_1003():\n    body, _ = handle_get_order("ORD-1003")\n    data = json.loads(body)\n    assert data["total_amount"] == "0.30" or data["total_amount"] == "0.3"\n', encoding='utf-8')
PYWRITE_2

# Fix 3: Update OpenAPI - total_amount is now string
# (already declared as string in the spec, which now matches)

echo "Fix applied: Decimal model + integration tests + docs consistent"
