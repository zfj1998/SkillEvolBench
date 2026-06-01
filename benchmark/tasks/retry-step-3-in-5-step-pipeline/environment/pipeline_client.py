from __future__ import annotations

from detail_stage import fetch_details_from_stage
from sync_state import build_sync_context


def fetch_details_with_retry(api, max_retries=2):
    context = build_sync_context(max_retries)
    return fetch_details_from_stage(api, max_retries=context["max_retries"])


def run_pipeline(api, max_retries=2):
    details = fetch_details_with_retry(api, max_retries=max_retries)
    enriched = api.enrich(details)
    return api.save(enriched)
