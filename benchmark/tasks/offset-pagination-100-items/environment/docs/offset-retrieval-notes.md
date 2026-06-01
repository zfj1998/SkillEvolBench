The `/users` endpoint is an older offset/limit export API.

Operational notes:
- requests use `offset` and `limit`
- `has_more` is the primary continuation signal
- `total` reflects the expected final export size
- some pages may temporarily include a repeated boundary row during backend fan-in
- clients should preserve the requested page stride and deduplicate by `id`
