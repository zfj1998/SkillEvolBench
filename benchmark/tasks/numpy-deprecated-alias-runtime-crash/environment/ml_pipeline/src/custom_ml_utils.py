import numpy as np


def advanced_calculate(values):
    """Process values: normalize scalars and arrays."""
    if isinstance(values, (int, float)):
        converted = np.float(values)
        return round(converted * 2.0 + 1.0, 6)
    result = []
    for v in values:
        converted = np.float(v)
        length = np.int(len(values))
        scaled = converted / length
        result.append(round(scaled, 6))
    return result


def prepare_batch(records, keep_metadata=False):
    """Prepare a batch of records for processing."""
    batch = []
    for rec in records:
        row = {}
        for key, val in rec.items():
            if isinstance(val, str) and not keep_metadata:
                continue
            try:
                row[key] = float(val)
            except (ValueError, TypeError):
                row[key] = val
        batch.append(row)
    mask = [np.bool(len(row) > 0) for row in batch]
    valid_batch = [b for b, m in zip(batch, mask) if m]
    return valid_batch
