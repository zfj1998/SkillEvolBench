"""Remove redundant OpenCode runtime state after canonical exports are sealed.

OpenCode's SQLite state is useful while a task is running, but it is neither
the canonical trajectory nor the canonical session export.  Shipping it makes
AP artifacts much larger and can retain arbitrary task strings in a binary
surface that the text sanitizer cannot safely rewrite.  This module removes
only the narrowly-scoped per-trial ``xdg-data`` directory, records a no-follow
digest of every removed tree, and binds the operation into metrics/provenance.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_NAME = "runtime_artifact_pruning_manifest.json"
POLICY = "remove-redundant-opencode-xdg-data-after-session-export"
_CANDIDATE_GLOB = "runs/*/harbor-job/*/*/agent/opencode/xdg-data"
_CANDIDATE_RE = re.compile(
    r"^runs/[^/]+/harbor-job/[^/]+/[^/]+/agent/opencode/xdg-data$"
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _tree_record(root: Path, candidate: Path) -> dict[str, Any]:
    relative = candidate.relative_to(root).as_posix()
    if _CANDIDATE_RE.fullmatch(relative) is None:
        raise RuntimeError(f"refusing unexpected runtime-state path: {relative}")
    if candidate.is_symlink() or not candidate.is_dir():
        raise RuntimeError(f"runtime-state root is not a real directory: {relative}")

    digest = hashlib.sha256()
    directory_count = 0
    regular_file_count = 0
    symlink_count = 0
    regular_file_bytes = 0
    stack = [candidate]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda entry: entry.name)
        except OSError as exc:
            raise RuntimeError(f"cannot inspect runtime-state tree: {relative}") from exc
        for entry in entries:
            path = Path(entry.path)
            inside = path.relative_to(candidate).as_posix()
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise RuntimeError(
                    f"cannot stat runtime-state entry: {relative}/{inside}"
                ) from exc
            permissions = stat.S_IMODE(mode)
            if stat.S_ISDIR(mode):
                directory_count += 1
                digest.update(f"D\0{inside}\0{permissions:o}\n".encode())
                stack.append(path)
            elif stat.S_ISREG(mode):
                file_hash = _sha256_file(path)
                size = entry.stat(follow_symlinks=False).st_size
                regular_file_count += 1
                regular_file_bytes += size
                digest.update(
                    f"F\0{inside}\0{permissions:o}\0{size}\0{file_hash}\n".encode()
                )
            elif stat.S_ISLNK(mode):
                try:
                    target_hash = hashlib.sha256(os.readlink(path).encode()).hexdigest()
                except OSError as exc:
                    raise RuntimeError(
                        f"cannot inspect runtime-state symlink: {relative}/{inside}"
                    ) from exc
                symlink_count += 1
                digest.update(
                    f"L\0{inside}\0{permissions:o}\0{target_hash}\n".encode()
                )
            else:
                raise RuntimeError(
                    f"unsupported runtime-state object: {relative}/{inside}"
                )

    agent_dir = candidate.parent.parent
    trajectory = agent_dir / "trajectory.json"
    session_export = agent_dir / "opencode.session.json"

    def canonical_hash(path: Path) -> str | None:
        return (
            _sha256_file(path)
            if not path.is_symlink() and path.is_file()
            else None
        )

    return {
        "path": relative,
        "tree_sha256": digest.hexdigest(),
        "directory_count": directory_count,
        "regular_file_count": regular_file_count,
        "regular_file_bytes": regular_file_bytes,
        "symlink_count": symlink_count,
        "canonical_trajectory_sha256": canonical_hash(trajectory),
        "canonical_session_export_sha256": canonical_hash(session_export),
    }


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy": POLICY,
        "manifest": MANIFEST_NAME,
        "removed_directory_count": len(records),
        "removed_regular_file_count": sum(
            int(record["regular_file_count"]) for record in records
        ),
        "removed_regular_file_bytes": sum(
            int(record["regular_file_bytes"]) for record in records
        ),
        "removed_symlink_count": sum(int(record["symlink_count"]) for record in records),
    }


def _validate_record(root: Path, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError("invalid runtime artifact pruning manifest")
    relative = raw.get("path")
    pure = PurePosixPath(relative) if isinstance(relative, str) else None
    if (
        pure is None
        or pure.is_absolute()
        or ".." in pure.parts
        or pure.as_posix() != relative
        or _CANDIDATE_RE.fullmatch(relative) is None
        or (root / relative).exists()
        or (root / relative).is_symlink()
        or _HEX64.fullmatch(str(raw.get("tree_sha256", ""))) is None
    ):
        raise RuntimeError("invalid runtime artifact pruning manifest")
    for field in (
        "directory_count",
        "regular_file_count",
        "regular_file_bytes",
        "symlink_count",
    ):
        value = raw.get(field)
        if type(value) is not int or value < 0:
            raise RuntimeError("invalid runtime artifact pruning manifest")
    for field in (
        "canonical_trajectory_sha256",
        "canonical_session_export_sha256",
    ):
        value = raw.get(field)
        if value is not None and (
            not isinstance(value, str) or _HEX64.fullmatch(value) is None
        ):
            raise RuntimeError("invalid runtime artifact pruning manifest")
    return raw


def read_manifest(root: Path) -> dict[str, Any] | None:
    path = root / MANIFEST_NAME
    if path.is_symlink():
        raise RuntimeError("invalid runtime artifact pruning manifest")
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid runtime artifact pruning manifest") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("policy") != POLICY
        or not isinstance(payload.get("removed_directories"), list)
    ):
        raise RuntimeError("invalid runtime artifact pruning manifest")
    records = [_validate_record(root, raw) for raw in payload["removed_directories"]]
    paths = [record["path"] for record in records]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise RuntimeError("invalid runtime artifact pruning manifest")
    expected = _summary(records)
    if any(payload.get(key) != value for key, value in expected.items()):
        raise RuntimeError("invalid runtime artifact pruning manifest")
    return payload


def _annotate(path: Path, summary: dict[str, Any]) -> None:
    if path.is_symlink() or not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot annotate pruning provenance: {path.name}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"cannot annotate pruning provenance: {path.name}")
    existing = payload.get("runtime_artifact_pruning")
    if existing not in (None, summary):
        raise RuntimeError(f"conflicting pruning provenance: {path.name}")
    payload["runtime_artifact_pruning"] = summary
    _atomic_json(path, payload)


def prune_tree(root: Path) -> int:
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError(f"artifact root must be a real directory: {root}")
    existing = read_manifest(root)
    if existing is not None:
        if list(root.glob(_CANDIDATE_GLOB)):
            raise RuntimeError("runtime state appeared after pruning manifest was sealed")
        return int(existing["removed_directory_count"])

    candidates = sorted(root.glob(_CANDIDATE_GLOB), key=lambda path: path.as_posix())
    records = [_tree_record(root, candidate) for candidate in candidates]
    for candidate in candidates:
        shutil.rmtree(candidate)
    if list(root.glob(_CANDIDATE_GLOB)):
        raise RuntimeError("runtime-state pruning was incomplete")

    summary = _summary(records)
    _annotate(root / "metrics.json", summary)
    _annotate(root / "ap_run_manifest.json", summary)
    payload = {**summary, "removed_directories": records}
    _atomic_json(root / MANIFEST_NAME, payload)
    return len(records)


def main() -> int:
    if len(sys.argv) > 2:
        raise SystemExit("usage: prune_runtime_artifacts.py [OUTPUT_DIR]")
    root = Path(sys.argv[1] if len(sys.argv) == 2 else os.environ["OUTPUT_DIR"])
    print(f"Pruned {prune_tree(root)} redundant OpenCode runtime-state directorie(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
