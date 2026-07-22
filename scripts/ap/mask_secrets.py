"""Mask known credentials in text artifacts before AP uploads them."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path, PurePosixPath


TEXT_SUFFIXES = {
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
}
SECRET_ENV_NAMES = {
    "MODEL_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AP_API_KEY",
    "OSS_ACCESS_KEY_ID",
    "OSS_ACCESS_KEY_SECRET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
}
SAFE_PLACEHOLDER_VALUES = {
    "DUMMY",
    "EMPTY",
    "NONE",
    "NOT-REQUIRED",
    "NOT_REQUIRED",
    "NULL",
}
SANITIZATION_MANIFEST = "sanitization_manifest.json"
MUTABLE_PATHS_EXCLUDED_FROM_MANIFEST = frozenset({"logs/main.log"})
MANIFEST_SCOPE = "changed-utf8-regular-files"

_SECRET_KEY = (
    r"(?:(?:[a-z0-9]+[_-])*(?:api[_-]?key|access[_-]?key[_-]?secret|"
    r"secret[_-]?access[_-]?key|auth[_-]?token|bearer[_-]?token)|"
    r"authorization)"
)
_QUOTED_SECRET_VALUE = re.compile(
    rf"(?i)(\b{_SECRET_KEY}\b[\"']?\s*[:=]\s*)([\"'])[^\r\n]*?\2"
)
_UNQUOTED_SECRET_VALUE = re.compile(
    rf"(?im)(\b{_SECRET_KEY}\b[\"']?\s*[:=]\s*)"
    r"(Bearer\s+)?(?![\"'])([^\s,#}\r\n]+)"
)

_SYSTEM_PYTHON_TARGET = re.compile(r"/usr/bin/python3(?:\.\d+)?")


def _safe_external_venv_interpreter_link(relative: str, target: str) -> bool:
    """Recognize the one inert external link created by ``python -m venv``.

    Task solutions may create ``.venv/bin/python`` as an absolute link to the
    container's system interpreter.  The evidence tree preserves links without
    following or executing them, so this exact shape is safe to retain.  Keep
    the exception deliberately narrow: arbitrary virtualenv names, binaries,
    relative escapes, and non-system targets remain rejected.
    """

    path = PurePosixPath(relative)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) >= 3
        and path.parts[-3:] == (".venv", "bin", "python")
        and _SYSTEM_PYTHON_TARGET.fullmatch(target) is not None
    )


def _mask_keyed_values(text: str) -> str:
    """Mask JSON, YAML, header, and shell-style credential assignments."""

    masked = _QUOTED_SECRET_VALUE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]{match.group(2)}",
        text,
    )
    return _UNQUOTED_SECRET_VALUE.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2) or ''}[REDACTED]"
        ),
        masked,
    )


def _mask_text(
    text: str,
    replacement_pattern: re.Pattern[str] | None,
    *,
    mask_keyed_values: bool = True,
) -> str:
    masked = (
        replacement_pattern.sub("[REDACTED]", text)
        if replacement_pattern is not None
        else text
    )
    return _mask_keyed_values(masked) if mask_keyed_values else masked


def _environment_replacements() -> dict[str, str]:
    replacements: dict[str, str] = {}
    for name in sorted(SECRET_ENV_NAMES):
        value = os.environ.get(name, "")
        if not value:
            continue
        if value.strip().upper() in SAFE_PLACEHOLDER_VALUES:
            continue
        if len(value) < 4:
            raise RuntimeError(
                f"refusing unsafe short value in sensitive environment variable: {name}"
            )
        replacements[value] = "[REDACTED]"
    return replacements


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes, *, mode: int) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.sanitize-",
        dir=path.parent,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _read_manifest(root: Path) -> dict[str, dict[str, str | int]] | None:
    manifest_path = root / SANITIZATION_MANIFEST
    if manifest_path.is_symlink():
        raise RuntimeError(f"refusing symlinked manifest path: {manifest_path}")
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid sanitization manifest: {manifest_path}") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("hash_algorithm") != "sha256"
        or payload.get("scope") != MANIFEST_SCOPE
        or payload.get("excluded_mutable_paths")
        != sorted(MUTABLE_PATHS_EXCLUDED_FROM_MANIFEST)
        or not isinstance(payload.get("changed_files"), list)
    ):
        raise RuntimeError(f"invalid sanitization manifest: {manifest_path}")

    records: dict[str, dict[str, str | int]] = {}
    for raw in payload["changed_files"]:
        if not isinstance(raw, dict):
            raise RuntimeError(f"invalid sanitization manifest: {manifest_path}")
        relative = raw.get("path")
        runtime_sha256 = raw.get("runtime_sha256")
        delivered_sha256 = raw.get("delivered_sha256")
        runtime_size = raw.get("runtime_size")
        delivered_size = raw.get("delivered_size")
        pure = PurePosixPath(relative) if isinstance(relative, str) else None
        if (
            pure is None
            or not relative
            or relative == "."
            or pure.is_absolute()
            or ".." in pure.parts
            or pure.as_posix() != relative
            or relative == SANITIZATION_MANIFEST
            or relative in MUTABLE_PATHS_EXCLUDED_FROM_MANIFEST
            or not isinstance(runtime_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", runtime_sha256) is None
            or not isinstance(delivered_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", delivered_sha256) is None
            or type(runtime_size) is not int
            or runtime_size < 0
            or type(delivered_size) is not int
            or delivered_size < 0
            or relative in records
        ):
            raise RuntimeError(f"invalid sanitization manifest: {manifest_path}")
        artifact_path = root / relative
        try:
            artifact_path.resolve(strict=True).relative_to(root.resolve())
        except (FileNotFoundError, ValueError) as exc:
            raise RuntimeError(
                f"sanitization manifest artifact is missing or unsafe: {relative}"
            ) from exc
        if artifact_path.is_symlink() or not artifact_path.is_file():
            raise RuntimeError(
                f"sanitization manifest artifact is not a regular file: {relative}"
            )
        try:
            delivered = artifact_path.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                f"cannot read sanitization manifest artifact: {relative}"
            ) from exc
        if len(delivered) != delivered_size or _sha256(delivered) != delivered_sha256:
            raise RuntimeError(
                f"sanitization manifest delivered digest mismatch: {relative}"
            )
        records[relative] = {
            "path": relative,
            "runtime_sha256": runtime_sha256,
            "delivered_sha256": delivered_sha256,
            "runtime_size": runtime_size,
            "delivered_size": delivered_size,
        }
    if payload.get("changed_file_count") != len(records):
        raise RuntimeError(f"invalid sanitization manifest: {manifest_path}")
    return records


def _write_manifest(
    root: Path,
    changed_files: list[dict[str, str | int]],
) -> None:
    manifest_path = root / SANITIZATION_MANIFEST
    payload = {
        "schema_version": 1,
        "hash_algorithm": "sha256",
        "scope": MANIFEST_SCOPE,
        "excluded_mutable_paths": sorted(MUTABLE_PATHS_EXCLUDED_FROM_MANIFEST),
        "changed_file_count": len(changed_files),
        "changed_files": sorted(changed_files, key=lambda item: item["path"]),
    }
    _atomic_write(
        manifest_path,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        mode=0o644,
    )


def mask_tree(root: Path) -> int:
    if not root.exists() or not root.is_dir() or root.is_symlink():
        raise RuntimeError(f"artifact root must be a real directory: {root}")
    existing_manifest = _read_manifest(root)
    replacements = _environment_replacements()
    ordered_secrets = sorted(
        replacements, key=lambda secret: (-len(secret), secret)
    )
    replacement_pattern = (
        re.compile("|".join(re.escape(secret) for secret in ordered_secrets))
        if ordered_secrets
        else None
    )
    secret_bytes = tuple(secret.encode("utf-8") for secret in ordered_secrets)
    changed_files: list[dict[str, str | int]] = []
    pending_writes: list[tuple[Path, str, bytes, bytes]] = []
    mutable_paths: list[tuple[Path, str]] = []
    resolved_root = root.resolve()
    manifest_path = root / SANITIZATION_MANIFEST
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if any(secret in relative for secret in ordered_secrets):
            raise RuntimeError(
                f"artifact path contains a sensitive value: {relative}"
            )
        if path.name == SANITIZATION_MANIFEST and path != manifest_path:
            raise RuntimeError(f"refusing nested sanitization manifest: {relative}")
        if path.is_symlink():
            try:
                link_target = os.readlink(path)
            except OSError as exc:
                raise RuntimeError(f"cannot inspect artifact symlink: {relative}") from exc
            if any(secret in link_target for secret in ordered_secrets):
                raise RuntimeError(
                    f"artifact symlink target contains a sensitive value: {relative}"
                )
            try:
                path.resolve(strict=False).relative_to(resolved_root)
            except ValueError as exc:
                if not _safe_external_venv_interpreter_link(relative, link_target):
                    raise RuntimeError(
                        f"refusing artifact symlink outside output root: {path}"
                    ) from exc
            continue
        if (
            not path.is_file()
            or path == manifest_path
        ):
            continue
        if relative in MUTABLE_PATHS_EXCLUDED_FROM_MANIFEST:
            mutable_paths.append((path, relative))
            continue
        try:
            before = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"cannot read artifact: {relative}") from exc
        is_supported_text = path.suffix.lower() in TEXT_SUFFIXES
        contains_exact_secret = any(secret in before for secret in secret_bytes)
        if not is_supported_text and not contains_exact_secret:
            continue
        try:
            text = before.decode("utf-8")
        except UnicodeDecodeError as exc:
            if contains_exact_secret:
                raise RuntimeError(
                    f"refusing non-UTF-8 artifact containing a sensitive value: {relative}"
                ) from exc
            raise RuntimeError(f"cannot sanitize text artifact: {relative}") from exc
        masked = _mask_text(
            text,
            replacement_pattern,
            mask_keyed_values=is_supported_text,
        )
        if masked != text:
            after = masked.encode("utf-8")
            pending_writes.append((path, relative, before, after))
            if relative not in MUTABLE_PATHS_EXCLUDED_FROM_MANIFEST:
                changed_files.append(
                    {
                        "path": relative,
                        "runtime_sha256": _sha256(before),
                        "delivered_sha256": _sha256(after),
                        "runtime_size": len(before),
                        "delivered_size": len(after),
                    }
                )
    if existing_manifest is not None:
        if pending_writes:
            raise RuntimeError(
                "sanitization manifest already seals the artifact tree"
            )
    else:
        for path, relative, before, after in pending_writes:
            if path.is_symlink() or not path.is_file():
                raise RuntimeError(f"artifact changed during sanitization: {relative}")
            try:
                current = path.read_bytes()
            except OSError as exc:
                raise RuntimeError(
                    f"cannot re-read text artifact before sanitizing: {relative}"
                ) from exc
            if current != before:
                raise RuntimeError(f"artifact changed during sanitization: {relative}")
            _atomic_write(path, after, mode=stat.S_IMODE(path.stat().st_mode))
        _write_manifest(root, changed_files)

    mutable_changed = 0
    for path, relative in mutable_paths:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"artifact changed during sanitization: {relative}")
        try:
            current = path.read_bytes()
            text = current.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"cannot sanitize mutable artifact: {relative}") from exc
        after = _mask_text(text, replacement_pattern).encode("utf-8")
        # Always detach the active writer from the upload path: an already-open
        # append descriptor continues on the old inode, while AP sees this
        # sanitized snapshot. Finalizer-tail lines are available through
        # metrics.json and are not part of the digest promise.
        _atomic_write(path, after, mode=stat.S_IMODE(path.stat().st_mode))
        if after != current:
            mutable_changed += 1
    return (0 if existing_manifest is not None else len(pending_writes)) + mutable_changed


def main() -> int:
    root = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("OUTPUT_DIR", "/tmp/output")
    )
    if not root.exists():
        return 0
    print(f"Masked secrets in {mask_tree(root)} text artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
