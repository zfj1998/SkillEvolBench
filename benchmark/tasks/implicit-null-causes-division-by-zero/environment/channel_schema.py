from __future__ import annotations

import math
import re

PLACEHOLDERS = {"", "na", "n/a", "null", "none", "-"}


def normalize_header(name: object) -> str:
    if name is None:
        return ""
    return str(name).replace("\ufeff", "").strip().lower()


def remove_zero_width(value: str) -> str:
    return re.sub(r"[\u200b\u200c\u200d\ufeff]", "", value)


def normalize_channel(value: object) -> str:
    if value is None:
        return ""
    text = remove_zero_width(str(value)).strip().lower()
    text = text.replace("-", "_")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def parse_metric(raw: object) -> tuple[float | int | None, str]:
    if raw is None:
        return None, "missing"
    text = str(raw).strip()
    if text == "":
        return None, "missing"
    if text.lower() in PLACEHOLDERS:
        return None, "missing"
    text = text.replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return None, "invalid"
    if not math.isfinite(value) or value < 0:
        return None, "invalid"
    if abs(value - round(value)) < 1e-9:
        return int(round(value)), "ok"
    return value, "ok"
