"""Generate 1000-row CSV with dates in M/D/YYYY format (non-zero-padded)
mixed with some MM/DD/YYYY. String-sorting these dates gives wrong order."""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

START = datetime(2023, 1, 1)
END = datetime(2024, 12, 31)
DELTA = (END - START).days

ACTIONS = ["LOGIN", "LOGOUT", "UPLOAD", "DOWNLOAD", "DELETE", "VIEW", "EDIT", "SHARE", "COMMENT", "EXPORT"]
USERS = [f"user_{i:03d}" for i in range(1, 81)]
SERVERS = [f"srv-{c}{n}" for c in "ABCD" for n in range(1, 6)]

rows = []
for i in range(1000):
    dt = START + timedelta(days=random.randint(0, DELTA),
                           hours=random.randint(0, 23),
                           minutes=random.randint(0, 59),
                           seconds=random.randint(0, 59))
    # 70% non-zero-padded M/D/YYYY, 30% zero-padded MM/DD/YYYY
    if random.random() < 0.70:
        date_str = f"{dt.month}/{dt.day}/{dt.year}"
    else:
        date_str = dt.strftime("%m/%d/%Y")

    rows.append({
        "log_id": i + 1,
        "date": date_str,
        "time": dt.strftime("%H:%M:%S"),
        "user": random.choice(USERS),
        "action": random.choice(ACTIONS),
        "server": random.choice(SERVERS),
        "bytes_transferred": random.randint(0, 10_000_000) if random.random() < 0.6 else 0,
        "status": random.choices(["OK", "WARN", "ERROR"], weights=[85, 10, 5])[0],
    })

with open("server_logs.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["log_id", "date", "time", "user", "action",
                                            "server", "bytes_transferred", "status"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated server_logs.csv with {len(rows)} rows")
