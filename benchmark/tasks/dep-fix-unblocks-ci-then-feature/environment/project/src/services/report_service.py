from analytics.stats import compute_statistics
from analytics.transform import find_outliers


def build_summary(records):
    values = [r["value"] for r in records]
    stats = compute_statistics(values)
    return {
        "record_count": len(records),
        "statistics": stats,
        "outlier_indices": find_outliers(values),
    }
