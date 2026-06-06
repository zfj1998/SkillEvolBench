from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_contacts.py"
CSV_PATH = PROJECT / "german_contacts.csv"
OUTPUT = PROJECT / "output.json"


def _german_key(text: str) -> str:
    return (
        str(text).replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
        .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss").casefold()
    )


def _expected():
    df = pd.read_csv(CSV_PATH)
    df = df.assign(
        _last=df["last_name"].map(_german_key),
        _first=df["first_name"].map(_german_key),
    )
    return df.sort_values(["_last", "_first", "contact_id"], kind="mergesort").drop(columns=["_last", "_first"])


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    public = run_checks("public", [
        ("row_count_correct", lambda: _run()[1].get("row_count") == len(expected) or (_ for _ in ()).throw(AssertionError("row count mismatch"))),
        ("records_present", lambda: len(_run()[1].get("records", [])) == len(expected) or (_ for _ in ()).throw(AssertionError("records missing"))),
    ])
    hidden = run_checks("hidden", [
        ("bär_in_b_section", lambda: [r["last_name"] for r in _run()[1].get("records", [])] == expected["last_name"].tolist() or (_ for _ in ()).throw(AssertionError("German ordering mismatch"))),
        ("müller_in_m_section", lambda: any(r["last_name"] == "Müller" for r in _run()[1].get("records", [])) or (_ for _ in ()).throw(AssertionError("Müller missing"))),
        ("köhler_in_k_section", lambda: any(r["last_name"] == "Köhler" for r in _run()[1].get("records", [])) or (_ for _ in ()).throw(AssertionError("Köhler missing"))),
        ("no_crash", lambda: _run()[0].returncode == 0 or (_ for _ in ()).throw(AssertionError("script crashed"))),
    ])
    return emit_report("E3-LS2-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
