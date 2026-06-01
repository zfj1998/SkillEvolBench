def default_structure():
    return {}


def default_marker():
    return {"_default": True}


def empty_render():
    return ""


def should_skip_transform(value):
    return value is None
