# Transaction Pipeline Notes

- Source file: `transaction_log.csv`
- Export quirks:
  - mixed-width date strings
  - string product ids
  - currency-formatted amounts
  - semantic duplicate rows with new transaction ids
- Final output should aggregate by product and date after cleaning and deduplication
