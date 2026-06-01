# Add plugin support, but do it in a maintainable way

The data processor project is in `/root/task`. The request from the team is to add a plugin system so custom transform functions can be loaded from `/root/task/plugins`, but the current code is packed into a single `processor.py`.

Please update the existing project in place. The end result needs to support plugins, but it also needs to stay maintainable:
- keep the current processing behavior working
- keep JSON / CSV / XML flows intact
- split responsibilities instead of bolting plugin logic into one giant file
- broken plugins should not take down the whole processor

Expected `process(...)` return schema:
- Success returns `{ "status": "ok", "result": <transformed output> }`.
- Error handling returns `{ "status": "error", "message": <string> }`.
- For memory output, `result` is the transformed row list.
- For JSON/file/API outputs, `result` should preserve the existing project semantics for that destination.

Start here:
- `/root/task/README.md`
- `/root/task/docs/ops-runbook.md`
- `/root/task/processor.py`
- `/root/task/sample_inputs/report.xml`
- `/root/task/plugins`

Save your edits under `/root/task`. Keep the project runnable there and do not replace the implementation with a stub.
