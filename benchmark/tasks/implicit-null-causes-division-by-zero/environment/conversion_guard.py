from __future__ import annotations


def prepare_impressions(impressions: float | int | None) -> float | int:
    if impressions is None:
        return 0
    return impressions


def classify_status(impressions: float | int | None, audit: dict[str, int]) -> str:
    if impressions in (None, 0):
        return "no_traffic"
    return "active"


def build_channel_metrics(
    *,
    channel: str,
    impressions: float | int | None,
    clicks: float | int,
    conversions: float | int,
    audit: dict[str, int],
) -> dict:
    denominator = prepare_impressions(impressions)
    return {
        "channel": channel,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "conversion_rate": round(float(conversions) / float(denominator), 6),
        "ctr": round(float(clicks) / float(denominator), 6),
        "status": classify_status(impressions, audit),
        "audit": audit,
    }
