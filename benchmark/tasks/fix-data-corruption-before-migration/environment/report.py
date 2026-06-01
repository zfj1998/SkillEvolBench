"""Report generator - produces event timeline using updated_at."""
from migrate import run_migration
from timeline_serializer import serialize_event


def generate_timeline_report():
    """Generate a timeline report using the migrated updated_at field."""
    records = run_migration()

    report = {"title": "Event Timeline Report", "events": []}
    for record in records:
        report["events"].append(serialize_event(record))

    return report


def print_report():
    """Print the timeline report."""
    report = generate_timeline_report()
    print(f"\n{report['title']}")
    print("=" * 50)
    for event in report["events"]:
        print(f"  {event['name']}: {event['timestamp']} (hour: {event['hour']})")
    return report


if __name__ == "__main__":
    print_report()
