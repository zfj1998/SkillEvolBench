__version__ = "2.5.0"


class ConfigDict(dict):
    pass


def field_validator(*fields, mode="after"):
    def decorator(func):
        func._v2_field_validator_fields = fields
        return func
    return decorator


def model_validator(mode="after"):
    def decorator(func):
        func._v2_model_validator = mode
        return func
    return decorator


class BaseModel:
    def __init__(self, **data):
        annotations = getattr(self.__class__, "__annotations__", {})
        values = {}
        for field in annotations:
            values[field] = data.get(field)
        for name, attr in self.__class__.__dict__.items():
            if hasattr(attr, "_v2_field_validator_fields"):
                for field in attr._v2_field_validator_fields:
                    if field in values:
                        bound = getattr(self.__class__, name)
                        values[field] = bound(values[field])
        for key, value in values.items():
            setattr(self, key, value)
        for name, attr in self.__class__.__dict__.items():
            if hasattr(attr, "_v2_model_validator"):
                bound = getattr(self, name)
                result = bound()
                if result is not None and result is not self:
                    raise TypeError("model_validator must return self or None in this benchmark fixture")

    def model_dump(self):
        return {field: getattr(self, field) for field in getattr(self.__class__, "__annotations__", {})}
