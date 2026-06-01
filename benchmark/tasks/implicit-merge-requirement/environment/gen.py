"""T4: implicit merge — 3 CSVs, instructions say only 'clean up the customer list'."""
import csv, json, random, os
random.seed(99)

DOMAINS = ["gmail.com","yahoo.com","acme.com","corp.io","biz.net"]
CITIES  = ["New York","San Francisco","Chicago","Austin","Seattle","Boston","Denver","Miami"]
FIRST   = ["Alice","Bob","Carol","Dave","Eve","Frank","Grace","Henry","Iris","James",
           "Karen","Leo","Maria","Nathan","Olivia","Pete","Quinn","Rachel","Sam","Tina",
           "Uma","Victor","Wendy","Xena","Yuri","Zara","Andy","Beth","Craig","Dana",
           "Evan","Faye","Glen","Hana","Igor","Jane","Kurt","Lily","Marc","Nina",
           "Owen","Petra","Rex","Sasha","Todd","Ula","Vera","Walt","Xin","Yale"]
LAST    = ["Smith","Jones","Brown","Davis","Miller","Wilson","Moore","Taylor","Anderson",
           "Thomas","Jackson","White","Harris","Martin","Thompson","Garcia","Martinez",
           "Robinson","Clark","Rodriguez","Lewis","Lee","Walker","Hall","Allen",
           "Young","Hernandez","King","Wright","Lopez","Hill","Scott","Green","Adams",
           "Baker","Gonzalez","Nelson","Carter","Mitchell","Perez","Roberts","Turner",
           "Phillips","Campbell","Parker","Evans","Edwards","Collins","Stewart","Sanchez"]

people = []
for i in range(850):
    fn = FIRST[i % len(FIRST)]; ln = LAST[i % len(LAST)]
    people.append({"id": f"C{i+1:04d}", "first_name": fn, "last_name": ln,
                   "email": f"{fn.lower()}{i}@{random.choice(DOMAINS)}",
                   "phone": f"555-{random.randint(1000,9999)}",
                   "city": random.choice(CITIES),
                   "company": f"Company{random.randint(1,200)}",
                   "tag": random.choice(["vip","prospect","customer","lead"])})

random.shuffle(people)
pm = {p["id"]: p for p in people}

crm_ids  = set(p["id"] for p in people[:500])
news_ids = set(p["id"] for p in people[:200] + people[500:600])
ev_ids   = set(p["id"] for p in people[:50]  + people[600:750])

out = os.path.dirname(os.path.abspath(__file__))

with open(f"{out}/crm_export.csv","w",newline="") as f:
    w = csv.DictWriter(f,["id","first_name","last_name","email","phone","city","company","tag"])
    w.writeheader()
    rows = [pm[pid] for pid in crm_ids]; random.shuffle(rows)
    w.writerows({k: r[k] for k in ["id","first_name","last_name","email","phone","city","company","tag"]} for r in rows)

with open(f"{out}/newsletter_list.csv","w",newline="") as f:
    w = csv.DictWriter(f,["subscriber_id","full_name","email","city","subscribed_date"])
    w.writeheader()
    rows = []
    for pid in news_ids:
        p = pm[pid]
        rows.append({"subscriber_id":pid,"full_name":f"{p['first_name']} {p['last_name']}",
                     "email":p["email"],"city":p["city"],
                     "subscribed_date":f"202{random.randint(1,4)}-{random.randint(1,12):02d}-01"})
    random.shuffle(rows); w.writerows(rows)

with open(f"{out}/event_attendees.csv","w",newline="") as f:
    w = csv.DictWriter(f,["attendee_id","name","email_address","phone","event","company"])
    w.writeheader()
    rows = []
    for pid in ev_ids:
        p = pm[pid]
        rows.append({"attendee_id":pid,"name":f"{p['first_name']} {p['last_name']}",
                     "email_address":p["email"],"phone":p["phone"],
                     "event":random.choice(["Summit 2024","Webinar Q1","Conference 2023"]),
                     "company":p["company"]})
    random.shuffle(rows); w.writerows(rows)

all_unique = crm_ids | news_ids | ev_ids
with open(f"{out}/ground_truth.json","w") as f:
    json.dump({"total_unique":len(all_unique),"crm":len(crm_ids),
               "newsletter":len(news_ids),"events":len(ev_ids),
               "all_emails":[pm[pid]["email"] for pid in all_unique]}, f, indent=2)
print(f"crm={len(crm_ids)} newsletter={len(news_ids)} events={len(ev_ids)} unique={len(all_unique)}")
