"""Process verifier for E1-LS2-T2.

P1: No --force / --legacy-peer-deps; installed version consistent with declared
P2: @acme/ui-components upgraded to 4.x in package.json
P3: React not downgraded from 18.x
P4: App.js adapted label → text (ui-components 4.0 breaking change)
P5: App.js migrated from ReactDOM.render to createRoot (React 18 API)
"""

import json
import re
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = TASK_DIR / "project" / "frontend-app"
PKG_JSON = PROJECT_DIR / "package.json"


def _read_pkg():
    return json.loads(PKG_JSON.read_text(encoding="utf-8"))


def _installed_ui_version():
    nm_pkg = PROJECT_DIR / "node_modules" / "@acme" / "ui-components" / "package.json"
    if not nm_pkg.exists():
        return None
    return json.loads(nm_pkg.read_text(encoding="utf-8")).get("version")


def test_process_p1_no_force_or_legacy_peer_deps():
    """No bypass flags; installed version matches declared version."""
    for path in PROJECT_DIR.rglob("*"):
        if not path.is_file() or "node_modules" in path.parts:
            continue
        if path.suffix not in {".js", ".json", ".sh", ".md", ".txt", ""} and path.name != ".npmrc":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "--legacy-peer-deps" in text:
            raise AssertionError(f"Found --legacy-peer-deps in {path.relative_to(TASK_DIR)}")
        if re.search(r"(?<!\w)--force(?!\w|-)", text):
            raise AssertionError(f"Found --force in {path.relative_to(TASK_DIR)}")

    npmrc = PROJECT_DIR / ".npmrc"
    if npmrc.exists():
        assert "legacy-peer-deps=true" not in npmrc.read_text(encoding="utf-8"), \
            ".npmrc sets legacy-peer-deps=true"

    installed = _installed_ui_version()
    if installed is not None:
        declared = _read_pkg().get("dependencies", {}).get("@acme/ui-components", "")
        if re.search(r"4", declared):
            assert installed.startswith("4."), (
                f"package.json says '{declared}' but node_modules has {installed} — "
                f"was --force used to install a mismatched version?"
            )


def test_process_p2_ui_components_upgraded():
    """@acme/ui-components references 4.x (not 3.x) in package.json."""
    ui = _read_pkg().get("dependencies", {}).get("@acme/ui-components", "")
    assert re.search(r"4", ui), f"ui-components is '{ui}' — expected 4.x"
    assert not re.match(r"[\^~]?3\.", ui), f"ui-components still 3.x: '{ui}'"


def test_process_p3_no_react_downgrade():
    """React not downgraded below 18."""
    react = _read_pkg().get("dependencies", {}).get("react", "")
    assert re.search(r"18", react), f"React is '{react}' — must be >=18"
    assert not re.match(r"[\^~]?17\.", react), f"React downgraded to 17: '{react}'"


def test_process_p4_label_to_text_adapted():
    """App code uses 4.0 'text' prop, not 3.x 'label' prop for Button."""
    app_js = (PROJECT_DIR / "src" / "App.js").read_text(encoding="utf-8")
    props_js = (PROJECT_DIR / "src" / "componentProps.js").read_text(encoding="utf-8")
    assert "@acme/ui-components" in app_js, "App.js no longer imports ui-components"
    assert "@acme/forms" in app_js, "App.js no longer imports forms"
    combined = app_js + "\n" + props_js
    assert "text" in combined, (
        "App code still doesn't use the 4.0 'text' prop"
    )
    assert "label:" not in props_js, (
        "componentProps.js still returns the old 'label' prop"
    )


def test_process_p5_createroot_migration():
    """App uses React 18 createRoot, not the removed ReactDOM.render."""
    app_js = (PROJECT_DIR / "src" / "App.js").read_text(encoding="utf-8")
    compat_js = (PROJECT_DIR / "src" / "compat.js").read_text(encoding="utf-8")
    assert "createRoot" in (app_js + "\n" + compat_js), (
        "App code does not use createRoot — mountApp must migrate from "
        "ReactDOM.render to React 18 createRoot"
    )
    lines = [l.strip() for l in app_js.splitlines() if not l.strip().startswith("//")]
    for line in lines:
        if "ReactDOM.render(" in line:
            raise AssertionError(
                f"App.js still calls ReactDOM.render() — "
                f"must migrate to createRoot. Line: {line!r}"
            )
