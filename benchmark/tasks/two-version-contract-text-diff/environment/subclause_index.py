from __future__ import annotations

import re


def extract_fee_subclauses(text: str) -> dict[str, str]:
    matches = re.findall(r"(?m)^(3\.\d)\s+(.*?)(?=^3\.\d|\Z)", text, flags=re.DOTALL)
    return {key: " ".join(value.split()) for key, value in matches}
