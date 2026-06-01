# Merge Report

## Source coverage
- crm.csv
- hr.csv
- email_contacts.csv

## Matching method
- Primary key: normalized email
- Secondary key: exact first-token + last-name match on same normalized phone
- Same-name / different-email contacts are kept separate to avoid false merges
- John Smith duplicate-name cases are expected to remain distinct

## Summary
- Raw records: 304
- Master records: 144
- Phone-assisted merges: 0
- Distinct same-name protections: 2
