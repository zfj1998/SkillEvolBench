TRACE = []


def send_transaction(payload):
    TRACE.append(payload)
    return {"status": "ok", "payload": payload}
