from __future__ import annotations


def build_internal_request(params):
    internal = dict(params)
    if internal.get("region") == "California":
        internal["state_code"] = "CA"
    if internal.get("sort_phrase") == "amount descending":
        internal["sort_by"] = "amount"
        internal["sort_direction"] = "desc"
    return internal


def build_api_payload(internal_request):
    # The pipeline still forwards the internal reporting keys instead of the
    # downstream API contract keys.
    return dict(internal_request)
