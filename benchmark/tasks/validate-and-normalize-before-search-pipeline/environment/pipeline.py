from pathlib import Path

from date_window import previous_month_window
from mock_api import TRACE, search_sales
from nlp_extractors import infer_region_phrase, infer_sort_clause
from request_assembly import build_api_payload, build_internal_request
from report_formatter import summarize_rows
from sales_contract import REQUIRED_INTERNAL_FIELDS


def extract_params(query):
    return {
        "region": infer_region_phrase(query),
        "sort_phrase": infer_sort_clause(query),
    }


def validate_params(params):
    errors = []
    for field_name in REQUIRED_INTERNAL_FIELDS:
        if not params.get(field_name):
            errors.append({"field": field_name, "reason": "missing"})
    return errors


def normalize_params(params):
    return build_internal_request(params)


def run_pipeline(query_path):
    TRACE.clear()
    query = Path(query_path).read_text(encoding="utf-8").strip()
    params = extract_params(query)
    internal_request = normalize_params(params)
    start, end = previous_month_window()
    internal_request["start_date"] = start
    internal_request["end_date"] = end
    validate_params(internal_request)
    api_payload = build_api_payload(internal_request)
    rows = search_sales(api_payload)
    return summarize_rows(rows)
