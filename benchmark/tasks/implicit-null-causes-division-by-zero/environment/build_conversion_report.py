from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from channel_dedup import deduplicate_rows
from channel_schema import normalize_channel, normalize_header, parse_metric
from conversion_guard import build_channel_metrics

INPUT_GLOB = "channel_metrics*.csv"
OUTPUT_PATH = Path("output.json")


def iter_rows(base_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(base_dir.glob(INPUT_GLOB)):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                continue
            field_map = {normalize_header(name): name for name in reader.fieldnames}
            for logical in ("channel", "impressions", "clicks", "conversions"):
                if logical not in field_map:
                    raise ValueError(f"Missing required column {logical!r} in {path.name}")

            for line_no, raw_row in enumerate(reader, start=2):
                channel = normalize_channel(raw_row.get(field_map["channel"]))
                if not channel:
                    continue
                impressions, impression_state = parse_metric(raw_row.get(field_map["impressions"]))
                clicks, click_state = parse_metric(raw_row.get(field_map["clicks"]))
                conversions, conversion_state = parse_metric(raw_row.get(field_map["conversions"]))
                rows.append(
                    {
                        "channel": channel,
                        "impressions": impressions,
                        "impression_state": impression_state,
                        "clicks": clicks if clicks is not None else 0,
                        "click_state": click_state,
                        "conversions": conversions if conversions is not None else 0,
                        "conversion_state": conversion_state,
                        "source_file": path.name,
                        "line_no": line_no,
                    }
                )
    return rows


def aggregate(rows: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = defaultdict(
        lambda: {
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "has_impressions": False,
            "missing_impression_rows": 0,
            "invalid_impression_rows": 0,
            "invalid_click_rows": 0,
            "invalid_conversion_rows": 0,
        }
    )
    for row in rows:
        group = grouped[row["channel"]]
        if row["impression_state"] == "ok":
            group["impressions"] += row["impressions"]
            group["has_impressions"] = True
        elif row["impression_state"] == "missing":
            group["missing_impression_rows"] += 1
        else:
            group["invalid_impression_rows"] += 1

        if row["click_state"] == "ok":
            group["clicks"] += row["clicks"]
        elif row["click_state"] == "invalid":
            group["invalid_click_rows"] += 1

        if row["conversion_state"] == "ok":
            group["conversions"] += row["conversions"]
        elif row["conversion_state"] == "invalid":
            group["invalid_conversion_rows"] += 1

    results: list[dict] = []
    for channel in sorted(grouped):
        group = grouped[channel]
        impressions = group["impressions"] if group["has_impressions"] else None
        audit = {
            "missing_impression_rows": int(group["missing_impression_rows"]),
            "invalid_impression_rows": int(group["invalid_impression_rows"]),
            "invalid_click_rows": int(group["invalid_click_rows"]),
            "invalid_conversion_rows": int(group["invalid_conversion_rows"]),
        }
        results.append(
            build_channel_metrics(
                channel=channel,
                impressions=impressions,
                clicks=group["clicks"],
                conversions=group["conversions"],
                audit=audit,
            )
        )
    return results


def build_summary(channels: list[dict]) -> dict:
    return {
        "channel_count": len(channels),
        "active_channels": sum(1 for row in channels if row["status"] == "active"),
        "channels_with_missing_denominator": sum(
            1 for row in channels if row["audit"]["missing_impression_rows"] or row["audit"]["invalid_impression_rows"]
        ),
        "channels_with_zero_impressions": sum(1 for row in channels if row["impressions"] == 0),
    }


def run(base_dir: Path = Path("."), output_path: Path = OUTPUT_PATH) -> dict:
    deduped = deduplicate_rows(iter_rows(base_dir))
    channels = aggregate(deduped)
    payload = {"channels": channels, "summary": build_summary(channels)}
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
