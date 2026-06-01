from __future__ import annotations

ITEM_PATTERNS = {
    "Personnel": r"Personnel costs of \$(\d[\d,]*)",
    "Equipment": r"Equipment at \$(\d[\d,]*)",
    "Travel": r"Travel at \$(\d[\d,]*)",
    "Software": r"\|\s*Software\s*\|\s*\$(\d[\d,]*)\s*\|",
    "Training": r"\|\s*Training\s*\|\s*\$(\d[\d,]*)\s*\|",
    "Contingency": r"Contingency at \$(\d[\d,]*)",
    "Overhead": r"Overhead at \$(\d[\d,]*)",
}

# Starter intentionally skips appendix-derived budget lines.
APPENDIX_PATTERNS = {}
