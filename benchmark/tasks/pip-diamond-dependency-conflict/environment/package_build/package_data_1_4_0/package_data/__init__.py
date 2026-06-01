def process(payload, mode=None):
    if mode is None:
        return payload.upper()
    return f"{mode}:{payload}"
