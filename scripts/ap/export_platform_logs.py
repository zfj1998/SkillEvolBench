#!/usr/bin/env python3
"""Export complete AP platform logs with safe pagination and verification.

The AP server accepts at most 500 log entries per request.  The stock AP CLI
0.1.16 requests 1,000 entries while exporting logs and can silently leave empty
files.  This helper instead pages every job container until ``next_offset`` is
null, writes mode-0600 files atomically, and repeats the API reads for a terminal
job before publishing a verification manifest.

Usage::

    ap --cluster benchmark-dev job export JOB_ID -o EXPORT_DIR --events
    python scripts/ap/export_platform_logs.py \
        JOB_ID EXPORT_DIR --cluster benchmark-dev

The helper reads only ``job.json`` from an existing AP export.  In particular,
it never opens ``artifacts.json``, whose transport metadata can contain signed
URLs.  Log contents are written to restrictive files but are never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Protocol, Sequence


PAGE_LIMIT = 500
TERMINAL_STATUSES = frozenset({"Succeeded", "Failed", "Cancelled", "Unknown"})
MANIFEST_NAME = "pagination_manifest.json"


class APLogClient(Protocol):
    """Small API surface needed by the exporter (and by its unit tests)."""

    def get_job(self, job_id: str, **kwargs: Any) -> dict[str, Any]: ...

    def get_job_containers(self, job_id: str) -> dict[str, Any]: ...

    def get_job_logs(
        self,
        job_id: str,
        container: str | None = None,
        offset: int | None = 0,
        limit: int | None = PAGE_LIMIT,
    ) -> dict[str, Any]: ...


class ExportError(RuntimeError):
    """A bounded, credential-free export validation error."""


def safe_name(name: str) -> str:
    """Return a filesystem-safe ASCII spelling for a container name."""

    value = "".join(
        character
        if character.isascii()
        and (character.isalnum() or character in ("-", "_", "."))
        else "-"
        for character in name
    ).strip(".")
    return value or "container"


def formatted(entry: Any) -> bytes:
    """Format one AP log entry without ever sending it to stdout/stderr."""

    if isinstance(entry, dict):
        content = str(entry.get("content", ""))
        timestamp = str(entry.get("timestamp", ""))
        text = f"[{timestamp}] {content}" if timestamp else content
    else:
        text = str(entry)
    return (text + "\n").encode("utf-8")


def pages(
    client: APLogClient, job_id: str, container: str
) -> Iterator[tuple[int, list[Any], int | None]]:
    """Yield contiguous pages through the server's terminal null offset."""

    offset = 0
    seen: set[int] = set()
    while True:
        if offset in seen:
            raise ExportError(
                f"pagination loop for container {container!r} at offset {offset}"
            )
        seen.add(offset)
        response = client.get_job_logs(
            job_id=job_id,
            container=container,
            offset=offset,
            limit=PAGE_LIMIT,
        )
        if not isinstance(response, dict):
            raise ExportError(
                f"non-object log response for container {container!r} at offset {offset}"
            )
        values = response.get("logs", [])
        if not isinstance(values, list):
            raise ExportError(
                f"non-list log response for container {container!r} at offset {offset}"
            )
        returned_offset = response.get("offset", offset)
        if returned_offset != offset:
            raise ExportError(
                f"offset disagreement for container {container!r}: "
                f"requested={offset}, returned={returned_offset!r}"
            )
        next_offset = response.get("next_offset")
        if next_offset is not None and (
            not isinstance(next_offset, int) or isinstance(next_offset, bool)
        ):
            raise ExportError(
                f"invalid next_offset for container {container!r} after offset {offset}"
            )
        yield offset, values, next_offset
        if next_offset is None:
            break
        if next_offset <= offset:
            raise ExportError(
                f"non-increasing next_offset for container {container!r} "
                f"after offset {offset}"
            )
        if next_offset != offset + len(values):
            raise ExportError(
                f"non-contiguous page for container {container!r}: "
                f"offset={offset}, count={len(values)}, next_offset={next_offset}"
            )
        offset = next_offset


def _page_record(offset: int, values: Sequence[Any], next_offset: int | None) -> dict[str, Any]:
    return {"offset": offset, "count": len(values), "next_offset": next_offset}


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".part", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        _fsync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _invalidate_manifest(path: Path) -> None:
    """Remove an earlier proof before any newly fetched log can replace it."""

    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        raise ExportError("pagination manifest path is an unexpected directory")
    path.unlink()
    _fsync_directory(path.parent)


