#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 <<'PYEOF'
from pathlib import Path

p = Path('tax_rates.py')
src = p.read_text(encoding='utf-8')
src = src.replace(
    """# Register null-region fallback for the billing bridge. Invoices with
# missing region metadata are normalized to the legacy empty-string code
# before they are handed to the lookup layer.
TAX_RATES.setdefault(LEGACY_EMPTY_REGION, 0.0)""",
    "# Null-region fallback removed — billing bridge now validates input."
)
src = src.replace(
    """def get_tax_rate(region: str) -> float:
    \"\"\"
    Look up the tax rate for a region.

    Uses the billing-bridge numeric index for compatibility with
    legacy callers that may pass either a region string or a code.
    \"\"\"
    code = get_region_code(region)
    return _RATE_VECTOR[code]""",
    """def get_tax_rate(region: str) -> float:
    \"\"\"Look up the tax rate for a region.\"\"\"
    if region not in TAX_RATES or region == "":
        raise ValueError(f"Unknown region: {region}")
    return TAX_RATES[region]"""
)
p.write_text(src, encoding='utf-8')
PYEOF
