from pydantic import BaseModel, ConfigDict, model_validator


class CoreRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    count: int

    @model_validator(mode="after")
    def validate_count(self):
        if self.count < 0:
            raise ValueError("count must be non-negative")
        self.name = self.name.upper()
        return self


def build_core_record(name: str, count: int) -> CoreRecord:
    return CoreRecord(name=name, count=count)


def get_core_payload(name: str = "alpha", count: int = 2) -> dict:
    return build_core_record(name, count).model_dump()
