from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "build_conversion_report.py"
OUTPUT = PROJECT / "output.json"


def _normalize_header(name: object) -> str:
    if name is None:
        return ""
    return str(name).replace("\ufeff", "").strip().lower()


def _normalize_channel(value: object) -> str:
    import re

    if value is None:
        return ""
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", str(value)).strip().lower()
    text = text.replace("-", "_")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def _parse_metric(raw: object) -> tuple[float | int | None, str]:
    placeholders = {"", "na", "n/a", "null", "none", "-"}
    if raw is None:
        return None, "missing"
    text = str(raw).strip()
    if text == "" or text.lower() in placeholders:
        return None, "missing"
    text = text.replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return None, "invalid"
    if not math.isfinite(value) or value < 0:
        return None, "invalid"
    if abs(value - round(value)) < 1e-9:
        return int(round(value)), "ok"
    return value, "ok"


def _expected() -> dict:
    rows: list[dict] = []
    for path in sorted(PROJECT.glob("channel_metrics*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames is not None
            field_map = {_normalize_header(name): name for name in reader.fieldnames}
            for raw_row in reader:
                channel = _normalize_channel(raw_row.get(field_map["channel"]))
                if not channel:
                    continue
                impressions, impression_state = _parse_metric(raw_row.get(field_map["impressions"]))
                clicks, click_state = _parse_metric(raw_row.get(field_map["clicks"]))
                conversions, conversion_state = _parse_metric(raw_row.get(field_map["conversions"]))
                rows.append(
                    {
                        "channel": channel,
                        "impressions": impressions,
                        "impression_state": impression_state,
                        "clicks": clicks if clicks is not None else 0,
                        "click_state": click_state,
                        "conversions": conversions if conversions is not None else 0,
                        "conversion_state": conversion_state,
                    }
                )

    seen: set[tuple] = set()
    deduped: list[dict] = []
    for row in rows:
        key = (row["channel"], row["impressions"], row["clicks"], row["conversions"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

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
    for row in deduped:
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

    channels: list[dict] = []
    for channel in sorted(grouped):
        group = grouped[channel]
        impressions = group["impressions"] if group["has_impressions"] else None
        if impressions is None:
            status = "data_missing"
            conversion_rate = None
            ctr = None
        elif impressions == 0:
            status = "no_traffic"
            conversion_rate = None
            ctr = None
        else:
            if group["missing_impression_rows"] or group["invalid_impression_rows"]:
                status = "incomplete_data"
            else:
                status = "active"
            conversion_rate = round(group["conversions"] / impressions, 6)
            ctr = round(group["clicks"] / impressions, 6)
        channels.append(
            {
                "channel": channel,
                "impressions": impressions,
                "clicks": group["clicks"],
                "conversions": group["conversions"],
                "conversion_rate": conversion_rate,
                "ctr": ctr,
                "status": status,
                "audit": {
                    "missing_impression_rows": int(group["missing_impression_rows"]),
                    "invalid_impression_rows": int(group["invalid_impression_rows"]),
                    "invalid_click_rows": int(group["invalid_click_rows"]),
                    "invalid_conversion_rows": int(group["invalid_conversion_rows"]),
                },
            }
        )

    return {
        "channels": channels,
        "summary": {
            "channel_count": len(channels),
            "active_channels": sum(1 for row in channels if row["status"] == "active"),
            "channels_with_missing_denominator": sum(
                1
                for row in channels
                if row["audit"]["missing_impression_rows"] or row["audit"]["invalid_impression_rows"]
            ),
            "channels_with_zero_impressions": sum(1 for row in channels if row["impressions"] == 0),
        },
    }


def _run() -> tuple[subprocess.CompletedProcess[str], dict]:
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def _by_channel(payload: dict) -> dict[str, dict]:
    return {row["channel"]: row for row in payload.get("channels", [])}


def run():
    expected = _expected()
    public = run_checks("public", [
        ("output_exists", lambda: (_run(), OUTPUT.exists())[1] or (_ for _ in ()).throw(AssertionError("output.json missing"))),
        ("channels_list_present", lambda: isinstance(_run()[1].get("channels"), list) or (_ for _ in ()).throw(AssertionError("channels list missing"))),
    ])

    def check_no_inf() -> None:
        payload = _run()[1]
        for row in payload.get("channels", []):
            for key in ("conversion_rate", "ctr"):
                value = row.get(key)
                if value is None:
                    continue
                assert math.isfinite(float(value)), f"{row['channel']} has non-finite {key}"

    def check_expected_channels() -> None:
        payload = _run()[1]
        got = _by_channel(payload)
        want = _by_channel(expected)
        assert sorted(got) == sorted(want), "channel set mismatch"
        for channel, expected_row in want.items():
            actual = got[channel]
            assert actual["status"] == expected_row["status"], f"wrong status for {channel}"
            assert actual["impressions"] == expected_row["impressions"], f"wrong impressions for {channel}"
            assert actual["audit"] == expected_row["audit"], f"wrong audit block for {channel}"
            for key in ("conversion_rate", "ctr"):
                av = actual[key]
                ev = expected_row[key]
                if ev is None:
                    assert av is None, f"{channel} should not have {key}"
                else:
                    assert math.isclose(float(av), float(ev), rel_tol=1e-9), f"wrong {key} for {channel}"

    hidden = run_checks("hidden", [
        ("script_does_not_crash", lambda: _run()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError(_run()[0].stderr[:400]))),
        ("no_inf_or_nan_rates", check_no_inf),
        ("channel_reports_match_ground_truth", check_expected_channels),
        ("summary_matches_ground_truth", lambda: _run()[1].get("summary") == expected["summary"] or (_ for _ in ()).throw(AssertionError("summary mismatch"))),
    ])
    return emit_report("E3-LS4-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
