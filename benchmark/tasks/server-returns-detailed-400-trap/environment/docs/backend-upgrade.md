# Backend Upgrade Note

The partner team is changing the 400 response format in the next release.

Do not rely on:
- `body.error`
- `body.field`

The only stable contract on our side is the local request schema we validate before dispatch.
