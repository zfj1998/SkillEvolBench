"""Build a deterministic Agent Platform dataset bundle from a Git revision.

The AP dataset has six logical instances (``E1`` ... ``E6``).  Each asset is a
complete archive of the selected repository revision, rather than a partial
environment tree, because SkillEvolBench's preflight and registry validation
intentionally cover all 30 families and 180 tasks.

Output layout (``--output-root`` is the dataset-name directory)::

    <output-root>/
      v1@6/E1.json
      ...
      v1@6/E6.json
      v1@6-assets/E1/content.tgz
      ...
      v1@6-assets/E6/content.tgz
      package-manifest.json

Each outer ``content.tgz`` contains ``source.tar.gz``, ``episode.json``, and
``source-manifest.json``.  ``source.tar.gz`` is the complete output of
``git archive <revision>`` plus a deterministic ``.skillevolbench-revision``
file at the repository root.  This keeps untracked credentials, local
environments, and run artifacts out of AP while matching the Agent-Hub runner's
two-layer extraction contract.  Tar ownership, modes, ordering, and timestamps
are normalized, and gzip uses a zero timestamp, so rebuilding the same revision
produces byte-identical files.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import stat
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

ENVIRONMENT_IDS = tuple(f"E{i}" for i in range(1, 7))
DEFAULT_DATASET = "skillevolbench/skillevolbench"
DEFAULT_SPLIT = "v1@6"
ARCHIVE_ROOT = "skillevolbench"
REVISION_FILE = ".skillevolbench-revision"
SAFE_ENV_SUFFIXES = {".dist", ".example", ".sample", ".template"}
SENSITIVE_BASENAMES = {
    ".gemini_api_key",
    ".git-credentials",
    ".harbor-agents.env",
    ".netrc",
    ".npmrc",
    ".ossutilconfig",
    ".pypirc",
    "credentials.json",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "service-account.json",
    "service_account.json",
}
SENSITIVE_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
# This is an intentional synthetic task fixture, not an operator credential.
# Pinning its content hash means an accidental replacement still fails closed.
SAFE_CREDENTIAL_FIXTURES = {
    "benchmark/tasks/auth-list-detail-save-4-step/environment/credentials.json": (
        "b7ffe049df6ac7803a2e3d0a0f8ed706f697f683107a4db01ff8a221bed95369"
    ),
}


def _run_git(repo_root: Path, *args: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=text,
    )
    if completed.returncode != 0:
        stderr = completed.stderr if text else completed.stderr.decode(errors="replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return completed.stdout


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _gzip_bytes(data: bytes) -> bytes:
    """Return a gzip member without a wall-clock timestamp or filename."""
    compressed = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=compressed,
        mtime=0,
    ) as archive:
        archive.write(data)
    return compressed.getvalue()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assert_clean(repo_root: Path) -> None:
    """Reject tracked/index changes; untracked files never enter git archive."""
    worktree_dirty = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--quiet"], check=False
    ).returncode
    index_dirty = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--quiet"],
        check=False,
    ).returncode
    if worktree_dirty or index_dirty:
        raise RuntimeError(
            "tracked or staged changes are present; commit them before packaging "
            "so benchmark_revision identifies the exact AP payload (or pass "
            "--allow-dirty to deliberately archive the selected commit only)"
        )


def _git_metadata(repo_root: Path, revision: str) -> tuple[str, int, str]:
    resolved = str(_run_git(repo_root, "rev-parse", f"{revision}^{{commit}}")).strip()
    timestamp_raw = str(
        _run_git(repo_root, "show", "-s", "--format=%ct", resolved)
    ).strip()
    commit_epoch = int(timestamp_raw)
    commit_iso = datetime.fromtimestamp(commit_epoch, tz=timezone.utc).isoformat()
    return resolved, commit_epoch, commit_iso


def _git_archive(repo_root: Path, revision: str) -> bytes:
    return bytes(
        _run_git(
            repo_root,
            "archive",
            "--format=tar",
            f"--prefix={ARCHIVE_ROOT}/",
            f"--add-virtual-file={ARCHIVE_ROOT}/{REVISION_FILE}:{revision}\n",
            revision,
            text=False,
        )
    )


def _assert_no_sensitive_files(source_tar: bytes) -> None:
    """Fail closed on credential-shaped tracked paths or private keys."""
    findings: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(source_tar), mode="r:") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            path = PurePosixPath(member.name)
            basename = path.name.lower()
            suffix = path.suffix.lower()
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            extracted = archive.extractfile(member)
            contents = extracted.read() if extracted is not None else b""
            is_env = basename == ".env" or (
                basename.startswith(".env.") and suffix not in SAFE_ENV_SUFFIXES
            )
            is_config_secret = len(path.parts) >= 2 and tuple(
                part.lower() for part in path.parts[-2:]
            ) in {
                (".aws", "credentials"),
                (".docker", "config.json"),
                (".kube", "config"),
            }
            if (
                is_env
                or is_config_secret
                or basename in SENSITIVE_BASENAMES
                or suffix in SENSITIVE_SUFFIXES
            ):
                expected_hash = SAFE_CREDENTIAL_FIXTURES.get(relative)
                if expected_hash == _sha256_bytes(contents):
                    continue
                findings.append(member.name)
                continue

            # Assemble markers at runtime so this scanner's own source does
            # not contain (and therefore self-match) a complete private-key
            # header when the repository is packaged.
            private_key_markers = tuple(
                b"-----BEGIN " + key_type + b"PRIVATE KEY-----"
                for key_type in (b"", b"RSA ", b"EC ", b"OPENSSH ")
            )
            if any(marker in contents for marker in private_key_markers):
                findings.append(member.name)

    if findings:
        rendered = ", ".join(sorted(findings)[:10])
        remainder = len(findings) - 10
        suffix = f" (+{remainder} more)" if remainder > 0 else ""
        raise RuntimeError(
            "refusing to package tracked credential-shaped files: "
            f"{rendered}{suffix}"
        )


def _normalize_tarinfo(info: tarfile.TarInfo, *, mtime: int) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = mtime
    info.pax_headers = {}
    if info.isdir():
        info.mode = 0o755
    elif info.issym():
        info.mode = 0o777
    elif info.isfile():
        info.mode = 0o755 if info.mode & stat.S_IXUSR else 0o644
    return info


def _iter_paths(root: Path) -> Iterable[Path]:
    """Yield directories and files in stable POSIX-path order."""
    return sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())


def _write_deterministic_tgz(
    source_root: Path, destination: Path, *, mtime: int
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                for path in _iter_paths(source_root):
                    relative = path.relative_to(source_root).as_posix()
                    info = _normalize_tarinfo(
                        archive.gettarinfo(str(path), arcname=relative),
                        mtime=mtime,
                    )
                    if info.isfile():
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)
                    else:
                        archive.addfile(info)


def _episode_metadata(
    *,
    environment_id: str,
    dataset: str,
    split: str,
    revision: str,
    commit_time: str,
    source_archive_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "instance_id": environment_id,
        "environment_id": environment_id,
        "dataset": dataset,
        "split": split,
        "benchmark_revision": revision,
        "benchmark_commit_time": commit_time,
        "source_archive_sha256": source_archive_sha256,
        "family_count": 5,
        "primary_task_count": 30,
        "roles": ["T1", "T2", "T3", "T4", "T5", "T6"],
        "scoreable_unit": "complete_environment_episode",
    }


def build_dataset(
    *,
    repo_root: Path,
    output_root: Path,
    revision: str = "HEAD",
    dataset: str = DEFAULT_DATASET,
    split: str = DEFAULT_SPLIT,
    allow_dirty: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create the six AP instance JSONs and deterministic asset archives."""
    repo_root = repo_root.resolve()
    if output_root.is_symlink():
        raise RuntimeError(
            f"refusing to replace a symlinked output path: {output_root}"
        )
    output_root = output_root.resolve()
    try:
        git_root = Path(
            str(_run_git(repo_root, "rev-parse", "--show-toplevel")).strip()
        ).resolve()
    except RuntimeError as exc:
        raise RuntimeError(f"not a Git worktree: {repo_root}") from exc
    if git_root != repo_root:
        raise RuntimeError(
            f"--repo-root must be the Git worktree root ({git_root}), got {repo_root}"
        )
    if output_root == repo_root or output_root in repo_root.parents:
        raise RuntimeError(
            f"refusing to replace output directory that contains the repository: {output_root}"
        )
    if output_root.exists() and not overwrite:
        raise RuntimeError(
            f"output directory already exists: {output_root} "
            "(pass --overwrite to replace it)"
        )
    if not allow_dirty:
        _assert_clean(repo_root)

    resolved, commit_epoch, commit_iso = _git_metadata(repo_root, revision)
    source_tar = _git_archive(repo_root, resolved)
    _assert_no_sensitive_files(source_tar)
    source_git_tar_sha256 = _sha256_bytes(source_tar)
    source_archive = _gzip_bytes(source_tar)
    source_archive_sha256 = _sha256_bytes(source_archive)

    if output_root.exists():
        shutil.rmtree(output_root)
    json_root = output_root / split
    assets_root = output_root / f"{split}-assets"
    json_root.mkdir(parents=True)
    assets_root.mkdir(parents=True)

    files: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="sevb-ap-package-") as temporary:
        temporary_root = Path(temporary)

        for environment_id in ENVIRONMENT_IDS:
            episode = _episode_metadata(
                environment_id=environment_id,
                dataset=dataset,
                split=split,
                revision=resolved,
                commit_time=commit_iso,
                source_archive_sha256=source_archive_sha256,
            )

            episode_tree = temporary_root / f"episode-{environment_id}"
            episode_tree.mkdir()
            (episode_tree / "source.tar.gz").write_bytes(source_archive)
            _write_json(episode_tree / "episode.json", episode)
            _write_json(
                episode_tree / "source-manifest.json",
                {
                    "schema_version": "1.0",
                    "benchmark_revision": resolved,
                    "benchmark_commit_time": commit_iso,
                    "source_archive_path": "source.tar.gz",
                    "source_archive_sha256": source_archive_sha256,
                    "source_archive_size_bytes": len(source_archive),
                    "git_archive_tar_sha256": source_git_tar_sha256,
                    "archive_root": f"{ARCHIVE_ROOT}/",
                    "revision_file": f"{ARCHIVE_ROOT}/{REVISION_FILE}",
                    "source": "git archive --add-virtual-file",
                },
            )

            content_path = assets_root / environment_id / "content.tgz"
            _write_deterministic_tgz(
                episode_tree,
                content_path,
                mtime=commit_epoch,
            )
            content_sha256 = _sha256_file(content_path)
            content_rel = content_path.relative_to(output_root).as_posix()
            episode["content_sha256"] = content_sha256
            episode["content_size_bytes"] = content_path.stat().st_size
            episode["asset_relative_path"] = content_rel

            instance_path = json_root / f"{environment_id}.json"
            _write_json(instance_path, episode)
            instance_rel = instance_path.relative_to(output_root).as_posix()
            files[environment_id] = {
                "instance_json": instance_rel,
                "instance_json_sha256": _sha256_file(instance_path),
                "content_tgz": content_rel,
                "content_tgz_sha256": content_sha256,
                "content_tgz_size_bytes": content_path.stat().st_size,
            }
            shutil.rmtree(episode_tree)

    manifest = {
        "schema_version": "1.0",
        "dataset": dataset,
        "split": split,
        "dataset_version_path": f"{dataset}/{split}",
        "benchmark_revision": resolved,
        "benchmark_commit_time": commit_iso,
        "source_archive_sha256": source_archive_sha256,
        "source_archive_size_bytes": len(source_archive),
        "git_archive_tar_sha256": source_git_tar_sha256,
        "revision_file": f"{ARCHIVE_ROOT}/{REVISION_FILE}",
        "environment_ids": list(ENVIRONMENT_IDS),
        "files": files,
    }
    _write_json(output_root / "package-manifest.json", manifest)
    return manifest


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="archive the selected commit even when tracked local changes exist",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing output directory",
    )
    args = parser.parse_args(argv)

    manifest = build_dataset(
        repo_root=args.repo_root,
        output_root=args.output_root,
        revision=args.revision,
        dataset=args.dataset,
        split=args.split,
        allow_dirty=args.allow_dirty,
        overwrite=args.overwrite,
    )
    print(f"Built {manifest['dataset_version_path']}")
    print(f"Revision: {manifest['benchmark_revision']}")
    print(f"Output: {args.output_root.resolve()}")
    for environment_id in ENVIRONMENT_IDS:
        item = manifest["files"][environment_id]
        print(
            f"  {environment_id}: {item['content_tgz']} "
            f"sha256={item['content_tgz_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
