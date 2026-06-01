# Task: Temperature Analysis

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Find the real issue or missing step.
2. Update the existing files under `/root/task`.
3. Keep the expected behavior correct after your changes.

Save all edits under `/root/task`. Do not move the project outside `/root/task` or replace it with a stub.
Calculate the average temperature from `/root/task/temperature_readings.csv` and save the result to `/root/task/output.json`.

The station network occasionally leaves the temperature field blank when a sensor is offline. The data dictionary explains how to interpret that blank value and what it means for aggregation.

Review:

- `/root/task/data_dictionary.md`
- `/root/task/temperature_readings.csv`
- `/root/task/offline_policy.py`
- `/root/task/compute_temperature_summary.py`

Include both the final average and a small audit block that explains how many readings were usable.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with the average-temperature result and audit fields for valid readings, offline/null readings, and actual zero-degree readings.

Design contract: `data_dictionary.md` defines missing temperature as sensor offline. Exclude null/offline readings from the mean, keep real `0.0` readings in the mean, and report the offline/null count. Do not use `fillna(0)` for temperature.

