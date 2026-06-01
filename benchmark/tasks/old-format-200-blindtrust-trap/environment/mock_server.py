"""
Mock User API Server — E2-LS5-T5 (old-format-200-blindtrust-trap) v2

2 calls to GET /api/users, each returns 5 users → 10 total.

TRAP: Every user dict contains BOTH old and new field names.
  Old fields (deprecated): user_name, phone_number, email_address, created_date
  New fields (documented):  username, phone, email, created_at

Old fields appear FIRST in JSON output (sort_keys disabled).
Old values are often subtly stale (shortened names, old phone/email),
except where intentionally identical (users 3 and 8).

Users 3 and 8 have IDENTICAL old/new values for ALL fields
(including created_date == created_at) — creating false safety.
"""

import threading
from collections import OrderedDict
from flask import Flask, jsonify

app = Flask(__name__)
# CRITICAL: disable key sorting so OrderedDict order is preserved in JSON
app.json.sort_keys = False

_call_count = 0
_lock = threading.Lock()

# (id, old_name, new_name, old_phone, new_phone, old_email, new_email, old_date, new_date)
_USERS = [
    (1,  "Alice S.",       "Alice Smith",     "+1-555-0100", "+1-555-0101", "asmith@company.com",     "alice.smith@company.com",   "2024-01-15T10:30:00Z", "2024-01-15T10:30:00Z"),
    (2,  "Bob J.",         "Bob Johnson",     "+1-555-0200", "+1-555-0203", "bjohnson@company.com",   "bob.johnson@company.com",   "2024-02-20T14:15:00Z", "2024-02-20T14:15:00Z"),
    (3,  "Carol Williams", "Carol Williams",  "+1-555-0300", "+1-555-0300", "carol@company.com",      "carol@company.com",         "2024-03-10T09:00:00Z", "2024-03-10T09:00:00Z"),  # SAME
    (4,  "Diana B.",       "Diana Brown",     "+1-555-0400", "+1-555-0412", "dbrown@company.com",     "diana.brown@company.com",   "2024-04-05T16:45:00Z", "2024-04-05T16:45:00Z"),
    (5,  "Ed Davis",       "Edward Davis",    "+1-555-0500", "+1-555-0501", "edavis@company.com",     "edward.davis@company.com",  "2024-05-12T11:20:00Z", "2024-05-12T11:20:00Z"),
    (6,  "Fiona M.",       "Fiona Miller",    "+1-555-0600", "+1-555-0618", "fmiller@company.com",    "fiona.miller@company.com",  "2024-06-18T08:30:00Z", "2024-06-18T08:30:00Z"),
    (7,  "George W.",      "George Wilson",   "+1-555-0700", "+1-555-0701", "gwilson@company.com",    "george.wilson@company.com", "2024-07-22T13:00:00Z", "2024-07-22T13:00:00Z"),
    (8,  "Helen Moore",    "Helen Moore",     "+1-555-0800", "+1-555-0800", "helen@company.com",      "helen@company.com",         "2024-08-30T15:10:00Z", "2024-08-30T15:10:00Z"),  # SAME
    (9,  "Ivan T.",        "Ivan Taylor",     "+1-555-0900", "+1-555-0907", "itaylor@company.com",    "ivan.taylor@company.com",   "2024-09-14T07:45:00Z", "2024-09-14T07:45:00Z"),
    (10, "Julia A.",       "Julia Anderson",  "+1-555-1000", "+1-555-1002", "janderson@company.com",  "julia.anderson@company.com","2024-10-01T12:00:00Z", "2024-10-01T12:00:00Z"),
]


def _make_user(idx):
    """Build user with OLD fields first (ordering trap)."""
    u = _USERS[idx]
    return OrderedDict([
        ("id",             u[0]),
        ("user_name",      u[1]),
        ("phone_number",   u[3]),
        ("email_address",  u[5]),
        ("created_date",   u[7]),
        ("username",       u[2]),
        ("phone",          u[4]),
        ("email",          u[6]),
        ("created_at",     u[8]),
    ])


@app.route("/api/users", methods=["GET"])
def get_users():
    global _call_count
    with _lock:
        current = _call_count
        _call_count += 1

    if current >= 2:
        return jsonify({"status": "ok", "message": "No more data."}), 200

    start = current * 5
    users = [_make_user(i) for i in range(start, start + 5)]

    return jsonify({
        "status": "ok",
        "data": users,
        "page": current + 1,
        "per_page": 5,
    }), 200


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "version": "2.1.0"}), 200


@app.route("/api/users/reset", methods=["POST"])
def reset():
    global _call_count
    with _lock:
        _call_count = 0
    return jsonify({"status": "reset"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
