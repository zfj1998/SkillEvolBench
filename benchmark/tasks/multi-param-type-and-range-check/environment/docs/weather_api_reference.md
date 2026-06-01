# Weather API Reference

Endpoint:
- `GET /weather`

Parameters:
- `city`: required, non-empty string
- `days`: required, integer in the inclusive range `1..14`
- `units`: required, one of `metric` or `imperial`

Batch ingestion note:
- Upstream request dumps sometimes contain blank strings, `null`, or stale enum values.
- Validation is expected to happen client-side before dispatch.

Validation error report schema:
- Each invalid request must keep a list of error objects.
- Each error object must use exactly this consistent shape:
  - `param` (string): parameter name, such as `city`, `days`, or `units`.
  - `error` (string): short error category, such as `required`, `type`, `range`, or `enum`.
  - `value` (any JSON value): the rejected value after local normalization.
  - `expected` (string or array): the expected contract for that parameter.
- If one request has multiple invalid parameters, report one error object per invalid parameter before dispatching any API call.
