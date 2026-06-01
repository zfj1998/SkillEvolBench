from __future__ import annotations


def project_row(row, index):
    projected = dict(row)
    projected["_row_index"] = index
    return projected
