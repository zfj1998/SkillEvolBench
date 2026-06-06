"""Generate fixture for T5: fillna-zero-destroys-meaning.
10000 readings: 200 with empty temp (offline), 50 with temp=0.0 (real).
Trap: fillna(0) → 200 fake zeros → avg drops from ~14.9° to ~11.9°."""
print("T5: fixture pre-generated")
