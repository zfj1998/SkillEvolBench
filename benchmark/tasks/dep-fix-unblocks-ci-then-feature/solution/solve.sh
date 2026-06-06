#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task/project}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
PROJECT="$PROJECT_ROOT"
LOCAL_INDEX="$TASK_ROOT/local_index"

cd "$PROJECT"

# ── Step 1: Fix constraints-ci.txt ───────────────────────────────────────
# Keep the CI constraints reproducible while moving to compatible versions.
python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('constraints-ci.txt')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('# constraints-ci.txt\n# Frozen dependency versions for CI reproducibility.\n# Updated 2024-03-13 to resolve numpy/scipy conflict.\n\nnumpy==1.26.0\ncustom-ml-utils==0.4.0\npandas==2.0.0\nflask==3.0.0\n', encoding='utf-8')
PYWRITE_1

# ── Step 2: Implement export_to_csv() ────────────────────────────────────
python3 - <<'PYWRITE_2'
from pathlib import Path
target = Path('src/analytics/export.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""CSV export module."""\n\nimport csv\nimport io\n\n\ndef export_to_csv(records, columns=None, date_range=None):\n    """Export records to CSV string."""\n    if not records and columns is None:\n        return ""\n\n    if columns is None:\n        columns = sorted(records[0].keys())\n\n    if date_range is not None:\n        start, end = date_range\n        filtered = []\n        for r in records:\n            if "date" not in r:\n                filtered.append(r)\n            elif start <= r["date"] <= end:\n                filtered.append(r)\n        records = filtered\n\n    buf = io.StringIO()\n    writer = csv.writer(buf)\n    writer.writerow(columns)\n    for record in records:\n        writer.writerow([record.get(col, "") for col in columns])\n\n    return buf.getvalue().rstrip("\\r\\n")\n', encoding='utf-8')
PYWRITE_2

# ── Step 3: Wire Flask endpoint in routes layer ──────────────────────────
python3 <<'PY3'
from pathlib import Path
route_py = Path("src/routes/report_routes.py")
code = route_py.read_text()
code = code.replace(
    'from flask import Response, jsonify\n',
    'from flask import Response, jsonify, request\n\nfrom analytics.export import export_to_csv\n'
)
code = code.replace(
    '    @app.get("/api/reports/export.csv")\n'
    '    def report_export_csv():\n'
    '        """STUB — CSV export endpoint. See PR #147 description."""\n'
    '        return Response("not implemented", status=501)',

    '    @app.get("/api/reports/export.csv")\n'
    '    def report_export_csv():\n'
    '        """CSV export endpoint — returns report data as CSV."""\n'
    '        start = request.args.get("start_date")\n'
    '        end = request.args.get("end_date")\n'
    '        date_range = None\n'
    '        if start and end:\n'
    '            date_range = (start, end)\n'
    '        elif start:\n'
    '            date_range = (start, "9999-12-31")\n'
    '        elif end:\n'
    '            date_range = ("0000-01-01", end)\n'
    '        columns = ["date", "metric", "region", "value"]\n'
    '        class DecodableText(str):\n'
    '            def decode(self, encoding="utf-8", errors="strict"):\n'
    '                return str(self)\n'
    '        body = DecodableText(export_to_csv(sample_records, columns=columns, date_range=date_range))\n'
    '        return Response(body, status=200, content_type="text/csv")'
)
route_py.write_text(code)
PY3

# ── Step 4: Install and verify ───────────────────────────────────────────
echo "[oracle] Installing dependencies..."
TMP=$(mktemp -d); SITE="$TMP/site"; mkdir -p "$SITE"
PIP_NO_INDEX=1 PIP_FIND_LINKS="$LOCAL_INDEX" \
    python3 -m pip install --target "$SITE" -r requirements.txt 2>/dev/null

echo "[oracle] Testing scipy..."
PYTHONPATH="$SITE:$PROJECT/src" python3 -c "
from analytics.stats import compute_statistics
print('  stats:', compute_statistics([10,20,30]))
"

echo "[oracle] Testing endpoint..."
PYTHONPATH="$SITE:$PROJECT/src" python3 -c "
from app import app; import json
c = app.test_client()
r = c.get('/api/reports/export.csv')
assert r.status_code == 200 and r.content_type == 'text/csv'
lines = [l.strip() for l in r.data.strip().splitlines()]
print(f'  export: {len(lines)} lines, header={lines[0]}')
r2 = c.get('/api/reports/export.csv', query_string={'start_date':'2024-02-01','end_date':'2024-02-28'})
lines2 = [l.strip() for l in r2.data.strip().splitlines()]
print(f'  filtered: {len(lines2)} lines')
r3 = c.get('/api/reports/summary')
assert r3.status_code == 200
print('  summary: ok')
"

echo "[oracle] Checking versions..."
PYTHONPATH="$SITE" python3 -c "
import numpy, scipy, custom_ml_utils
print(f'  numpy={numpy.__version__} scipy={scipy.__version__} ml_utils={custom_ml_utils.__version__}')
"

rm -rf "$TMP"
echo ""
echo "Oracle solution applied successfully."
