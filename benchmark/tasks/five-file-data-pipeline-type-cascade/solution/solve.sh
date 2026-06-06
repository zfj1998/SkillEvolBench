#!/bin/bash
# Oracle solution for E1-LS4-T1: five-file-data-pipeline-type-cascade
# Root cause: validator.py converts Decimal to float, causing precision loss
# Fix: Remove the float() conversion, keep amounts as Decimal

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

# Fix validator.py - remove float conversion
sed -i 's/    record\["amount"\] = float(record\["amount"\])/    # Keep amount as-is (preserve Decimal type)\n    pass/' validator.py

echo "Fix applied: removed float() conversion in validator.py"
echo "Amounts now stay as Decimal throughout the pipeline"
