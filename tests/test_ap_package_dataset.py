from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

from scripts.ap.package_dataset import ENVIRONMENT_IDS, build_dataset


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.stdout.strip()


def _make_repository(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "benchmark@example.com")
    _git(repo, "config", "user.name", "Benchmark Test")

    (repo / "README.md").write_text("committed source\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.0.0"\n', encoding="utf-8"
    )
    (repo / "nested").mkdir()
    (repo / "nested" / "data.txt").write_text("task asset\n", encoding="utf-8")
    script = repo / "run.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    (repo / ".env").write_text("MODEL_API_KEY=must-not-leak\n", encoding="utf-8")

    _git(repo, "add", "README.md", "pyproject.toml", "nested/data.txt", "run.sh")
    commit_env = dict(os.environ)
    commit_env.update(
        {
            "GIT_AUTHOR_DATE": "2024-01-02T03:04:05+00:00",
            "GIT_COMMITTER_DATE": "2024-01-02T03:04:05+00:00",
        }
    )
    _git(repo, "commit", "-m", "fixture", env=commit_env)
    return repo, _git(repo, "rev-parse", "HEAD")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _outer_members(content_tgz: Path) -> tuple[dict[str, bytes], list[str]]:
    with tarfile.open(content_tgz, mode="r:gz") as archive:
        names = archive.getnames()
        files = {
            name: archive.extractfile(name).read()  # type: ignore[union-attr]
            for name in names
            if archive.getmember(name).isfile()
        }
    return files, names


def test_package_is_deterministic_complete_and_secret_free(tmp_path: Path) -> None:
    repo, revision = _make_repository(tmp_path)
    output_one = tmp_path / "output-one"
    output_two = tmp_path / "output-two"

    first = build_dataset(repo_root=repo, output_root=output_one)
    second = build_dataset(repo_root=repo, output_root=output_two)

    assert first == second
    assert first["benchmark_revision"] == revision
    assert first["revision_file"] == "skillevolbench/.skillevolbench-revision"
    assert first["environment_ids"] == list(ENVIRONMENT_IDS)
    assert (output_one / "package-manifest.json").read_bytes() == (
        output_two / "package-manifest.json"
    ).read_bytes()

    content_hashes: set[str] = set()
    for environment_id in ENVIRONMENT_IDS:
        instance_rel = Path("v1@5") / f"{environment_id}.json"
        content_rel = Path("v1@5-assets") / environment_id / "content.tgz"
        instance_path = output_one / instance_rel
        content_path = output_one / content_rel
        assert instance_path.is_file()
        assert content_path.is_file()
        assert content_path.read_bytes() == (output_two / content_rel).read_bytes()

        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        assert instance["instance_id"] == environment_id
        assert instance["environment_id"] == environment_id
        assert instance["benchmark_revision"] == revision
        assert instance["asset_relative_path"] == content_rel.as_posix()
        assert instance["content_sha256"] == _sha256(content_path)
        assert (
            first["files"][environment_id]["instance_json"] == instance_rel.as_posix()
        )
        assert first["files"][environment_id]["content_tgz"] == content_rel.as_posix()

        outer_files, outer_names = _outer_members(content_path)
        assert outer_names == ["episode.json", "source-manifest.json", "source.tar.gz"]
        episode = json.loads(outer_files["episode.json"])
        source_manifest = json.loads(outer_files["source-manifest.json"])
        assert episode["environment_id"] == environment_id
        assert source_manifest["benchmark_revision"] == revision
        assert source_manifest["revision_file"] == (
            "skillevolbench/.skillevolbench-revision"
        )
        assert (
            source_manifest["source_archive_sha256"]
            == hashlib.sha256(outer_files["source.tar.gz"]).hexdigest()
        )

        with tarfile.open(
            fileobj=io.BytesIO(outer_files["source.tar.gz"]), mode="r:gz"
        ) as source:
            source_names = source.getnames()
            assert "skillevolbench/README.md" in source_names
            assert "skillevolbench/pyproject.toml" in source_names
            assert "skillevolbench/nested/data.txt" in source_names
            assert "skillevolbench/run.sh" in source_names
            assert "skillevolbench/.skillevolbench-revision" in source_names
            assert "skillevolbench/.env" not in source_names
            assert not any("/.git/" in name for name in source_names)
            revision_file = source.extractfile(
                "skillevolbench/.skillevolbench-revision"
            )
            assert revision_file is not None
            assert revision_file.read().decode() == f"{revision}\n"
            assert source.getmember("skillevolbench/run.sh").mode & 0o111

        content_hashes.add(_sha256(content_path))

    # Episode metadata makes each environment asset intentionally distinct.
    assert len(content_hashes) == len(ENVIRONMENT_IDS)


def test_dirty_tracked_files_are_rejected_unless_explicitly_allowed(
    tmp_path: Path,
) -> None:
    repo, _revision = _make_repository(tmp_path)
    (repo / "README.md").write_text("dirty worktree\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="tracked or staged changes"):
        build_dataset(repo_root=repo, output_root=tmp_path / "rejected")

    build_dataset(
        repo_root=repo,
        output_root=tmp_path / "allowed",
        allow_dirty=True,
    )
    outer_files, _ = _outer_members(
        tmp_path / "allowed" / "v1@5-assets" / "E1" / "content.tgz"
    )
    with tarfile.open(
        fileobj=io.BytesIO(outer_files["source.tar.gz"]), mode="r:gz"
    ) as source:
        readme = source.extractfile("skillevolbench/README.md")
        assert readme is not None
        assert readme.read() == b"committed source\n"


def test_refuses_output_directory_that_contains_repository(tmp_path: Path) -> None:
    repo, _revision = _make_repository(tmp_path)

    with pytest.raises(RuntimeError, match="contains the repository"):
        build_dataset(repo_root=repo, output_root=tmp_path)


def test_refuses_tracked_credential_shaped_files(tmp_path: Path) -> None:
    repo, _revision = _make_repository(tmp_path)
    _git(repo, "add", "--force", ".env")
    _git(repo, "commit", "-m", "accidentally tracked credential")

    with pytest.raises(RuntimeError, match="credential-shaped files"):
        build_dataset(repo_root=repo, output_root=tmp_path / "rejected-secret")


def test_existing_output_requires_explicit_overwrite(tmp_path: Path) -> None:
    repo, _revision = _make_repository(tmp_path)
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("do not delete implicitly\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists"):
        build_dataset(repo_root=repo, output_root=output)
    assert sentinel.is_file()

    build_dataset(repo_root=repo, output_root=output, overwrite=True)
    assert not sentinel.exists()
    assert (output / "package-manifest.json").is_file()
