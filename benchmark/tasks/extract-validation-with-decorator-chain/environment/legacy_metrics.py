def validate_metrics(payload):
    if "tenant_id" not in payload:
        return False
    return True
