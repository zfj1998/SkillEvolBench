from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
ALIASES = PROJECT / "city_aliases.py"
NORMALIZER = PROJECT / "city_normalizer.py"
MERGE_SCRIPT = PROJECT / "merge_cities.py"


def run():
    aliases = read_text(ALIASES)
    normalizer = read_text(NORMALIZER)
    merge_script = read_text(MERGE_SCRIPT)
    public = run_checks("public", [
        ("uses_alias_mapping", lambda: "CITY_ALIASES" in aliases or (_ for _ in ()).throw(AssertionError("alias mapping missing"))),
    ])
    hidden = run_checks("hidden", [
        ("normalizes_case_and_spacing", lambda: ".lower()" in normalizer and "re.sub" in normalizer or (_ for _ in ()).throw(AssertionError("normalization pre-processing missing"))),
        ("handles_punctuation_variants", lambda: "\\u00a0" in normalizer and "replace(\"-\", \" \")" in normalizer and "replace(\"’\", \" \")" in normalizer or (_ for _ in ()).throw(AssertionError("punctuation/nbsp normalization missing"))),
        ("ranks_duplicate_sources", lambda: "_source_rank" in merge_script and "better" in merge_script or (_ for _ in ()).throw(AssertionError("duplicate source ranking missing"))),
        ("supports_two_extraction_paths", lambda: "canonical_city" in merge_script or (_ for _ in ()).throw(AssertionError("canonical city merge path missing"))),
        ("reports_unmatched", lambda: "build_unmatched_report" in merge_script or (_ for _ in ()).throw(AssertionError("unmatched audit missing"))),
    ])
    return emit_report("E3-LS3-T2", public, hidden)


if __name__ == "__main__":
    print_report(run())
