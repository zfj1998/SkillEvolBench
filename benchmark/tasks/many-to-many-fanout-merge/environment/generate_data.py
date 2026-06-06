import csv
import os
import random
import shutil
import unicodedata

random.seed(1337)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def zws(s):
    return "\u200b" + s + "\u200c"


def noisy_header(name):
    variants = [
        name,
        f" {name} ",
        name.upper(),
        name.title(),
        zws(name),
        f"\ufeff{name}",
    ]
    return random.choice(variants)


def write_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def maybe_dirty_int_str(n):
    variants = [
        str(n),
        f" {n}",
        f"{n} ",
        f" {n} ",
        zws(str(n)),
    ]
    return random.choice(variants)


def maybe_null():
    return random.choice(["", " ", "NA", "N/A", "NULL", "None", "nan", "\u200b"])


def clean_text(s):
    return "".join(ch for ch in s if unicodedata.category(ch) != "Cf").strip()


def main():
    # Fresh fixture directory contents
    for name in ["students.csv", "courses.csv", "enrollments.csv"]:
        p = os.path.join(PROJECT_DIR, name)
        if os.path.exists(p):
            os.remove(p)

    # -------------------------
    # students.csv
    # -------------------------
    student_headers = [
        noisy_header("student_id"),
        noisy_header("name"),
        noisy_header("major"),
        noisy_header("gpa"),
    ]

    majors = ["CS", "Math", "History", "Biology", "Physics", "Economics", "English", "Psychology", "Chemistry"]
    student_rows = []

    # 1000 valid unique students
    for sid in range(1, 1001):
        student_rows.append([
            maybe_dirty_int_str(sid),
            f"Student_{sid:04d}",
            random.choice(majors),
            f"{random.uniform(2.0, 4.0):.2f}",
        ])

    # duplicate valid student rows
    for sid in [5, 17, 17, 222, 500, 999]:
        student_rows.append([
            maybe_dirty_int_str(sid),
            f"Student_{sid:04d}_DUP",
            random.choice(majors),
            f"{random.uniform(2.0, 4.0):.2f}",
        ])

    # invalid student rows
    bad_student_ids = [maybe_null(), maybe_null(), "0", "-7", "12.5", "abc", "1e3"]
    for bad in bad_student_ids:
        student_rows.append([
            bad,
            "Bad_Student",
            random.choice(majors),
            f"{random.uniform(2.0, 4.0):.2f}",
        ])

    random.shuffle(student_rows)
    write_csv(os.path.join(PROJECT_DIR, "students.csv"), student_headers, student_rows)

    # -------------------------
    # courses.csv
    # -------------------------
    course_headers = [
        noisy_header("course_id"),
        noisy_header("course_name"),
        noisy_header("department"),
        noisy_header("credits"),
    ]

    departments = ["Mathematics", "English", "Physics", "Art", "History", "Biology", "Economics", "Chemistry", "Computer Science", "Psychology"]
    course_rows = []

    # 200 valid unique courses
    for cid in range(1, 201):
        cname = f"COURSE_{cid:03d}"
        course_rows.append([
            maybe_dirty_int_str(cid),
            random.choice([cname, f" {cname} ", zws(cname)]),
            random.choice(departments),
            str(random.randint(1, 4)),
        ])

    # duplicate course rows: first valid should win
    for cid in [7, 7, 42, 150]:
        course_rows.append([
            maybe_dirty_int_str(cid),
            f"WRONG_NAME_{cid}",
            random.choice(departments),
            str(random.randint(1, 4)),
        ])

    # invalid course rows
    invalid_course_rows = [
        [maybe_null(), "NO_ID", "X", "3"],
        ["0", "ZERO_ID", "X", "3"],
        ["-1", "NEG_ID", "X", "3"],
        ["abc", "BAD_ID", "X", "3"],
        ["201", "   ", "X", "3"],   # invalid because blank name after trim
        ["202", zws(""), "X", "3"],  # invalid because blank after removing Cf
    ]
    course_rows.extend(invalid_course_rows)

    random.shuffle(course_rows)
    write_csv(os.path.join(PROJECT_DIR, "courses.csv"), course_headers, course_rows)

    # -------------------------
    # enrollments.csv
    # -------------------------
    enrollment_headers = [
        noisy_header("student_id"),
        noisy_header("course_id"),
        noisy_header("semester"),
        noisy_header("grade"),
    ]

    semesters = ["Fall2023", "Spring2024", "Fall2024", "Spring2025"]
    grades = ["A", "A-", "B+", "B", "B-", "C+", "C"]

    # Build deterministic valid unique enrollment pairs with controlled popularity.
    unique_pairs = set()
    enrollment_rows = []

    # Force top courses with ties to require secondary sorting by course_name then course_id
    target_counts = {
        7: 60,
        42: 60,
        105: 58,
        3: 58,
        150: 55,
        11: 55,
        88: 54,
        120: 54,
        1: 53,
        200: 53,
        99: 53,
        17: 52,
    }

    used_students = {cid: set() for cid in target_counts}
    for cid, count in target_counts.items():
        while len(used_students[cid]) < count:
            sid = random.randint(1, 1000)
            if sid not in used_students[cid]:
                used_students[cid].add(sid)
                unique_pairs.add((sid, cid))

    # Fill remaining unique valid pairs to 4200
    while len(unique_pairs) < 4200:
        sid = random.randint(1, 1000)
        cid = random.randint(1, 200)
        unique_pairs.add((sid, cid))

    unique_pairs = sorted(unique_pairs)

    # Add each valid pair once
    for sid, cid in unique_pairs:
        enrollment_rows.append([
            maybe_dirty_int_str(sid),
            maybe_dirty_int_str(cid),
            random.choice(semesters),
            random.choice(grades),
        ])

    # Add duplicate rows for many existing pairs, sometimes different semester/grade
    dup_pairs = random.sample(unique_pairs, 900)
    for sid, cid in dup_pairs:
        enrollment_rows.append([
            maybe_dirty_int_str(sid),
            maybe_dirty_int_str(cid),
            random.choice(semesters),
            random.choice(grades),
        ])

    # Add exact duplicate rows too
    exact_dup_pairs = random.sample(unique_pairs, 300)
    for sid, cid in exact_dup_pairs:
        sem = random.choice(semesters)
        grd = random.choice(grades)
        row = [maybe_dirty_int_str(sid), maybe_dirty_int_str(cid), sem, grd]
        enrollment_rows.append(row)
        enrollment_rows.append(list(row))

    # Invalid / unknown references
    bad_enrollments = []
    for _ in range(250):
        bad_enrollments.append([
            maybe_dirty_int_str(random.randint(1001, 1100)),  # unknown student
            maybe_dirty_int_str(random.randint(1, 200)),
            random.choice(semesters),
            random.choice(grades),
        ])
    for _ in range(250):
        bad_enrollments.append([
            maybe_dirty_int_str(random.randint(1, 1000)),
            maybe_dirty_int_str(random.randint(201, 260)),  # unknown course
            random.choice(semesters),
            random.choice(grades),
        ])
    for _ in range(100):
        bad_enrollments.append([
            maybe_null(),
            maybe_dirty_int_str(random.randint(1, 200)),
            random.choice(semesters),
            random.choice(grades),
        ])
    for _ in range(100):
        bad_enrollments.append([
            maybe_dirty_int_str(random.randint(1, 1000)),
            maybe_null(),
            random.choice(semesters),
            random.choice(grades),
        ])
    for _ in range(50):
        bad_enrollments.append([
            random.choice(["0", "-3", "abc", "12.7"]),
            random.choice(["0", "-9", "xyz", "8.2"]),
            random.choice(semesters),
            random.choice(grades),
        ])

    enrollment_rows.extend(bad_enrollments)
    random.shuffle(enrollment_rows)
    write_csv(os.path.join(PROJECT_DIR, "enrollments.csv"), enrollment_headers, enrollment_rows)

    print("Generated harder fixture in", PROJECT_DIR)


if __name__ == "__main__":
    main()