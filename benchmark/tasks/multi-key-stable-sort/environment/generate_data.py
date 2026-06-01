"""Generate 500-row employee CSV with department, salary, name, hire_date.
Key challenge: multiple employees share same department+salary,
requiring stable sort to preserve original input order for ties."""

import csv
import random
from datetime import datetime, timedelta

random.seed(123)

DEPARTMENTS = ["Engineering", "Marketing", "Sales", "Finance", "HR",
               "Operations", "Legal", "Product", "Design", "Support"]

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
    "Charles", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony",
    "Margaret", "Mark", "Sandra", "Donald", "Ashley", "Steven", "Dorothy",
    "Andrew", "Kimberly", "Paul", "Emily", "Joshua", "Donna",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
]

# Salary tiers per department (to create many ties)
SALARY_TIERS = {
    "Engineering": [85000, 95000, 105000, 115000, 125000, 135000],
    "Marketing": [55000, 65000, 75000, 85000, 95000],
    "Sales": [50000, 60000, 70000, 80000, 90000, 100000],
    "Finance": [70000, 80000, 90000, 100000, 110000],
    "HR": [50000, 60000, 70000, 80000],
    "Operations": [45000, 55000, 65000, 75000, 85000],
    "Legal": [80000, 95000, 110000, 125000],
    "Product": [75000, 90000, 105000, 120000],
    "Design": [60000, 70000, 80000, 90000, 100000],
    "Support": [40000, 50000, 60000, 70000],
}

START_DATE = datetime(2015, 1, 1)
END_DATE = datetime(2024, 6, 30)
DELTA_DAYS = (END_DATE - START_DATE).days

rows = []
for i in range(500):
    dept = random.choice(DEPARTMENTS)
    salary = random.choice(SALARY_TIERS[dept])
    hire = START_DATE + timedelta(days=random.randint(0, DELTA_DAYS))

    rows.append({
        "employee_id": i + 1,
        "first_name": random.choice(FIRST_NAMES),
        "last_name": random.choice(LAST_NAMES),
        "department": dept,
        "salary": salary,
        "hire_date": hire.strftime("%Y-%m-%d"),
        "performance_rating": round(random.uniform(1.0, 5.0), 1),
    })

with open("employees.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["employee_id", "first_name", "last_name",
                                            "department", "salary", "hire_date",
                                            "performance_rating"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated employees.csv with {len(rows)} rows")
# Count ties to verify the fixture is challenging
from collections import Counter
dept_salary = [(r["department"], r["salary"]) for r in rows]
ties = sum(1 for count in Counter(dept_salary).values() if count > 1)
print(f"Department+salary groups with ties: {ties}")
