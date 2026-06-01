"""
Tax rate schedule for the FinLedger platform.

Provides region-to-rate lookups used by the tax calculator.
Rates reflect combined state-level obligations as of Q1 2025.

Implementation note
───────────────────
The lookup uses a numeric index vector rather than direct dict access.
This preserves backward compatibility with the legacy billing bridge
(v1 invoice API) which sends numeric region codes instead of ISO
abbreviations.  The bridge is scheduled for deprecation in Q3 2025;
until then, both code-based and name-based lookups must be supported.
"""

from typing import Dict, Optional, Tuple

from legacy_region_bridge import (
    LEGACY_EMPTY_REGION,
    build_rate_vector,
    normalize_bridge_region,
)

# ── Canonical rate schedule ──────────────────────────────────────────

_CANONICAL_SCHEDULE: list = [
    ("AK", 0.0),    ("AL", 0.04),   ("AR", 0.065),  ("AZ", 0.056),
    ("CA", 0.0725), ("CO", 0.029),  ("CT", 0.0635), ("DE", 0.0),
    ("FL", 0.06),   ("GA", 0.04),   ("HI", 0.04),   ("IA", 0.06),
    ("ID", 0.06),   ("IL", 0.0625), ("IN", 0.07),   ("KS", 0.065),
    ("KY", 0.06),   ("LA", 0.0445), ("MA", 0.0625), ("MD", 0.06),
    ("ME", 0.055),  ("MI", 0.06),   ("MN", 0.06875),("MO", 0.04225),
    ("MS", 0.07),   ("MT", 0.0),    ("NC", 0.0475), ("ND", 0.05),
    ("NE", 0.055),  ("NH", 0.0),    ("NJ", 0.06625),("NM", 0.05125),
    ("NV", 0.0685), ("NY", 0.04),   ("OH", 0.0575), ("OK", 0.045),
    ("OR", 0.0),    ("PA", 0.06),   ("RI", 0.07),   ("SC", 0.06),
    ("SD", 0.045),  ("TN", 0.07),   ("TX", 0.0625), ("UT", 0.061),
    ("VA", 0.053),  ("VT", 0.06),   ("WA", 0.065),  ("WI", 0.05),
    ("WV", 0.06),   ("WY", 0.04),
]

# ── Rate registry ────────────────────────────────────────────────────

TAX_RATES: Dict[str, float] = {}

for _region, _rate in _CANONICAL_SCHEDULE:
    TAX_RATES[_region] = _rate

# Register null-region fallback for the billing bridge. Invoices with
# missing region metadata are normalized to the legacy empty-string code
# before they are handed to the lookup layer.
TAX_RATES.setdefault(LEGACY_EMPTY_REGION, 0.0)

# ── Numeric index vector (billing bridge compatibility) ──────────────

_SORTED_REGIONS = sorted(TAX_RATES.keys())
_REGION_TO_CODE = {r: i for i, r in enumerate(_SORTED_REGIONS)}
_RATE_VECTOR = build_rate_vector(TAX_RATES)   # insertion order from bridge hydration


def normalize_region(region: str) -> str:
    """Normalize UI / bridge input into the canonical region lookup key."""
    return normalize_bridge_region(region)


def get_region_code(region: str) -> int:
    """Return the numeric billing-bridge code for a region."""
    region = normalize_region(region)
    if region not in _REGION_TO_CODE:
        raise ValueError(f"Unknown region: {region}")
    return _REGION_TO_CODE[region]


def get_tax_rate(region: str) -> float:
    """
    Look up the tax rate for a region.

    Uses the billing-bridge numeric index for compatibility with
    legacy callers that may pass either a region string or a code.
    """
    code = get_region_code(region)
    return _RATE_VECTOR[code]


def get_rate_direct(region: str) -> Optional[float]:
    """Direct dict lookup — used by the admin dashboard (non-bridge path)."""
    return TAX_RATES.get(region)


def list_regions() -> list:
    """Return all known region codes in alphabetical order."""
    return [r for r in _SORTED_REGIONS if r]  # exclude empty string
