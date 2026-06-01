"""Generate fixture CSVs for T4: implicit-schema-check-before-join.

Creates two CSVs:
  - users.csv: user_id as integer (1, 2, 3, ..., 500), plus region
  - orders.csv: user_id as prefixed string ("USR001", "USR002", ..., "USR500"), plus amount
The type mismatch (int 1 vs str "USR001") causes pd.merge() to return 0 rows.
Agent must extract numeric part or convert to match.
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(2024)

REGIONS = ["North", "South", "East", "West", "Central"]
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer",
    "Michael", "Linda", "David", "Elizabeth", "William", "Barbara",
    "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
    "Christopher", "Karen", "Charles", "Lisa", "Daniel", "Nancy",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
    "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
    "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
    "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
]

BASE_DATE = datetime(2024, 1, 1)

out_dir = os.path.dirname(os.path.abspath(__file__))

# Generate users.csv -- user_id as INTEGER
users_path = os.path.join(out_dir, "users.csv")
with open(users_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["user_id", "name", "region", "signup_date"])
    for uid in range(1, 501):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        region = random.choice(REGIONS)
        signup = (BASE_DATE - timedelta(days=random.randint(30, 730))).strftime("%Y-%m-%d")
        writer.writerow([uid, name, region, signup])

print(f"Generated {users_path} with 500 users (user_id as int)")

# Generate orders.csv -- user_id as PREFIXED STRING ("USR001")
# The prefix forces pandas to read as string (cannot auto-convert to int)
orders_path = os.path.join(out_dir, "orders.csv")
with open(orders_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["order_id", "user_id", "amount", "order_date"])
    for oid in range(1, 3001):
        uid = random.randint(1, 500)
        uid_str = f"USR{uid:03d}"  # "USR001" to "USR500"
        amount = round(random.uniform(5.0, 500.0), 2)
        order_date = (BASE_DATE + timedelta(days=random.randint(0, 364))).strftime("%Y-%m-%d")
        writer.writerow([oid, uid_str, amount, order_date])

print(f"Generated {orders_path} with 3000 orders (user_id as prefixed string 'USR###')")

# Verify the type mismatch
import pandas as pd
df_users = pd.read_csv(users_path)
df_orders = pd.read_csv(orders_path)
print(f"Users user_id dtype: {df_users['user_id'].dtype}")  # int64
print(f"Orders user_id dtype: {df_orders['user_id'].dtype}")  # object (string)
try:
    merged = pd.merge(df_users, df_orders, on="user_id")
    print(f"Naive merge result: {len(merged)} rows (should be 0 or error)")
except ValueError as e:
    print(f"Naive merge FAILED as expected: {e}")
