from __future__ import annotations

FIELD_ORDER = [
    "name",
    "id",
    "department",
    "start_date",
    "salary",
    "manager",
    "office",
]

# Legacy export aliases are intentionally incomplete in the starter.
# The HR exporter sometimes emits Start_Date instead of Start Date.
LABEL_ALIASES = {
    "name": ["Name"],
    "id": ["ID"],
    "department": ["Department"],
    "start_date": ["Start Date"],
    "salary": ["Salary"],
    "manager": ["Manager"],
    "office": ["Office"],
}
