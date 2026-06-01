from __future__ import annotations


def create_report_task(api, month: str) -> dict:
    return api.create_report(month)


def fetch_report_status(api, task_id: str) -> dict:
    return api.get_status(task_id)


def fetch_report_result(api, task_id: str) -> dict:
    return api.get_result(task_id)['report']
