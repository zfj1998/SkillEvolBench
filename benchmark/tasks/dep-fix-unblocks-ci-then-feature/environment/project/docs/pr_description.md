# PR #147: Add CSV Export Endpoint

## Summary

Add a `GET /api/reports/export.csv` endpoint that returns report data in CSV format. The existing `/api/reports/summary` returns JSON — this adds the CSV counterpart.

## Requirements

### Endpoint

`GET /api/reports/export.csv`

**Query parameters:**
- `start_date` (optional): `YYYY-MM-DD` — include records from this date (inclusive)
- `end_date` (optional): `YYYY-MM-DD` — include records up to this date (inclusive)

**Response:**
- Content-Type: `text/csv`
- Status: 200
- Body: CSV with header row + data rows

### CSV format

1. **Columns**: `date,metric,region,value` (in that order)
2. Use standard `csv` module for proper escaping
3. No trailing newline after the last data row

### Export function

Implement the underlying `export_to_csv()` in `src/analytics/export.py`:

```python
def export_to_csv(records, columns=None, date_range=None) -> str
```

- `records`: list of dicts
- `columns`: ordered list of column names (default: `["date", "metric", "region", "value"]`)
- `date_range`: optional `(start_date, end_date)` tuple for filtering by `record["date"]`
- Returns: CSV string

### Edge cases

- No query params → return all records
- `start_date` only → filter from that date onward
- `end_date` only → filter up to that date
- No matching records → header row only
- Empty records + explicit columns → header row only
- Empty records + no columns → empty string

## Testing

Existing tests must continue to pass. The `/api/reports/summary` endpoint must still work.
