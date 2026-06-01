# Reduce duplicated validation in the intake handlers

The service lives in `/root/task`. Four intake handlers under `/root/task/routes` all do nearly the same payload validation, but each one drifted a little over time.

Please refactor the existing code in place so the validation is shared through a reusable decorator or decorator factory. Keep the current externally visible behavior the same:
- the same success cases should still return `status == 200`
- the same invalid inputs should still return `status == 400`
- the error payload shape must stay consistent
- optional field behavior must stay exactly as it is today

Start here:
- `/root/task/README.md`
- `/root/task/docs/api_contract_notes.md`
- `/root/task/routes/shared.py`
- `/root/task/routes/users.py`
- `/root/task/routes/products.py`
- `/root/task/routes/orders.py`
- `/root/task/routes/reviews.py`

Make your edits under `/root/task` and keep the project runnable from there. Do not replace the handlers with stubs or rewrite the task into a different structure.

The uniform validation error payload for rejected requests is:

```json
{"status": 400, "error": {"field": "field_name", "message": "human-readable reason"}}
```

Keep boundary checks intact: reject `age=-1`, `price=0`, `quantity=101`, and `rating=6`.
