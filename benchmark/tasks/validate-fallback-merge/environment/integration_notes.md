# Primary + backup merge notes

The export should prefer the primary API whenever a record is valid.

Backup behavior:
- Use the backup API only for records that fail validation.
- Backup rows are one day older, so replacing healthy primary rows with backup rows is not acceptable.

Current known anomaly classes from the primary feed:
- negative price
- missing required field
- null required field
