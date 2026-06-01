from __future__ import annotations

from collections import Counter
from typing import Any


class TransientServiceError(RuntimeError):
    pass


class PipelineAPI:
    def __init__(self):
        self.trace: list[dict[str, Any]] = []
        self.step_counts = Counter()
        self.saved: list[dict[str, Any]] = []
        self.detail_failures_remaining = 1

    def authenticate(self) -> str:
        self.step_counts["auth"] += 1
        self.trace.append({"step": "auth", "status": 200})
        return "token-1"

    def list_records(self, token: str) -> list[str]:
        self.step_counts["list"] += 1
        self.trace.append({"step": "list", "status": 200, "token": token})
        return ["item-1", "item-2"]

    def fetch_details(self, record_ids: list[str]) -> list[dict[str, Any]]:
        self.step_counts["detail"] += 1
        if self.detail_failures_remaining:
            self.detail_failures_remaining -= 1
            self.trace.append({"step": "detail", "status": 503})
            raise TransientServiceError("detail service temporarily unavailable")
        self.trace.append({"step": "detail", "status": 200})
        return [{"id": record_id, "amount": 10} for record_id in record_ids]

    def enrich(self, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.step_counts["enrich"] += 1
        self.trace.append({"step": "enrich", "status": 200})
        return [{**row, "enriched": True} for row in details]

    def save(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        self.step_counts["save"] += 1
        self.trace.append({"step": "save", "status": 200})
        self.saved = list(rows)
        return {"saved": len(rows), "rows": list(rows)}
