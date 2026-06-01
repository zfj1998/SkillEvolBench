"""Generate fixture for T1: standard-null-filter-before-sum.
5000 orders, first 200 have empty amount (NaN when loaded).
Trap: sum()/len() gives ~96 instead of ~100 for average."""
print("T1: fixture pre-generated")
