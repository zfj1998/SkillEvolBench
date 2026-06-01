# Revenue Export Cleanup Notes

- Source file: `transactions.csv`
- Business metric: `revenue`
- The export mixes clean decimals with spreadsheet-friendly display formats
- The final job should keep valid revenue rows, ignore true nulls, and compute correct totals
