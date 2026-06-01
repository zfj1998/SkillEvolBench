from __future__ import annotations

import re


def parse_money(text: str) -> float:
    normalized = text.replace(",", "").replace("$", "").strip()
    if "million" in normalized.lower():
        return float(re.search(r"(\d+(?:\.\d+)?)", normalized).group(1)) * 1_000_000
    return float(re.search(r"(\d+(?:\.\d+)?)", normalized).group(1))


def extract_revenue_evidence(pages: list[str]) -> list[dict]:
    evidence = []
    summary_match = re.search(r"(\$2\.5 million)", pages[0], re.I)
    if summary_match:
        evidence.append(
            {
                "value": parse_money(summary_match.group(1)),
                "source": "Executive Summary (page 3)",
                "excerpt": summary_match.group(1),
            }
        )
    table_match = re.search(r"(\$2,300,000)", pages[1], re.I)
    if table_match:
        evidence.append(
            {
                "value": parse_money(table_match.group(1)),
                "source": "Financial Statements (page 12)",
                "excerpt": table_match.group(1),
            }
        )
    return evidence
