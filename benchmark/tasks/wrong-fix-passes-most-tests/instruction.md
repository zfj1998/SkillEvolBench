# Fix the tax calculation bug without patching around individual states

The Python project is in `/root/task`. QA first noticed the wrong tax total on California orders, but we need the real fix, not a one-off special case.

Please trace the actual root cause in the existing code under `/root/task` and fix it in place. Keep the calculator working for every region, and save all edits under `/root/task`.

Expected calculator behavior:
- `calculate_tax(income, region)` returns `round(income * TAX_RATES[region], 2)` for every valid region in `/root/task/tax_rates.py`.
- Zero or negative income should return `0.0`.
- Unknown regions such as `"ZZ"` should raise `ValueError`.
- The fix should be general across the whole region table; do not patch around a single observed state or add region-specific shortcut logic in `tax_calculator.py`.

Start with:
- `/root/task/tax_calculator.py`
- `/root/task/tax_rates.py`
- `/root/task/public_tests/test_tax.py`

Deliverable note: no standalone output file is required. The required artifact is the corrected calculator code under `/root/task`; the verifier checks the existing function behavior against the documented tax-calculation contract.
