# Employee Metrics With Sentinel Values

`employee_data.csv` is exported from several HR tools and contains documented sentinel values that mean different things in different columns.

Important examples:

- `age = -1` means “not provided”
- `salary = 0` means “unpaid volunteer” and is valid
- `site_temperature = -999` means sensor fault

The current pipeline uses a shared numeric missing-value registry. That makes the implementation short, but it also causes column-specific meanings to collapse into one global rule.
