from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "merge_cities.py"
POPULATION = PROJECT / "population.csv"
GDP = PROJECT / "gdp_data.csv"
OUTPUT = PROJECT / "output.json"


def _canon(value: str) -> str:
    cleaned = str(value).replace("\u00a0", " ").replace("\u200b", "").replace("’", " ").replace(".", " ").replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    alias_map = {
        "ny": "new york",
        "nyc": "new york",
        "new york city": "new york",
        "la": "los angeles",
        "sf": "san francisco",
        "s f": "san francisco",
        "ft worth": "fort worth",
        "saint louis": "st louis",
    }
    return alias_map.get(cleaned, cleaned)


def _valid_city(value: object) -> bool:
    cleaned = str(value).strip().lower()
    return not (
        cleaned.startswith("#")
        or cleaned.startswith("...")
        or "test" in cleaned
        or "sandbox" in cleaned
        or "scratch" in cleaned
    )


def _expected() -> pd.DataFrame:
    population = pd.read_csv(POPULATION)
    population = population[population["city"].map(_valid_city)].copy()
    population["population"] = pd.to_numeric(
        population["population"].astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )
    population["canonical_city"] = population["city"].map(_canon)
    population["_quality_rank"] = population["population"].notna().astype(int)
    population = population.sort_values(["canonical_city", "_quality_rank"], ascending=[True, False], kind="mergesort")
    population = population.drop_duplicates(subset=["canonical_city"], keep="first").rename(columns={"city": "city_population"}).drop(columns=["_quality_rank"])

    gdp = pd.read_csv(GDP)
    gdp = gdp[gdp["city"].map(_valid_city)].copy()
    gdp["gdp_billion"] = pd.to_numeric(
        gdp["gdp_billion"].astype(str).str.replace("$", "", regex=False).str.strip(),
        errors="coerce",
    )
    gdp["canonical_city"] = gdp["city"].map(_canon)
    gdp["_source_rank"] = gdp["source"].fillna("").map(lambda value: 1 if "better" in value else 0)
    gdp["_quality_rank"] = gdp["gdp_billion"].notna().astype(int)
    gdp = gdp.sort_values(["canonical_city", "_quality_rank", "_source_rank"], ascending=[True, False, False], kind="mergesort")
    gdp = gdp.drop_duplicates(subset=["canonical_city"], keep="first").rename(columns={"city": "city_gdp"}).drop(columns=["_source_rank", "_quality_rank"])

    return (
        population.merge(gdp, on="canonical_city", how="outer", suffixes=("_population", "_gdp"))
        .sort_values("canonical_city", kind="mergesort")
        .reset_index(drop=True)
    )


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    expected = _expected()
    expected_columns = list(expected.columns)

    def _matches_expected() -> bool:
        payload = _run()[1]
        actual = pd.DataFrame(payload.get("records", []))
        if actual.empty and not expected.empty:
            return False
        actual = actual.reindex(columns=expected_columns)
        return actual.fillna("__NA__").astype(str).equals(expected.fillna("__NA__").astype(str))

    def _record_for(city: str) -> dict | None:
        for record in _run()[1].get("records", []):
            if record.get("canonical_city") == city:
                return record
        return None

    public = run_checks("public", [
        ("row_count_at_least_40", lambda: _run()[1].get("row_count", 0) >= 40 or (_ for _ in ()).throw(AssertionError("merge coverage too low"))),
        ("records_present", lambda: len(_run()[1].get("records", [])) >= 40 or (_ for _ in ()).throw(AssertionError("records missing"))),
    ])
    hidden = run_checks("hidden", [
        ("nyc_new_york_matched", lambda: any(r["canonical_city"] == "new york" and pd.notna(r.get("gdp_billion")) for r in _run()[1].get("records", [])) or (_ for _ in ()).throw(AssertionError("new york alias not matched"))),
        ("los_angeles_matched", lambda: any(r["canonical_city"] == "los angeles" and pd.notna(r.get("gdp_billion")) for r in _run()[1].get("records", [])) or (_ for _ in ()).throw(AssertionError("los angeles variant not matched"))),
        ("better_duplicate_selected", lambda: (_record_for("charlotte") or {}).get("source") == "better duplicate" or (_ for _ in ()).throw(AssertionError("did not keep the highest-quality duplicate source"))),
        ("st_louis_variant_matched", lambda: any(r["canonical_city"] == "st louis" and pd.notna(r.get("gdp_billion")) for r in _run()[1].get("records", [])) or (_ for _ in ()).throw(AssertionError("saint louis/st louis variant not aligned"))),
        ("coverage_at_least_48", lambda: _run()[1].get("matched_count", 0) >= 48 or (_ for _ in ()).throw(AssertionError("matched coverage below 48 cities"))),
        ("normalized_output_matches_expected", lambda: _matches_expected() or (_ for _ in ()).throw(AssertionError("merged city output incorrect"))),
    ])
    return emit_report("E3-LS3-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
