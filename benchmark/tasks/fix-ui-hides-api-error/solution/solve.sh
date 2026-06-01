#!/bin/bash
# Oracle solution for E1-LS4-T5: fix-ui-hides-api-error
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

# Fix 1: backend/services.py - use specific exception, re-raise on server errors
python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('backend/services.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Business logic layer for user profiles."""\nimport backend.database as db_module\n\n\ndef get_user_profile(user_id):\n    """Get user profile data."""\n    try:\n        user = db_module.db.get_user(user_id)\n        if not user:\n            return {"status": "not_found", "message": "User not found", "data": None}\n        return {"status": "ok", "data": user}\n    except ConnectionError:\n        # Let connection errors propagate so routes can return 500\n        raise\n', encoding='utf-8')
PYWRITE_1

# Fix 2: backend/routes.py - return proper HTTP status codes
python3 - <<'PYWRITE_2'
from pathlib import Path
target = Path('backend/routes.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""API routes for user profiles."""\nimport json\nfrom backend.services import get_user_profile\n\n\ndef handle_get_user(user_id):\n    """Handle GET /api/user/<id>."""\n    try:\n        result = get_user_profile(user_id)\n        if result["status"] == "not_found":\n            return json.dumps(result), 404\n        return json.dumps(result), 200\n    except ConnectionError as e:\n        return json.dumps({"status": "error", "message": str(e), "data": None}), 500\n', encoding='utf-8')
PYWRITE_2

# Fix 3: frontend/UserProfile.jsx - check response status
python3 - <<'PYWRITE_3'
from pathlib import Path
target = Path('frontend/UserProfile.jsx')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('import React, { useState, useEffect } from \'react\';\nimport { fetchUserProfile } from \'./api\';\n\nfunction UserProfile({ userId }) {\n    const [user, setUser] = useState(null);\n    const [loading, setLoading] = useState(true);\n    const [error, setError] = useState(null);\n\n    useEffect(() => {\n        setLoading(true);\n        setError(null);\n        fetchUserProfile(userId)\n            .then(data => {\n                if (data.status === "error") {\n                    setError(data.message || "An error occurred");\n                    setUser(null);\n                } else {\n                    setUser(data.data);\n                    setError(null);\n                }\n                setLoading(false);\n            })\n            .catch(err => {\n                setError(err.message);\n                setLoading(false);\n            });\n    }, [userId]);\n\n    if (loading) return <div className="spinner">Loading...</div>;\n    if (error) return <div className="error-message">Error: {error}</div>;\n    if (!user) return <div className="no-data">No data available</div>;\n\n    return (\n        <div className="user-profile">\n            <h1>{user.name}</h1>\n            <p>{user.email}</p>\n            <span className="role">{user.role}</span>\n        </div>\n    );\n}\n\nexport default UserProfile;\n', encoding='utf-8')
PYWRITE_3

echo "Fix applied: backend returns proper HTTP codes, frontend shows error messages"
