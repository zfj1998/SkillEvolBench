def validate_payload(payload):
    errors = []
    if not payload.get("city"):
        errors.append({"field": "city", "message": "city required"})
    return errors
