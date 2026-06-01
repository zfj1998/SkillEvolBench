__version__ = "1.10.9"


def validator(*fields):
    def decorator(func):
        func._v1_validator_fields = fields
        return func
    return decorator


class BaseModel:
    def __init__(self, **data):
        annotations = getattr(self.__class__, "__annotations__", {})
        values = {}
        for field in annotations:
            values[field] = data.get(field)
        for name, attr in self.__class__.__dict__.items():
            if hasattr(attr, "_v1_validator_fields"):
                for field in attr._v1_validator_fields:
                    if field in values:
                        values[field] = getattr(self.__class__, name)(values[field])
        for key, value in values.items():
            setattr(self, key, value)

    def dict(self):
        return {field: getattr(self, field) for field in getattr(self.__class__, "__annotations__", {})}
