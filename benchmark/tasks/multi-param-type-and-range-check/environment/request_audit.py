from __future__ import annotations


def build_failure_entry(index, request, errors):
    return {
        "index": index,
        "request": request,
        "errors": errors,
    }


def summarize_batch(successes, failures, trace):
    return {
        "successes": successes,
        "failures": failures,
        "trace": list(trace),
        "summary": {
            "total": len(successes) + len(failures),
            "sent": len(successes),
            "rejected": len(failures),
        },
    }
