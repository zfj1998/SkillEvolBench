#!/usr/bin/env python3
"""Read-only safety scan for an exported SkillEvolBench AP evidence tree.

The scanner never follows symlinks, never writes beneath the scanned root, and
never prints matched values or file contents.  Its JSON result contains only
aggregate counts.  ``artifacts.json`` contents are skipped by default because
AP uses that transport file for signed download metadata; filenames and any
symlink with that name are still inspected.

Optional exact-value checks are loaded only from :data:`SECRET_ENV_NAMES`.
Secret values are not accepted as command-line arguments and are never copied
into the result.

Usage::

    python scripts/ap/scan_export_safety.py /path/to/exported/group

Exit status is zero only for a complete scan with no finding.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


SCHEMA_VERSION = 1
CHUNK_SIZE = 1024 * 1024
MIN_EXACT_SECRET_BYTES = 8
MAX_EXACT_SECRET_BYTES = 64 * 1024
SKIPPED_TRANSPORT_NAME = "artifacts.json"

# Keep this list explicit: adding arbitrary environment-variable names through
# a CLI flag would make operator secrets visible in process listings.
SECRET_ENV_NAMES = frozenset(
    {
        "ALIBABA_CLOUD_ACCESS_KEY_ID",
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
        "ANTHROPIC_API_KEY",
        "AP_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AZURE_OPENAI_API_KEY",
        "DOCKER_PASSWORD",
        "MODEL_API_KEY",
        "OPENAI_API_KEY",
        "OSS_ACCESS_KEY_ID",
        "OSS_ACCESS_KEY_SECRET",
        "REGISTRY_PASSWORD",
    }
)

CONTENT_CATEGORIES = (
    "credential_assignment",
    "exact_secret_value",
    "no_auth_sentinel",
    "private_key_header",
    "signed_url_query",
)
FILESYSTEM_CATEGORIES = (
    "root_is_symlink",
    "symlink_escapes_root",
    "unreadable_directory",
    "unreadable_file",
    "unreadable_symlink",
    "unsupported_object",
)
ALL_CATEGORIES = tuple(sorted(CONTENT_CATEGORIES + FILESYSTEM_CATEGORIES))
ALL_SURFACES = (
    "content",
    "filename",
    "filesystem",
    "symlink_safety",
    "symlink_target",
)

PRIVATE_KEY_HEADER_RE = re.compile(
    rb"-----BEGIN [A-Z0-9 -]{0,64}PRIVATE KEY(?: BLOCK)?-----",
    re.IGNORECASE,
)
SIGNED_URL_QUERY_RE = re.compile(
    rb"(?:\?|&|&amp;|%3[fF]|%26)"
    rb"(?:AWSAccessKeyId|GoogleAccessId|OSSAccessKeyId|Signature|sig|"
    rb"x-amz-credential|x-amz-security-token|x-amz-signature|"
    rb"x-goog-credential|x-goog-signature|x-oss-credential|"
    rb"x-oss-security-token|x-oss-signature)(?:=|%3[dD])",
    re.IGNORECASE,
)
NO_AUTH_SENTINEL_RE = re.compile(rb"sevb-no-auth-", re.IGNORECASE)
KNOWN_CREDENTIAL_VALUE_RE = re.compile(
    rb"(?:"
    rb"(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}"
    rb"|gh[pousr]_[A-Za-z0-9]{16,}"
    rb"|(?:AKIA|ASIA)[A-Z0-9]{16}"
    rb"|LTAI[A-Za-z0-9]{12,}"
    rb"|AIza[0-9A-Za-z_-]{20,}"
    rb"|xox[baprs]-[A-Za-z0-9-]{16,}"
    rb"|eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{8,}"
    rb")",
)
CREDENTIAL_ASSIGNMENT_RE = re.compile(
    rb"""
    (?<![A-Za-z0-9_])
    ["']?
    (?:[A-Za-z0-9]+[_-]){0,4}
    (?:
        api[_-]?key
        | access[_-]?key(?:[_-]?(?:id|secret))?
        | secret[_-]?access[_-]?key
        | secret[_-]?key
        | client[_-]?secret
        | (?:access|auth|bearer|refresh)[_-]?token
        | password
        | passwd
        | registry[_-]?password
        | authorization
    )
    ["']?
    [ \t]{0,16}[:=][ \t]{0,16}
    (?:
        ["']([^"'\r\n]{8,512})["']
        |
        ((?:Bearer[ \t]+)?[^\s,;\]}\r\n]{8,512})
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

PLACEHOLDER_PREFIXES = (
    b"changeme",
    b"dummy",
    b"empty",
    b"example",
    b"fake",
    b"masked",
    b"none",
    b"not-required",
    b"not_required",
    b"placeholder",
    b"redact",
    b"replace",
    b"sample",
    b"test-",
    b"test_",
    b"unset",
    b"your-",
    b"your_",
)
REFERENCE_PREFIXES = (
    b"${",
    b"{{",
    b"{env:",
    b"{secret:",
    b"<",
    b"config.",
    b"credentials.",
    b"env.",
    b"env:",
    b"getenv",
    b"os.environ",
    b"process.env",
    b"secretref:",
    b"self.",
    b"settings.",
    b"vault:",
)
SAFE_EXACT_VALUES = frozenset(
    {
        b"dummy",
        b"empty",
        b"none",
        b"not-required",
        b"not_required",
        b"null",
        b"placeholder",
        b"redacted",
    }
)

# These are committed, local-only bearer values exposed by two E2 mock APIs.
# OpenCode may preserve them with JSON/SQLite quote escaping in its audit DB.
# Keep this exception exact and benchmark-specific; arbitrary bearer values
# must continue through the credential-assignment heuristic below.
SKILLEVOLBENCH_MOCK_BEARER_TOKENS = frozenset(
    {
        b"token-e2-ls4-t1",
        b"token-e2-ls4-t6",
    }
)


class ScanError(RuntimeError):
    """A safe, non-content-bearing scanner configuration error."""


@dataclass
class Findings:
    """Aggregate findings without retaining or reporting sensitive payloads."""

    category_counts: Counter[str] = field(default_factory=Counter)
    surface_counts: Counter[str] = field(default_factory=Counter)

    def add(self, category: str, surface: str) -> None:
        if category not in ALL_CATEGORIES:
            raise ValueError("unknown finding category")
        if surface not in ALL_SURFACES:
            raise ValueError("unknown finding surface")
        self.category_counts[category] += 1
        self.surface_counts[surface] += 1

    @property
    def count(self) -> int:
        return sum(self.category_counts.values())


@dataclass
class ScanStats:
    bytes_scanned: int = 0
    directories: int = 0
    entries: int = 0
    regular_files: int = 0
    symlinks: int = 0
    skipped_artifacts_json: int = 0
    exact_secret_values_loaded: int = 0
    exact_secret_values_ignored: int = 0
    scan_complete: bool = True


def _is_skillevolbench_mock_bearer_token(value: bytes) -> bool:
    """Recognize only committed E2 mock tokens through audit-text wrappers."""

    # OpenCode's SQLite event text can retain JSON quote escapes plus Markdown
    # code-span and sentence punctuation around an otherwise exact fixture.
    normalized = value.strip().strip(b"\\\"'`.")
    if normalized.lower().startswith(b"bearer "):
        normalized = normalized[7:].strip().strip(b"\\\"'`.")
    return normalized in SKILLEVOLBENCH_MOCK_BEARER_TOKENS


def _is_suspicious_assignment_value(value: bytes) -> bool:
    value = value.strip()
    lowered = value.lower()
    if len(value) < 8 or len(value) > 512:
        return False
    if not value.strip(b"*xX-_.[]"):
        return False
    if _is_skillevolbench_mock_bearer_token(value):
        return False
    normalized = lowered.strip(b"[]()")
    if normalized in SAFE_EXACT_VALUES:
        return False
    if normalized.startswith(PLACEHOLDER_PREFIXES) or lowered.startswith(
        REFERENCE_PREFIXES
    ):
        return False
    if any(
        marker in normalized
        for marker in (b"changeme", b"dummy", b"example", b"placeholder", b"redacted")
    ):
        return False
    if b"://" in lowered:
        return False
    if lowered.endswith((b".api_key", b".password", b".secret", b".token")):
        return False

    # A keyed assignment is not enough on its own. Benchmark task fixtures can
    # legitimately contain short, human-readable fake credentials, while code
    # and type annotations can look like assignments. Require a known token
    # prefix, a plausible bearer token, or a long opaque value. Exact
    # environment-value checks remain available for unusual known credentials.
    bearer_value = value[7:] if lowered.startswith(b"bearer ") else b""
    if bearer_value and len(bearer_value) >= 16 and len(set(bearer_value)) >= 8:
        return True
    if KNOWN_CREDENTIAL_VALUE_RE.fullmatch(value):
        return True
    if len(value) < 32 or len(set(value)) < 10:
        return False
    character_classes = sum(
        (
            any(65 <= byte <= 90 for byte in value),
            any(97 <= byte <= 122 for byte in value),
            any(48 <= byte <= 57 for byte in value),
            any(byte in b"+/=_:.-@" for byte in value),
        )
    )
    return character_classes >= 2


def detect_payload(payload: bytes, exact_secrets: Iterable[bytes]) -> set[str]:
    """Return category names only; never return matched bytes."""

    detected: set[str] = set()
    if PRIVATE_KEY_HEADER_RE.search(payload):
        detected.add("private_key_header")
    if SIGNED_URL_QUERY_RE.search(payload):
        detected.add("signed_url_query")
    if NO_AUTH_SENTINEL_RE.search(payload):
        detected.add("no_auth_sentinel")
    if any(secret in payload for secret in exact_secrets):
        detected.add("exact_secret_value")
    if any(
        _is_suspicious_assignment_value(match.group(1) or match.group(2))
        for match in CREDENTIAL_ASSIGNMENT_RE.finditer(payload)
    ):
        detected.add("credential_assignment")
    return detected


def _load_exact_secrets(
    environment: Mapping[str, str],
) -> tuple[tuple[bytes, ...], int]:
    values: set[bytes] = set()
    ignored = 0
    for name in SECRET_ENV_NAMES:
        raw = environment.get(name)
        if not raw:
            continue
        value = os.fsencode(raw)
        if (
            len(value) < MIN_EXACT_SECRET_BYTES
            or len(value) > MAX_EXACT_SECRET_BYTES
            or value.strip().lower() in SAFE_EXACT_VALUES
        ):
            ignored += 1
            continue
        values.add(value)
    return tuple(sorted(values, key=lambda item: (-len(item), item))), ignored


def _record_payload(
    payload: bytes,
    *,
    exact_secrets: tuple[bytes, ...],
    findings: Findings,
    surface: str,
) -> None:
    for category in detect_payload(payload, exact_secrets):
        findings.add(category, surface)


def _scan_regular_file(
    path: Path,
    *,
    exact_secrets: tuple[bytes, ...],
    findings: Findings,
    stats: ScanStats,
) -> None:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            findings.add("unsupported_object", "filesystem")
            stats.scan_complete = False
            return

        overlap_size = max(
            2048,
            max((len(secret) for secret in exact_secrets), default=0) - 1,
        )
        tail = b""
        detected: set[str] = set()
        while chunk := os.read(descriptor, CHUNK_SIZE):
            stats.bytes_scanned += len(chunk)
            window = tail + chunk
            detected.update(detect_payload(window, exact_secrets))
            tail = window[-overlap_size:]
        for category in detected:
            findings.add(category, "content")
    except OSError:
        findings.add("unreadable_file", "filesystem")
        stats.scan_complete = False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _validate_skipped_transport_file(
    path: Path,
    *,
    findings: Findings,
    stats: ScanStats,
) -> None:
    """Prove the excluded transport object is readable without reading it."""

    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            findings.add("unsupported_object", "filesystem")
            stats.scan_complete = False
    except OSError:
        findings.add("unreadable_file", "filesystem")
        stats.scan_complete = False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _is_outside_root(path: Path, target: str, resolved_root: Path) -> bool:
    try:
        resolved_target = (path.parent / target).resolve(strict=False)
        resolved_target.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError):
        return True
    return False


