from __future__ import annotations


def extract_remote_error(response):
    body = response["body"]
    return {"field": body["field"], "message": body["error"], "source": "remote-400"}
