def prepare_stage_input(value):
    if isinstance(value, dict):
        return dict(value)
    return value


def remember_stage(stage_name, value):
    return {"stage": stage_name, "is_none": value is None}
