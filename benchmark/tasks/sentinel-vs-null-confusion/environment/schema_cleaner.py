from __future__ import annotations

import re
import unicodedata


def clean_text(value: object) -> str:
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    text = text.strip().strip('"').strip("'").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_header(header: object) -> str:
    text = clean_text(header).lower().replace(" ", "_")
    return text
