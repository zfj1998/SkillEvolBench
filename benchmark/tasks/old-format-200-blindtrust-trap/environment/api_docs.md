# User API response contract

Current canonical fields:
- `id`
- `username`
- `phone`
- `email`
- `created_at`

Compatibility note:
- Deprecated aliases may still appear during the migration window:
  - `user_name`
  - `phone_number`
  - `email_address`
  - `created_date`
- Treat deprecated aliases as compatibility-only. When both old and new fields are present, prefer the canonical fields above.
