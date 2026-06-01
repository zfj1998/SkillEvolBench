from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from city_normalizer import canonical_city_name
from merge_audit import build_unmatched_report

POPULATION_PATH = Path("population.csv")
GDP_PATH = Path("gdp_data.csv")
OUTPUT_PATH = Path("output.json")


def _valid_city(value: object) -> bool:
    cleaned = str(value).strip().lower()
    return not (
        cleaned.startswith("#")
        or cleaned.startswith("...")
        or "test" in cleaned
        or "sandbox" in cleaned
        or "scratch" in cleaned
    )


def _prepare_population(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    prepared = prepared[prepared["city"].map(_valid_city)].copy()
    prepared["population"] = pd.to_numeric(
        prepared["population"].astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )
    prepared["canonical_city"] = prepared["city"].map(canonical_city_name)
    prepared["_quality_rank"] = prepared["population"].notna().astype(int)
    prepared = prepared.sort_values(["canonical_city", "_quality_rank"], ascending=[True, False], kind="mergesort")
    prepared = prepared.drop_duplicates(subset=["canonical_city"], keep="first").copy()
    prepared = prepared.rename(columns={"city": "city_population"})
    return prepared.drop(columns=["_quality_rank"])


def _prepare_gdp(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    prepared = prepared[prepared["city"].map(_valid_city)].copy()
    prepared["gdp_billion"] = pd.to_numeric(
        prepared["gdp_billion"].astype(str).str.replace("$", "", regex=False).str.strip(),
        errors="coerce",
    )
    prepared["canonical_city"] = prepared["city"].map(canonical_city_name)
    prepared["_quality_rank"] = prepared["gdp_billion"].notna().astype(int)
    prepared = prepared.sort_values(["canonical_city", "_quality_rank"], ascending=[True, False], kind="mergesort")
    prepared = prepared.drop_duplicates(subset=["canonical_city"], keep="first").copy()
    prepared = prepared.rename(columns={"city": "city_gdp"})
    return prepared.drop(columns=["_quality_rank"])


def run(
    population_path: Path = POPULATION_PATH,
    gdp_path: Path = GDP_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict:
    population = _prepare_population(pd.read_csv(population_path))
    gdp = _prepare_gdp(pd.read_csv(gdp_path))
    merged = population.merge(gdp, on="canonical_city", how="outer", suffixes=("_population", "_gdp"))
    merged = merged.sort_values("canonical_city", kind="mergesort").reset_index(drop=True)
    payload = {
        "row_count": int(len(merged)),
        "matched_count": int(merged["population"].notna().sum()),
        "unmatched": build_unmatched_report(merged),
        "records": merged.to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
