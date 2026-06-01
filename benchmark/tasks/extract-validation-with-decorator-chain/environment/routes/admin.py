def rebuild_index(payload):
    if "dry_run" in payload and not isinstance(payload["dry_run"], bool):
        return {"status": 400, "error": {"field": "dry_run", "message": "dry_run must be boolean"}}
    return {"status": 200, "data": {"status": "queued"}}
