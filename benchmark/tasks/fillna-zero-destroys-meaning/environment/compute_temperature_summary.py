from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from offline_policy import compute_average_temperature, parse_temperature_series
from reading_classifier import classify_temperature_readings

INPUT_PATH = Path("temperature_readings.csv")
OUTPUT_PATH = Path("output.json")


def run(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> dict:
    frame = pd.read_csv(input_path)
    temperatures = parse_temperature_series(frame)
    profile = classify_temperature_readings(temperatures)
    payload = {
        "average_temperature": compute_average_temperature(temperatures),
        "valid_reading_count": int(temperatures.notna().sum()),
        "offline_reading_count": int(profile["offline_reading_count"]),
        "zero_degree_count": int(profile["zero_degree_count"]),
        "sanity_checks": {
            "valid_average_band": -20.0 < compute_average_temperature(temperatures) < 45.0,
            "offline_readings_reported": int(profile["offline_reading_count"]) > 0,
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
