"""Time verification helper."""
from models import KNOWN_EVENT_TIMES


def verify_event_time(event_id, reported_hour):
    """Verify that the reported hour matches the known event time."""
    known = KNOWN_EVENT_TIMES.get(event_id)
    if not known:
        return False
    return reported_hour == known["hour"]


def verify_all_events(report_events):
    """Verify all events in a report."""
    results = []
    for event in report_events:
        correct = verify_event_time(event["id"], event["hour"])
        results.append({
            "id": event["id"],
            "name": event["name"],
            "reported_hour": event["hour"],
            "expected_hour": KNOWN_EVENT_TIMES.get(event["id"], {}).get("hour"),
            "correct": correct,
        })
    return results
