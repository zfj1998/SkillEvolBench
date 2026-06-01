# DACH Revenue Loader Notes

- Source file: `revenue.csv`
- Export owner: regional finance operations for Germany/Austria/Switzerland
- The export may contain spreadsheet artifacts in both headers and numeric cells
- Downstream analysts expect canonical fields: `region`, `name`, `amount`, `quarter`
- The output should preserve all valid rows and aggregate revenue by region
