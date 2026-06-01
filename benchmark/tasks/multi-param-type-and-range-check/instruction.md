# Task: Process the Weather Batch Without Sending Bad Requests

I need the batch processor in `/root/task` fixed before we send another round of weather lookups.

The input file is `/root/task/requests.json`. It contains ten weather requests from an upstream job. Some are valid and should be sent. Some are invalid and should be rejected locally with useful error details. Do not rely on the mock API to tell you what's wrong after the request is already sent.

Start here:
- `/root/task/README.md`
- `/root/task/client.py`
- `/root/task/mock_api.py`
- `/root/task/docs/weather_api_reference.md`

What I need:
1. Validate each request before calling the API.
2. Send only the valid requests.
3. Keep a structured error report for the invalid ones.
4. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Each invalid request should report all validation failures found before dispatch. Use one consistent error object shape with `param`, `error`, `value`, and `expected` fields; for example, a request with a bad `days` value and bad `units` value should produce two error objects rather than stopping at the first failure.
