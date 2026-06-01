def normalize_transport_value(value):
    if isinstance(value, dict):
        return dict(value)
    return value


def is_transport_empty_string(value):
    return value == ""


def is_transport_dict(value):
    return isinstance(value, dict)
