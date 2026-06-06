"""Generate fixture for T1: exact-merge-two-tables.
Creates customers.csv (1000 rows) and orders_summary.csv (800 rows).
200 customers have no orders — agent must use left merge and handle NaN."""
import csv, os, random
from datetime import datetime, timedelta
random.seed(42)
FIRST = ["Alice","Bob","Carol","David","Eva","Frank","Grace","Henry","Irene","James",
    "Karen","Leo","Maria","Nathan","Olivia","Peter","Quinn","Rachel","Sam","Tina",
    "Uma","Victor","Wendy","Xavier","Yolanda","Zach","Amy","Brian","Cindy","Derek"]
LAST = ["Johnson","Smith","Williams","Brown","Martinez","Garcia","Lee","Wilson",
    "Anderson","Thomas","Jackson","White","Harris","Clark","Lewis","Robinson",
    "Walker","Hall","Allen","Young","King","Wright","Scott","Torres","Adams","Nelson"]
D = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(D,"customers.csv"),"w",newline="") as f:
    w=csv.writer(f); w.writerow(["customer_id","name","region","signup_date"])
    for i in range(1,1001):
        w.writerow([i, random.choice(FIRST)+" "+random.choice(LAST),
            random.choice(["North","South","East","West","Central"]),
            (datetime(2020,1,1)+timedelta(days=random.randint(0,1500))).strftime("%Y-%m-%d")])
cids=list(range(1,1001)); random.shuffle(cids); has=sorted(cids[:800])
with open(os.path.join(D,"orders_summary.csv"),"w",newline="") as f:
    w=csv.writer(f); w.writerow(["customer_id","total_orders","total_amount","last_order_date"])
    for c in has:
        w.writerow([c, random.randint(1,50), round(random.uniform(100,50000),2),
            (datetime(2023,1,1)+timedelta(days=random.randint(0,730))).strftime("%Y-%m-%d")])
print("T1 fixture generated")
