# Active Customer Definition

This report is not asking for everyone in the customer table.

A logical customer counts as active only if:
- the customer identity resolves after email normalization
- at least one valid order exists for that identity
- valid means a real paid or shipped order with a positive amount and a parseable order date

The raw tables contain duplicate customer rows and orders with bad foreign keys, bad amounts, and non-active statuses.
