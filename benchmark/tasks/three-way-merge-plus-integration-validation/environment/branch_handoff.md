# Branch Handoff Notes

Merged feature branches:
- `feat/search`
- `feat/notifications`
- `feat/export`

Cross-feature assumptions people made independently:
- Search assumes event records have a stable event-type field for filtering and reporting.
- Notifications owns the schema for `user_events`.
- Export expects to dump the same event rows search and notifications operate on.

Things to watch after conflict resolution:
- A clean text merge does not guarantee the three features agree on shared table shape.
- Export headers and search filters should match the actual notification schema.
