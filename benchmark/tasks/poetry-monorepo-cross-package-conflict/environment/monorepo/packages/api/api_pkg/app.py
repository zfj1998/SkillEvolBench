from fastapi import FastAPI
from pydantic import BaseModel, validator


app = FastAPI()


class JobRequest(BaseModel):
    name: str
    priority: int

    @validator("name")
    def normalize_name(cls, value):
        return value.strip().title()

    def to_payload(self) -> dict:
        return self.dict()


@app.post("/jobs")
def create_job(name: str, priority: int = 1) -> dict:
    req = JobRequest(name=name, priority=priority)
    return req.to_payload()


def get_api_payload(name: str = "  batch sync  ", priority: int = 2) -> dict:
    req = JobRequest(name=name, priority=priority)
    return req.to_payload()
