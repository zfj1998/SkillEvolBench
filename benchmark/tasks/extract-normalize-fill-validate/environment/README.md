This fixture simulates an ERP import preparation step.

Relevant files:
- `invoice.pdf`
- `erp_template.csv`
- `date_normalizer.py`: ERP date-format contract
- `erp_writer.py`: CSV header/row shaping
- `consistency_check.py`: total reconciliation between PDF and CSV
- `analyzer.py`: pipeline orchestration

Starter limitation:
- invoice dates are not normalized to `YYYY-MM-DD`
- CSV column order still follows the extraction order, not the ERP template
- validation is recorded but not actually enforced
