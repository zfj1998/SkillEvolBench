#!/usr/bin/env bash
set -euo pipefail

TASK_ROOT="${TASK_ROOT:-/root/task}"
PROJECT_ROOT="${PROJECT_ROOT:-/root/task/frontend-app}"
LOCAL_PKGS="$TASK_ROOT/local_packages"
export npm_config_cache="${TASK_ROOT}/.npm-cache"
mkdir -p "$npm_config_cache"

# ── Step 1: Install from local tarballs (4.0.0 for ui-components) ────────
cd "$PROJECT_ROOT"
rm -rf node_modules package-lock.json

npm install \
    "$LOCAL_PKGS/react-18.2.0.tgz" \
    "$LOCAL_PKGS/react-dom-18.2.0.tgz" \
    "$LOCAL_PKGS/acme-ui-components-4.0.0.tgz" \
    "$LOCAL_PKGS/acme-forms-2.0.0.tgz" \
    --no-audit --no-fund 2>&1

# ── Step 2: Restore package.json with correct semver ─────────────────────
# (npm install <tgz> rewrites deps to file: paths; restore proper ranges)
python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('"$PROJECT_ROOT/package.json"')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('{\n  "name": "frontend-app",\n  "version": "1.0.0",\n  "private": true,\n  "description": "Internal dashboard with UI components and forms",\n  "main": "src/App.js",\n  "scripts": {\n    "test": "node tests/test.js"\n  },\n  "dependencies": {\n    "react": "^18.2.0",\n    "react-dom": "^18.2.0",\n    "@acme/ui-components": "^4.0.0",\n    "@acme/forms": "^2.0.0"\n  }\n}\n', encoding='utf-8')
PYWRITE_1

# ── Step 3: Adapt code for 4.0 breaking change (label → text)
#            + migrate ReactDOM.render → createRoot (React 18)
PROJECT_ROOT="$PROJECT_ROOT" python3 <<'PYFIX'
import os
from pathlib import Path

root = Path(os.environ["PROJECT_ROOT"])
app = Path(os.environ["PROJECT_ROOT"]) / "src" / "App.js"
code = app.read_text()
props = root / "src" / "componentProps.js"
props_code = props.read_text()
props_code = props_code.replace("return { label: 'Submit' };", "return { text: 'Submit' };")
props.write_text(props_code)

code = code.replace("ReactDOM.render(content, container);", "return require('./compat').mountWithReact18(container, content);")
app.write_text(code)
PYFIX

# ── Step 4: Run tests ────────────────────────────────────────────────────
echo ""
echo "[oracle] Running tests..."
node tests/test.js

echo ""
echo "Oracle solution applied successfully."