def _scan_symlink(
    path: Path,
    *,
    resolved_root: Path,
    exact_secrets: tuple[bytes, ...],
    findings: Findings,
    stats: ScanStats,
) -> None:
    try:
        target = os.readlink(path)
    except OSError:
        findings.add("unreadable_symlink", "filesystem")
        stats.scan_complete = False
        return
    _record_payload(
        os.fsencode(target),
        exact_secrets=exact_secrets,
        findings=findings,
        surface="symlink_target",
    )
    if _is_outside_root(path, target, resolved_root):
        findings.add("symlink_escapes_root", "symlink_safety")


def _walk(
    directory: Path,
    *,
    resolved_root: Path,
    exact_secrets: tuple[bytes, ...],
    findings: Findings,
    stats: ScanStats,
) -> None:
    stats.directories += 1
    try:
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda entry: os.fsencode(entry.name))
    except OSError:
        findings.add("unreadable_directory", "filesystem")
        stats.scan_complete = False
        return

    for entry in ordered:
        stats.entries += 1
        path = Path(entry.path)
        _record_payload(
            os.fsencode(entry.name),
            exact_secrets=exact_secrets,
            findings=findings,
            surface="filename",
        )
        try:
            if entry.is_symlink():
                stats.symlinks += 1
                _scan_symlink(
                    path,
                    resolved_root=resolved_root,
                    exact_secrets=exact_secrets,
                    findings=findings,
                    stats=stats,
                )
            elif entry.is_dir(follow_symlinks=False):
                _walk(
                    path,
                    resolved_root=resolved_root,
                    exact_secrets=exact_secrets,
                    findings=findings,
                    stats=stats,
                )
            elif entry.is_file(follow_symlinks=False):
                stats.regular_files += 1
                if entry.name == SKIPPED_TRANSPORT_NAME:
                    stats.skipped_artifacts_json += 1
                    _validate_skipped_transport_file(
                        path,
                        findings=findings,
                        stats=stats,
                    )
                    continue
                _scan_regular_file(
                    path,
                    exact_secrets=exact_secrets,
                    findings=findings,
                    stats=stats,
                )
            else:
                findings.add("unsupported_object", "filesystem")
                stats.scan_complete = False
        except OSError:
            findings.add("unreadable_file", "filesystem")
            stats.scan_complete = False


