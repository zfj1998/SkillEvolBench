from __future__ import annotations

from pathlib import Path

import pandas as pd

from denominator_policy import select_denominator


def load_orders(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    return frame


def compute_amount_summary(frame: pd.DataFrame) -> dict:
    total_rows = int(len(frame))
    valid_amounts = frame["amount"].dropna()
    total_amount = float(valid_amounts.sum())
    missing_amount_count = int(frame["amount"].isna().sum())
    denominator = select_denominator(
        total_rows=total_rows,
        valid_amount_count=int(valid_amounts.shape[0]),
        missing_amount_count=missing_amount_count,
    )
    denominator_used = int(denominator["denominator_used"])
    average_amount = round(total_amount / denominator_used, 4) if denominator_used else 0.0
    return {
        "average_amount": average_amount,
        "total_rows": total_rows,
        "valid_amount_count": int(valid_amounts.shape[0]),
        "missing_amount_count": missing_amount_count,
        "total_amount": round(total_amount, 4),
        "denominator_used": denominator_used,
        "denominator_strategy": denominator["denominator_strategy"],
    }
