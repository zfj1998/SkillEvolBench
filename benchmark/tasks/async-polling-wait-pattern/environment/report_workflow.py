from __future__ import annotations

import json
from pathlib import Path

import mock_api
from polling_policy import wait_for_next_poll
from report_client import create_report_task, fetch_report_result, fetch_report_status
from status_gate import is_result_ready

REQUEST_FILE = Path(__file__).with_name('request.json')


def run(output_path: str | Path = 'report_output.json'):
    month = json.loads(REQUEST_FILE.read_text(encoding='utf-8'))['month']
    task = create_report_task(mock_api, month)
    while True:
        status = fetch_report_status(mock_api, task['task_id'])
        if is_result_ready(status):
            break
        wait_for_next_poll()
    report = fetch_report_result(mock_api, task['task_id'])
    Path(output_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    run()
