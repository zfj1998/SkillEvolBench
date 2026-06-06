#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "city_aliases.py": dedent(
        """
        from __future__ import annotations

        CITY_ALIASES = {
            "new york": "new york",
            "ny": "new york",
            "nyc": "new york",
            "new york city": "new york",
            "los angeles": "los angeles",
            "la": "los angeles",
            "san francisco": "san francisco",
            "sf": "san francisco",
            "s f": "san francisco",
            "s f ": "san francisco",
            "ft worth": "fort worth",
            "saint louis": "st louis",
        }
        """
    ),
    "city_normalizer.py": dedent(
        """
        from __future__ import annotations

        import re

        from city_aliases import CITY_ALIASES


        def _basic_normalize(value: str) -> str:
            cleaned = str(value).replace("\\u00a0", " ").replace("\\u200b", "").replace("’", " ").replace(".", " ").replace("-", " ")
            cleaned = re.sub(r"\\s+", " ", cleaned).strip().lower()
            return cleaned


        def canonical_city_name(value: str) -> str:
            normalized = _basic_normalize(value)
            return CITY_ALIASES.get(normalized, normalized)
        """
    ),
    "merge_cities.py": dedent(
        """
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
            prepared["_source_rank"] = prepared["source"].fillna("").map(lambda value: 1 if "better" in value else 0)
            prepared["_quality_rank"] = prepared["gdp_billion"].notna().astype(int)
            prepared = prepared.sort_values(["canonical_city", "_quality_rank", "_source_rank"], ascending=[True, False, False], kind="mergesort")
            prepared = prepared.drop_duplicates(subset=["canonical_city"], keep="first").copy()
            prepared = prepared.rename(columns={"city": "city_gdp"})
            return prepared.drop(columns=["_source_rank", "_quality_rank"])


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
                "matched_count": int((merged["population"].notna() & merged["gdp_billion"].notna()).sum()),
                "unmatched": build_unmatched_report(merged),
                "records": merged.to_dict(orient="records"),
            }
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload


        if __name__ == "__main__":
            run()
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
