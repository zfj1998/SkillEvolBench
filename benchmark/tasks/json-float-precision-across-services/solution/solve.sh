#!/bin/bash
# Oracle solution for E1-LS4-T3: json-float-precision-across-services
# Fix: Use Decimal arithmetic in calculator.py

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('service_a/calculator.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Order total calculator for Service A - uses Decimal for precision."""\nfrom decimal import Decimal\n\n\ndef calculate_order_total(quantity, unit_price):\n    """Calculate order total using Decimal arithmetic."""\n    return Decimal(str(quantity)) * Decimal(str(unit_price))\n\n\ndef recalculate_order(order):\n    """Recalculate an order\'s total for verification."""\n    total = calculate_order_total(order["quantity"], order["unit_price"])\n    return {\n        "id": order["id"],\n        "item": order["item"],\n        "quantity": order["quantity"],\n        "unit_price": str(order["unit_price"]),\n        "calculated_total": str(total),\n    }\n', encoding='utf-8')
PYWRITE_1

echo "Fix applied: calculator.py now uses Decimal arithmetic"
