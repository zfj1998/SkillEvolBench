from __future__ import annotations

from datetime import date, timedelta


def previous_month_window(anchor=None):
    anchor = anchor or date(2025, 4, 15)
    first_this_month = date(anchor.year, anchor.month, 1)
    last_prev_month = first_this_month - timedelta(days=1)
    first_prev_month = date(last_prev_month.year, last_prev_month.month, 1)
    return first_prev_month.isoformat(), last_prev_month.isoformat()
