from copy import deepcopy


def prepare_payload(payload, route_name):
    if not isinstance(payload, dict):
        return {"route": route_name, "payload": payload}
    return {"route": route_name, "payload": deepcopy(payload)}


def record_validation_attempt(route_name, payload):
    return {"route": route_name, "field_count": len(payload) if isinstance(payload, dict) else 0}
