from __future__ import annotations

import mock_api
from endpoint_registry import resolve_data_endpoint
from payload_writer import write_payload


def run(output_path: str = 'latest_data.json'):
    config = mock_api.get_config()
    data = mock_api.fetch_data(resolve_data_endpoint(config))
    write_payload(output_path, data)
    return data


if __name__ == '__main__':
    run()
