TRACE = []


def call_api(payload):
    TRACE.append(payload)
    if not payload.get("city"):
        return {"status": 400, "body": {"errors": [{"message": "city required", "type": "required"}]}}
    if payload.get("days", 0) > 14:
        return {"status": 400, "body": {"errors": [{"message": "days out of range", "type": "range"}]}}
    return {"status": 200, "body": {"ok": True, "payload": payload}}