def _report(findings: Findings, stats: ScanStats) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "clean": stats.scan_complete and findings.count == 0,
        "scan_complete": stats.scan_complete,
        "finding_count": findings.count,
        "category_counts": {
            category: findings.category_counts[category] for category in ALL_CATEGORIES
        },
        "surface_counts": {
            surface: findings.surface_counts[surface] for surface in ALL_SURFACES
        },
        "scan_counts": {
            "bytes_scanned": stats.bytes_scanned,
            "directories": stats.directories,
            "entries": stats.entries,
            "regular_files": stats.regular_files,
            "symlinks": stats.symlinks,
            "skipped_artifacts_json": stats.skipped_artifacts_json,
            "exact_secret_values_loaded": stats.exact_secret_values_loaded,
            "exact_secret_values_ignored": stats.exact_secret_values_ignored,
        },
        "policy": {
            "artifacts_json_content": "skipped_by_default",
            "finding_count_unit": "category_per_object_surface",
            "matched_values_reported": False,
            "paths_reported": False,
            "symlinks_followed": False,
            "writes_performed": False,
        },
    }


def scan_tree(
    root: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Scan ``root`` without writing to it or following any symlink."""

    root = root.expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    try:
        root_stat = root.lstat()
    except OSError as error:
        raise ScanError("scan root is not an accessible directory") from error
    if stat.S_ISLNK(root_stat.st_mode):
        source_environment = environment if environment is not None else os.environ
        secrets, ignored = _load_exact_secrets(source_environment)
        findings = Findings()
        findings.add("root_is_symlink", "filesystem")
        stats = ScanStats(
            exact_secret_values_loaded=len(secrets),
            exact_secret_values_ignored=ignored,
            scan_complete=False,
        )
        return _report(findings, stats)
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ScanError("scan root is not a directory")

    try:
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        raise ScanError("scan root cannot be resolved") from error
    source_environment = environment if environment is not None else os.environ
    secrets, ignored = _load_exact_secrets(source_environment)
    findings = Findings()
    stats = ScanStats(
        exact_secret_values_loaded=len(secrets),
        exact_secret_values_ignored=ignored,
    )
    _record_payload(
        os.fsencode(root.name),
        exact_secrets=secrets,
        findings=findings,
        surface="filename",
    )
    _walk(
        root,
        resolved_root=resolved_root,
        exact_secrets=secrets,
        findings=findings,
        stats=stats,
    )
    return _report(findings, stats)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only safety scan of an exported SkillEvolBench AP evidence "
            "tree. Output is aggregate JSON and never includes matches or contents."
        ),
        epilog=(
            "The scanner never follows symlinks or writes files. It skips "
            "artifacts.json content by default, while still checking its filename "
            "and symlink metadata. Exact values come only from the built-in "
            "sensitive environment-variable allowlist."
        ),
    )
    parser.add_argument("root", type=Path, help="exported AP group or job directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        report = scan_tree(args.root)
    except ScanError:
        report = {
            "schema_version": SCHEMA_VERSION,
            "clean": False,
            "scan_complete": False,
            "finding_count": 1,
            "category_counts": {"scan_configuration_error": 1},
            "surface_counts": {"filesystem": 1},
            "policy": {
                "matched_values_reported": False,
                "paths_reported": False,
                "writes_performed": False,
            },
        }
    except Exception as error:  # Never risk formatting secret-bearing context.
        report = {
            "schema_version": SCHEMA_VERSION,
            "clean": False,
            "scan_complete": False,
            "finding_count": 1,
            "category_counts": {"scanner_internal_error": 1},
            "surface_counts": {"filesystem": 1},
            "error_type": type(error).__name__,
            "policy": {
                "matched_values_reported": False,
                "paths_reported": False,
                "writes_performed": False,
            },
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("clean") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
