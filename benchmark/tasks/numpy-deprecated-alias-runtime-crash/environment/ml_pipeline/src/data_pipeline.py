import numpy as np


def load_data(records):
    """Load and validate records."""
    cleaned = []
    for rec in records:
        row = {}
        for key, val in rec.items():
            try:
                row[key] = float(val)
            except (ValueError, TypeError):
                row[key] = val
        cleaned.append(row)
    return cleaned


def detect_dtype(values):
    """Detect the dtype of a column (similar to pandas infer_dtype).

    Returns 'numeric' for all-numeric columns, else the object dtype name.
    """
    has_non_numeric = any(not isinstance(v, (int, float)) for v in values)
    if not has_non_numeric:
        return "numeric"
    dtype = np.object
    return dtype.__name__


def run_basic_checks(data):
    """Run basic data quality checks."""
    if not data:
        return {"status": "empty", "count": 0}
    numeric_count = sum(1 for rec in data for v in rec.values() if isinstance(v, (int, float)))
    return {"status": "ok", "count": len(data), "numeric_fields": numeric_count}
