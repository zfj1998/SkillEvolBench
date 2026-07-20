from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


ENV_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "skillevolbench"
    / "harbor_ext"
    / "env.py"
)


def _load_environment_class(
    monkeypatch: pytest.MonkeyPatch,
    docker_environment: type,
) -> type:
    modules = {
        name: ModuleType(name)
        for name in (
            "harbor",
            "harbor.environments",
            "harbor.environments.docker",
            "harbor.environments.docker.docker",
        )
    }
    modules["harbor.environments.docker.docker"].DockerEnvironment = (
        docker_environment
    )
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    module_name = f"_test_sevb_env_{docker_environment.__name__}"
    spec = importlib.util.spec_from_file_location(module_name, ENV_MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GlobalLibraryEnvironment


def _common_args(tmp_path: Path) -> dict[str, Any]:
    library_root = tmp_path / "library"
    (library_root / "active").mkdir(parents=True)
    return {
        "library_root": str(library_root),
        "run_root": str(tmp_path),
        "environment_dir": tmp_path / "environment",
        "environment_name": "fixture",
        "session_id": "session",
        "trial_paths": SimpleNamespace(
            trial_dir=tmp_path / "harbor-job" / "E1-LS1-T1__abcdefg"
        ),
        "task_env_config": object(),
    }


def _assert_complete_mount_set(environment: Any, base_mounts: list[dict]) -> None:
    mounts = environment.forwarded_mounts
    assert mounts[: len(base_mounts)] == base_mounts
    assert len(mounts) == len(base_mounts) + 6
    assert {mount["target"] for mount in mounts[len(base_mounts) :]} == {
        "/root/.claude/skills",
        "/root/.gemini/skills",
        "/root/.agents/skills",
        "/root/.kimi/skills",
        "/skills",
        "/context/injection.json",
    }


def test_current_harbor_mounts_are_preserved_and_extended(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CurrentDockerEnvironment:
        def __init__(self, *, mounts: list[dict] | None = None, **_kwargs: Any):
            self.forwarded_mounts = list(mounts or [])

    environment_cls = _load_environment_class(monkeypatch, CurrentDockerEnvironment)
    base_mounts = [
        {"type": "bind", "source": f"/host/{name}", "target": f"/logs/{name}"}
        for name in ("agent", "verifier", "artifacts")
    ]

    environment = environment_cls(**_common_args(tmp_path), mounts=base_mounts)

    _assert_complete_mount_set(environment, base_mounts)


def test_legacy_harbor_mounts_json_is_still_supported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LegacyDockerEnvironment:
        def __init__(
            self, *, mounts_json: list[dict] | None = None, **_kwargs: Any
        ):
            self.forwarded_mounts = list(mounts_json or [])

    environment_cls = _load_environment_class(monkeypatch, LegacyDockerEnvironment)
    base_mounts = [
        {"type": "bind", "source": "/host/verifier", "target": "/logs/verifier"}
    ]

    environment = environment_cls(**_common_args(tmp_path), mounts_json=base_mounts)

    _assert_complete_mount_set(environment, base_mounts)
