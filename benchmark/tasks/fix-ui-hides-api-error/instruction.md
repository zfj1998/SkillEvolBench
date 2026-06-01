# Fix the profile page error handling end to end

The user profile app is in `/root/task`. When the backend hits an error, the page currently shows "No data available", which is misleading. Product wants proper error handling on the profile page.

Please fix the issue in place across the existing stack:
- the UI should show an actual error state when the request fails
- server-side failures should not still look like successful API responses
- keep the normal success path working

Expected API response schema:
- Successful profile lookup returns HTTP `200` with `{ "status": "ok", "data": <profile object> }`.
- Missing users return HTTP `404` with `{ "status": "not_found", "message": <string>, "data": null }`.
- Server-side failures return a non-200 error status such as `500` with `{ "status": "error", "message": <string>, "data": null }`.
- The frontend should render an error state for `"status": "error"` responses and should not collapse them into the normal "No data available" state.
- Error handling must be per request: an intermittent backend failure should not
  poison later successful lookups. If the data layer fails once and then returns
  a valid profile on the next call, the second API response should still be a
  normal `200` success response with profile data.

Start here:
- `/root/task/frontend/UserProfile.jsx`
- `/root/task/frontend/api.js`
- `/root/task/backend/routes.py`
- `/root/task/backend/services.py`
- `/root/task/backend/database.py`

Make your edits under `/root/task`. Do not solve this with a frontend-only workaround.
