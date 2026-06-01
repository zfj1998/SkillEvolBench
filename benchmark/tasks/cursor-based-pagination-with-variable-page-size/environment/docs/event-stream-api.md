The `/events` endpoint is cursor-based.

Important behavior:
- requests should pass back the opaque `next_cursor` value from the previous page byte-for-byte
- the service decides how many events fit in each page
- page size is not stable enough to use as a stop condition
- boundary ids may repeat when event chunks are repacked
- consumers should stop only when `next_cursor` is `null`
- cursors may carry snapshot metadata after a `|` separator and should not be normalized client-side
