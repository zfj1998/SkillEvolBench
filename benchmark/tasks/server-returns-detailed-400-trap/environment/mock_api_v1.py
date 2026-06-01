TRACE = []


def call_api(payload):
    TRACE.append(payload)
    if not payload.get("city"):
        return {"status": 400, "body": {"error": "city required", "field": "city"}}
    if payload.get("days", 0) > 14:
        return {"status": 400, "body": {"error": "days out of range", "field": "days"}}
    return {"status": 200, "body": {"ok": True, "payload": payload}}
