TRACE = []


def search(payload):
    TRACE.append(payload)
    return {"status": "ok", "payload": payload}
