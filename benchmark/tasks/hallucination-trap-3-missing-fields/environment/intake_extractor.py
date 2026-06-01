from __future__ import annotations


def extract_label_values(text: str, labels: dict[str, str]) -> dict[str, str]:
    data = {}
    for field, label in labels.items():
        prefix = f"{label}:"
        for line in text.splitlines():
            if line.startswith(prefix):
                data[field] = line.split(":", 1)[1].strip()
                break
        else:
            data[field] = ""
    return data
