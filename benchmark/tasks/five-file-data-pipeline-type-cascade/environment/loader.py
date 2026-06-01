"""Record loader module - outputs pipeline results."""
from formatting_policy import summarize_change


def load_records(records):
    """Load enriched records and produce summary."""
    changed = [r for r in records if r.get("changed")]
    unchanged = [r for r in records if not r.get("changed")]

    return {
        "total": len(records),
        "changed_count": len(changed),
        "unchanged_count": len(unchanged),
        "changed_records": changed,
        "unchanged_records": unchanged,
        "change_summary": [summarize_change(r) for r in records],
    }


def run_pipeline_report(result):
    """Generate and print pipeline summary report."""
    print("Pipeline Report:")
    print(f"  Total records: {result['total']}")
    print(f"  Changed: {result['changed_count']}")
    print(f"  Unchanged: {result['unchanged_count']}")
    return result
