# Task: Finish the Config Merge Without Breaking the YAML Structure

I need the merged config in `/root/task/config.yaml` cleaned up before we roll this deploy.

One branch increased the database pool size. The other branch added SSL settings. Both changes need to survive, and the YAML still needs to parse with the same structure the app expects.

Start here:
- `/root/task/config.yaml`
- `/root/task/config_schema.json`
- `/root/task/app.py`
- `/root/task/ops_merge_notes.md`

What I need:
1. Resolve the YAML merge conflict in `/root/task/config.yaml`.
2. Keep the larger pool size.
3. Keep the SSL block nested in the right place.
4. Save the fixed config back to `/root/task/config.yaml`.

Do not move the project outside `/root/task`, and do not replace it with a stub.
