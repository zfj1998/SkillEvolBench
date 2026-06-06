"""Outcome verifier for E1-LS2-T2: npm-react18-ui-lib-peer-conflict.

_install_project() uses node-based semver matching against available tarballs,
driven by the CURRENT package.json. Broken state → broken install → tests fail.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

TASK_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = TASK_DIR / "project" / "frontend-app"
LOCAL_PKGS = TASK_DIR / "project" / "local_packages"

_CATALOG = {
    "react":                [("18.2.0", "react-18.2.0.tgz")],
    "react-dom":            [("18.2.0", "react-dom-18.2.0.tgz")],
    "@acme/ui-components":  [("3.2.0", "acme-ui-components-3.2.0.tgz"),
                             ("4.0.0", "acme-ui-components-4.0.0.tgz")],
    "@acme/forms":          [("2.0.0", "acme-forms-2.0.0.tgz")],
}


def _semver_satisfies(version, range_str):
    js = (
        f"var v='{version}'.split('.').map(Number),"
        f"r='{range_str}'.trim();"
        "var m=r.match(/([\\^~><=]*)\\s*(\\d+)(?:\\.(\\d+))?(?:\\.(\\d+))?/);"
        "if(!m)process.exit(1);"
        "var op=m[1],rM=+(m[2]||0),rm=+(m[3]||0),rp=+(m[4]||0);"
        "var vM=v[0],vm=v[1],vp=v[2],ok=false;"
        "if(op==='^')ok=vM===rM&&(vM>0?(vm*1000+vp)>=(rm*1000+rp):vm===rm&&vp>=rp);"
        "else if(op==='~')ok=vM===rM&&vm===rm&&vp>=rp;"
        "else if(op==='>='||op==='=>')ok=(vM*1e6+vm*1e3+vp)>=(rM*1e6+rm*1e3+rp);"
        "else ok=vM===rM&&vm===rm&&vp===rp;"
        "process.exit(ok?0:1)"
    )
    return subprocess.run(["node", "-e", js], capture_output=True, timeout=5).returncode == 0


def _resolve_tarball(pkg_name, range_str):
    candidates = _CATALOG.get(pkg_name, [])
    matching = [(v, f) for v, f in candidates if _semver_satisfies(v, range_str)]
    matching.sort(key=lambda x: [int(n) for n in x[0].split(".")], reverse=True)
    return str(LOCAL_PKGS / matching[0][1]) if matching else None


def _install_project():
    tmp = tempfile.TemporaryDirectory()
    app = Path(tmp.name) / "app"
    shutil.copytree(PROJECT_DIR, app)
    nm = app / "node_modules"
    if nm.exists():
        shutil.rmtree(nm)
    pkg = json.loads((app / "package.json").read_text())
    tarballs = [_resolve_tarball(n, v) for n, v in pkg.get("dependencies", {}).items()]
    tarballs = [t for t in tarballs if t]
    result = subprocess.run(
        ["npm", "install"] + tarballs + ["--no-audit", "--no-fund"],
        cwd=str(app), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=30,
    )
    return tmp, app, result


def _node(app, code):
    return subprocess.run(
        ["node", "-e", code], cwd=str(app),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10,
    )


# ── Public tests ──────────────────────────────────────────────────────────

def test_public_install_succeeds():
    tmp, app, r = _install_project()
    try:
        assert r.returncode == 0, f"npm install failed:\n{r.stderr}"
    finally:
        tmp.cleanup()


def test_public_tests_pass():
    tmp, app, r = _install_project()
    try:
        assert r.returncode == 0, f"npm install failed:\n{r.stderr}"
        t = subprocess.run(
            ["node", "tests/test.js"], cwd=str(app),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10,
        )
        assert t.returncode == 0, f"Tests failed:\n{t.stdout}\n{t.stderr}"
    finally:
        tmp.cleanup()


# ── Hidden tests ──────────────────────────────────────────────────────────

@pytest.mark.hidden
def test_hidden_h1_zero_eresolve():
    tmp, app, r = _install_project()
    try:
        assert r.returncode == 0, r.stderr
        assert "ERESOLVE" not in r.stderr
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h2_button_renders():
    """Button must return 'Button:Submit' — catches --force trap (3.2.0 throws)
    AND missing label→text adaptation (4.0.0 returns 'Button:default')."""
    tmp, app, r = _install_project()
    try:
        assert r.returncode == 0, r.stderr
        t = _node(app, "var A=require('./src/App'); console.log(A.renderButton())")
        assert t.returncode == 0, f"renderButton threw:\n{t.stderr}"
        assert t.stdout.strip() == "Button:Submit", (
            f"Got '{t.stdout.strip()}'. "
            f"ui-components 3.2.0 + React 18 → throw; "
            f"4.0.0 without label→text fix → 'Button:default'"
        )
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h3_formfield_renders():
    tmp, app, r = _install_project()
    try:
        assert r.returncode == 0, r.stderr
        t = _node(app, "var A=require('./src/App'); console.log(A.renderForm())")
        assert t.returncode == 0, t.stderr
        assert t.stdout.strip() == "FormField:email:valid"
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h4_no_dual_react_instance():
    """Check for duplicate react installs in the node_modules tree."""
    tmp, app, r = _install_project()
    try:
        assert r.returncode == 0, r.stderr
        # Check root-level react version
        t = _node(app, "var R=require('react'); console.log(R.version)")
        assert t.returncode == 0, t.stderr
        assert t.stdout.strip() == "18.2.0"
        # Check no nested react under any scoped package
        t2 = _node(app, """
var fs=require('fs'), path=require('path');
var nm=path.join(process.cwd(),'node_modules');
var nested=[];
function walk(dir,depth){
  if(depth>3)return;
  try{var entries=fs.readdirSync(dir);}catch(e){return;}
  entries.forEach(function(e){
    var p=path.join(dir,e);
    if(e==='react'&&dir!==nm){nested.push(p)}
    if(e.startsWith('@')||e==='node_modules'){try{walk(p,depth+1)}catch(x){}}
  });
}
walk(nm,0);
console.log(nested.length===0?'clean':'DUAL:'+nested.join(','));
""")
        assert t2.returncode == 0, t2.stderr
        assert t2.stdout.strip() == "clean", (
            f"Found nested react installs: {t2.stdout.strip()}"
        )
    finally:
        tmp.cleanup()


@pytest.mark.hidden
def test_hidden_h5_mountapp_uses_createroot():
    """mountApp() must work — proves code migrated from ReactDOM.render to createRoot.
    If App.js still calls ReactDOM.render, it throws TypeError (React 18 removed it)."""
    tmp, app, r = _install_project()
    try:
        assert r.returncode == 0, r.stderr
        t = _node(app, """
try {
    var App = require('./src/App');
    var result = App.mountApp({id:'root'});
    console.log(result);
} catch(e) {
    console.error('MOUNT_FAILED:' + e.message);
    process.exit(1);
}
""")
        assert t.returncode == 0, (
            f"mountApp() failed — App.js likely still uses ReactDOM.render "
            f"(removed in React 18). Migrate to createRoot.\n{t.stderr}"
        )
        assert t.stdout.strip() == "Button:Submit | FormField:email:valid", (
            f"mountApp() returned '{t.stdout.strip()}'"
        )
    finally:
        tmp.cleanup()
