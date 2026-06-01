The catalog API is paginated even for plain export workflows.

Behavior summary:
- default page size is 25 products
- responses include `has_more` and `total`
- clients should continue paging until `has_more` becomes `false`
- "close enough to total" is not a safe completeness check for exports
