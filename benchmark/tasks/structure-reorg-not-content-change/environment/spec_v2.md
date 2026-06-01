# API Integration Specification — v2

**Document ID:** SPEC-2024-API-001
**Status:** Draft

---

## Section 1: Error Handling

All error responses follow the standard format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "request_id": "uuid-v4"
  }
}
```

Common error codes:
- `AUTH_EXPIRED` — token has expired
- `RATE_LIMITED` — rate limit exceeded
- `NOT_FOUND` — resource does not exist
- `VALIDATION_ERROR` — request body failed schema validation

---

## Section 2: Pagination

List endpoints return paginated responses. The default page size is 20 items; the maximum
is 100.

Pagination uses cursor-based navigation. Each response includes a `next_cursor` field.
Pass this value as the `cursor` query parameter in the next request. When `next_cursor`
is `null`, there are no more pages.

---

## Section 3: Webhooks

Webhooks deliver real-time event notifications to a registered HTTPS endpoint.

**Supported events:**
- `resource.created`
- `resource.updated`
- `resource.deleted`

Each webhook payload is signed with HMAC-SHA256 using your webhook secret. Verify the
`X-Signature-256` header to confirm authenticity.

Respond with HTTP 200 within 10 seconds; otherwise the delivery is retried up to 3 times
with exponential back-off.

---

## Section 4: Authentication

All API requests must be authenticated using Bearer tokens. Tokens are issued via the
`/auth/token` endpoint and expire after 3600 seconds (1 hour).

**Required headers:**
- `Authorization: Bearer <token>`
- `Content-Type: application/json`

Token refresh must be performed at least 60 seconds before expiry to avoid service
interruption.

---

## Section 5: Rate Limiting

The API enforces rate limits per authenticated user:
- **Standard tier:** 100 requests per minute
- **Premium tier:** 500 requests per minute

When a rate limit is exceeded, the API returns HTTP 429 with a `Retry-After` header
indicating the number of seconds until the limit resets.

Clients must implement exponential back-off starting at 1 second, doubling on each
subsequent retry, capped at 32 seconds.
