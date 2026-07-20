"""Mask known credentials in text artifacts before AP uploads them."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


TEXT_SUFFIXES = {
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
}
SECRET_ENV_NAMES = {
    "MODEL_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AP_API_KEY",
    "OSS_ACCESS_KEY_ID",
    "OSS_ACCESS_KEY_SECRET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
}

_SECRET_KEY = (
    r"(?:(?:[a-z0-9]+[_-])*(?:api[_-]?key|access[_-]?key[_-]?secret|"
    r"secret[_-]?access[_-]?key|auth[_-]?token|bearer[_-]?token)|"
    r"authorization)"
)
_QUOTED_SECRET_VALUE = re.compile(
    rf"(?i)(\b{_SECRET_KEY}\b[\"']?\s*[:=]\s*)([\"'])[^\r\n]*?\2"
)
_UNQUOTED_SECRET_VALUE = re.compile(
    rf"(?im)(\b{_SECRET_KEY}\b[\"']?\s*[:=]\s*)"
    r"(Bearer\s+)?(?![\"'])([^\s,#}\r\n]+)"
)


def _mask_keyed_values(text: str) -> str:
    """Mask JSON, YAML, header, and shell-style credential assignments."""

    masked = _QUOTED_SECRET_VALUE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]{match.group(2)}",
        text,
    )
    return _UNQUOTED_SECRET_VALUE.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2) or ''}[REDACTED]"
        ),
        masked,
    )


def mask_tree(root: Path) -> int:
    replacements = {
        value: "[REDACTED]"
        for name in SECRET_ENV_NAMES
        if len(value := os.environ.get(name, "")) >= 4
    }
    changed = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        masked = text
        for secret, replacement in replacements.items():
            masked = masked.replace(secret, replacement)
        masked = _mask_keyed_values(masked)
        if masked != text:
            path.write_text(masked)
            changed += 1
    return changed


def main() -> int:
    root = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("OUTPUT_DIR", "/tmp/output")
    )
    if not root.exists():
        return 0
    print(f"Masked secrets in {mask_tree(root)} text artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
