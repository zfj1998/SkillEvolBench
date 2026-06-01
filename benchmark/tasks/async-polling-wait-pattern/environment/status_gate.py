from __future__ import annotations


def is_result_ready(status_payload: dict[str, object]) -> bool:
    # The starter still stops polling as soon as the task leaves "pending",
    # which treats "processing" as a terminal state.
    return status_payload['status'] != 'pending'
