from __future__ import annotations


def is_lossless(original, restored) -> bool:
    return restored == original
