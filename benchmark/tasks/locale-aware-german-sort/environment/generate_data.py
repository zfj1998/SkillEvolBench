"""Generate 200-row CSV with German names containing umlauts and eszett.
Default Python sort puts umlauted characters after Z (Unicode code points),
but correct German phonebook sort treats ae=ä, oe=ö, ue=ü, ss=ß."""

import csv
import random

random.seed(7)

# German surnames — mix of umlaut and non-umlaut names
SURNAMES = [
    "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner",
    "Becker", "Schulz", "Hoffmann", "Schäfer", "Koch", "Bauer", "Richter",
    "Klein", "Wolf", "Schröder", "Neumann", "Schwarz", "Zimmermann",
    "Braun", "Krüger", "Hofmann", "Hartmann", "Lange", "Schmitt", "Werner",
    "Schmitz", "Krause", "Meier", "Lehmann", "Schmid", "Schulze", "Maier",
    "Köhler", "Herrmann", "König", "Walter", "Mayer", "Huber", "Kaiser",
    "Fuchs", "Peters", "Lang", "Scholz", "Möller", "Weiß", "Jung",
    "Hahn", "Schubert", "Vogel", "Friedrich", "Keller", "Günther",
    "Frank", "Berger", "Winkler", "Roth", "Beck", "Lorenz", "Baumann",
    "Franke", "Albrecht", "Schuster", "Simon", "Ludwig", "Böhm", "Winter",
    "Kraus", "Martin", "Schumacher", "Krämer", "Vogt", "Stein", "Jäger",
    "Otto", "Sommer", "Groß", "Seidel", "Heinrich", "Brandt", "Haas",
    "Schreiber", "Graf", "Schulte", "Dietrich", "Ziegler", "Kuhn",
    "Kühn", "Pohl", "Engel", "Horn", "Busch", "Bergmann", "Thomas",
    "Voigt", "Sauer", "Arnold", "Wolff", "Pfeiffer", "Böttcher", "Bär",
    "Förster", "Übel", "Überall", "Ährenfeld", "Ärzte", "Öhler", "Östermann",
]

FIRST_NAMES = [
    "Hans", "Peter", "Michael", "Thomas", "Andreas", "Stefan", "Wolfgang",
    "Klaus", "Jürgen", "Dieter", "Helmut", "Günter", "Werner", "Gerhard",
    "Manfred", "Karl", "Heinrich", "Uwe", "Bernd", "Rainer",
    "Anna", "Maria", "Ursula", "Monika", "Petra", "Brigitte", "Sabine",
    "Karin", "Heike", "Claudia", "Renate", "Ingrid", "Erika", "Helga",
    "Gisela", "Christine", "Bärbel", "Käthe", "Rüdiger", "Björn",
]

CITIES = [
    "Berlin", "München", "Hamburg", "Köln", "Frankfurt", "Stuttgart",
    "Düsseldorf", "Dortmund", "Essen", "Leipzig", "Bremen", "Dresden",
    "Hannover", "Nürnberg", "Duisburg", "Bochum", "Wuppertal", "Bielefeld",
    "Bonn", "Münster",
]

DEPARTMENTS = ["Vertrieb", "Technik", "Buchhaltung", "Personal", "Marketing",
               "Forschung", "Logistik", "Kundendienst"]

rows = []
for i in range(200):
    surname = random.choice(SURNAMES)
    first_name = random.choice(FIRST_NAMES)
    rows.append({
        "contact_id": i + 1,
        "last_name": surname,
        "first_name": first_name,
        "city": random.choice(CITIES),
        "department": random.choice(DEPARTMENTS),
        "phone": f"+49 {random.randint(100, 999)} {random.randint(1000000, 9999999)}",
        "email": f"{first_name.lower().replace('ä','ae').replace('ö','oe').replace('ü','ue').replace('ß','ss')}.{surname.lower().replace('ä','ae').replace('ö','oe').replace('ü','ue').replace('ß','ss')}@firma.de",
    })

with open("german_contacts.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["contact_id", "last_name", "first_name",
                                            "city", "department", "phone", "email"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated german_contacts.csv with {len(rows)} rows")