def export_container(
    client: APLogClient,
    job_id: str,
    container: str,
    destination: Path,
) -> dict[str, Any]:
    """Atomically write the first complete API pass for one container."""

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
    )
    temporary = Path(temporary_name)
    digest = hashlib.sha256()
    entry_count = 0
    byte_count = 0
    page_records: list[dict[str, Any]] = []
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            for offset, values, next_offset in pages(client, job_id, container):
                page_records.append(_page_record(offset, values, next_offset))
                for value in values:
                    payload = formatted(value)
                    stream.write(payload)
                    digest.update(payload)
                    byte_count += len(payload)
                entry_count += len(values)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
        _fsync_directory(destination.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {
        "file": f"logs/{destination.name}",
        "complete": True,
        "entry_count": entry_count,
        "byte_count": byte_count,
        "sha256": digest.hexdigest(),
        "pages": page_records,
    }


def verify_container(
    client: APLogClient,
    job_id: str,
    container: str,
    destination: Path,
    expected: dict[str, Any],
) -> None:
    """Repeat the API fetch and compare it with the restrictive local file."""

    digest = hashlib.sha256()
    entries = 0
    byte_count = 0
    page_records: list[dict[str, Any]] = []
    for offset, values, next_offset in pages(client, job_id, container):
        page_records.append(_page_record(offset, values, next_offset))
        for value in values:
            payload = formatted(value)
            digest.update(payload)
            byte_count += len(payload)
        entries += len(values)

    observed = {
        "entry_count": entries,
        "byte_count": byte_count,
        "sha256": digest.hexdigest(),
        "pages": page_records,
    }
    for key, value in observed.items():
        if expected.get(key) != value:
            raise ExportError(
                f"second API pass mismatch for container {container!r}: {key}"
            )

    if destination.is_symlink() or not destination.is_file():
        raise ExportError(f"local log is not a regular file for container {container!r}")
    local_digest, local_size = _hash_file(destination)
    if local_digest != expected.get("sha256") or local_size != expected.get("byte_count"):
        raise ExportError(
            f"local hash/size verification mismatch for container {container!r}"
        )


def _terminal_snapshot(
    client: APLogClient, job_id: str, cluster: str
) -> dict[str, Any]:
    response = client.get_job(job_id)
    if not isinstance(response, dict):
        raise ExportError("AP returned a non-object job response")
    if response.get("job_id") != job_id:
        raise ExportError("AP job response does not match the requested job")
    response_cluster = response.get("ap_cluster_name")
    if response_cluster not in (None, cluster):
        raise ExportError("AP job response does not match the requested cluster")
    status = response.get("status")
    if status not in TERMINAL_STATUSES:
        raise ExportError(
            f"job is not terminal (status={status!r}); wait before exporting logs"
        )
    return {
        "job_id": job_id,
        "status": status,
        "attempt": response.get("attempt"),
        "finished_at": response.get("finished_at"),
        "pod_uid": response.get("pod_uid"),
    }


def _containers(client: APLogClient, job_id: str) -> list[str]:
    response = client.get_job_containers(job_id)
    if not isinstance(response, dict):
        raise ExportError("AP returned a non-object container response")
    response_job_id = response.get("job_id")
    if response_job_id not in (None, job_id):
        raise ExportError("AP container response does not match the requested job")
    values = response.get("containers", [])
    if not isinstance(values, list) or not values:
        raise ExportError("AP returned no containers")
    if any(not isinstance(value, str) or not value for value in values):
        raise ExportError("AP returned an invalid container name")
    if len(values) != len(set(values)):
        raise ExportError("AP returned duplicate container names")
    return sorted(values)


def _destination_names(containers: Iterable[str]) -> dict[str, str]:
    containers = list(containers)
    bases = {container: safe_name(container) for container in containers}
    counts = Counter(bases.values())
    names: dict[str, str] = {}
    for container in containers:
        base = bases[container]
        if counts[base] > 1:
            suffix = hashlib.sha256(container.encode("utf-8")).hexdigest()[:12]
            base = f"{base}-{suffix}"
        filename = f"{base}.log"
        if filename in names.values():
            raise ExportError("container names cannot be mapped to unique log files")
        names[container] = filename
    return names


def _validate_local_export(export_dir: Path, job_id: str, cluster: str) -> None:
    if export_dir.is_symlink() or not export_dir.is_dir():
        raise ExportError("export_dir must be an existing, real AP export directory")
    job_path = export_dir / "job.json"
    if job_path.is_symlink() or not job_path.is_file():
        raise ExportError("export_dir is missing a regular job.json")
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ExportError("job.json is not readable valid JSON") from error
    if not isinstance(job, dict) or job.get("job_id") != job_id:
        raise ExportError("job.json job_id does not match the requested job")
    if job.get("ap_cluster_name") not in (None, cluster):
        raise ExportError("job.json cluster does not match --cluster")


def export_job_logs(
    client: APLogClient,
    *,
    job_id: str,
    export_dir: Path,
    cluster: str,
) -> dict[str, Any]:
    """Export and independently verify every container of one terminal job."""

    export_dir = export_dir.expanduser()
    if not export_dir.is_absolute():
        export_dir = Path.cwd() / export_dir
    _validate_local_export(export_dir, job_id, cluster)
    export_dir = export_dir.resolve(strict=True)

    first_job = _terminal_snapshot(client, job_id, cluster)
    first_containers = _containers(client, job_id)
    destinations = _destination_names(first_containers)

    logs_dir = export_dir / "logs"
    if logs_dir.exists() and (logs_dir.is_symlink() or not logs_dir.is_dir()):
        raise ExportError("logs path exists but is not a real directory")
    logs_dir.mkdir(mode=0o700, parents=False, exist_ok=True)
    os.chmod(logs_dir, 0o700)
    manifest_path = logs_dir / MANIFEST_NAME
    _invalidate_manifest(manifest_path)

    records: dict[str, dict[str, Any]] = {}
    for container in first_containers:
        destination = logs_dir / destinations[container]
        records[container] = export_container(
            client, job_id, container, destination
        )

    # A terminal job must still refer to the same attempt and exact container
    # set before the independent read.  This catches a retry/race rather than
    # accidentally certifying logs assembled from two executions.
    second_job = _terminal_snapshot(client, job_id, cluster)
    if second_job != first_job:
        raise ExportError("job identity changed between independent API passes")
    second_containers = _containers(client, job_id)
    if second_containers != first_containers:
        raise ExportError("container set changed between independent API passes")

    for container in second_containers:
        verify_container(
            client,
            job_id,
            container,
            logs_dir / destinations[container],
            records[container],
        )

    manifest = {
        "schema_version": 1,
        "job_id": job_id,
        "cluster": cluster,
        "job_status": first_job["status"],
        "job_attempt": first_job["attempt"],
        "job_finished_at": first_job["finished_at"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "page_limit": PAGE_LIMIT,
        "completion_rule": "next_offset_is_null",
        "terminal_job_verified_by_two_api_reads": True,
        "container_list_verified_by_two_api_reads": True,
        "logs_verified_by_second_api_pass": True,
        "local_hash_and_size_verified": True,
        "container_count": len(second_containers),
        "containers": records,
    }
    _atomic_json(manifest_path, manifest)
    return manifest


def build_client(cluster: str) -> APLogClient:
    """Build a quiet AP client without displaying credentials or headers."""

    try:
        from ap_client.api import APIClient
        from ap_client.config import get_config
    except ImportError as error:  # pragma: no cover - depends on operator env
        raise ExportError("the ap-client package is required") from error

    config = get_config(cluster=cluster, verbose=False)
    config.verbose = False
    return APIClient(config)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export every platform-log container with AP's 500-entry page limit "
            "and verify a terminal job with a second independent API pass."
        ),
        epilog=(
            "First export the AP job without the stock --logs option. This tool "
            "reads job.json only; it never opens artifacts.json or prints log contents."
        ),
    )
    parser.add_argument("job_id", help="terminal AP job ID")
    parser.add_argument("export_dir", type=Path, help="existing AP job export directory")
    parser.add_argument("--cluster", required=True, help="AP cluster name")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        manifest = export_job_logs(
            build_client(args.cluster),
            job_id=args.job_id,
            export_dir=args.export_dir,
            cluster=args.cluster,
        )
    except ExportError as error:
        parser.exit(1, f"error: {error}\n")
    except Exception as error:  # Do not risk echoing request headers or secrets.
        parser.exit(1, f"error: AP request failed ({type(error).__name__})\n")

    print(
        f"job={args.job_id} status={manifest['job_status']} "
        f"containers={manifest['container_count']} page_limit={PAGE_LIMIT}"
    )
    for container, record in manifest["containers"].items():
        print(
            f"{container}: entries={record['entry_count']} "
            f"pages={len(record['pages'])} bytes={record['byte_count']} "
            f"sha256={record['sha256'][:16]}... complete=true verified=true"
        )
    print(f"manifest={args.export_dir.resolve() / 'logs' / MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
