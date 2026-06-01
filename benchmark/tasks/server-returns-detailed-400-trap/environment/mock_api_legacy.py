TRACE = []


def call_api(payload):
    TRACE.append(payload)
    return {"status": 200, "body": {"ok": True, "payload": payload}}
