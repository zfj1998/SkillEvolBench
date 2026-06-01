"""VerifierAdapter -- read the verifier-output contract into a TrialOutcome.

Reads the four verifier-output files documented in
``docs/PART1_STATIC_ASSETS.md`` §1.6:

* ``reward.txt``           -- canonical Harbor reward (required)
* ``score_report.json``    -- rubric dimensions
* ``outcome_report.json``  -- per-test pass/fail (outcome group)
* ``process_report.json``  -- per-test pass/fail (process group)

This intentionally does NOT read ``ctrf.json`` (which Harbor does not
generate; the Engineering Design recommended it but our 180 task ``test.sh``
files emit the richer outcome/process split instead).

Returns a fully-populated :class:`TrialOutcome` Pydantic model; missing
optional files degrade gracefully (T5 ``trap_resistance`` analysis just
loses the per-test detail for that task).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from skillevolbench.schemas import (
    FailedTest,
    RubricDimension,
    TrialOutcome,
)


_LOG = logging.getLogger(__name__)


class VerifierAdapter:
    """Parse Harbor verifier outputs into a :class:`TrialOutcome`."""

    def parse(self, trial_result: Any) -> TrialOutcome:
        """Adapter from Harbor ``TrialResult`` -> our :class:`TrialOutcome`.

        The ``trial_result`` is duck-typed -- we read whatever attributes
        Harbor exposes. Robust to the SDK changing names by falling back to
        the on-disk verifier files.
        """
        log_dir = self._resolve_log_dir(trial_result)
        task_id = self._resolve_task_id(trial_result)
        return self._parse_from_dir(log_dir=log_dir, task_id=task_id,
                                    trial_result=trial_result)

    def parse_from_dir(
        self,
        *,
        log_dir: Path,
        task_id: str,
    ) -> TrialOutcome:
        """Pure-disk variant for unit tests / replay analysis."""
        return self._parse_from_dir(log_dir=log_dir, task_id=task_id,
                                    trial_result=None)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _parse_from_dir(
        self,
        *,
        log_dir: Path,
        task_id: str,
        trial_result: Optional[Any],
    ) -> TrialOutcome:
        log_dir = Path(log_dir)

        # 1. reward.txt -- canonical Harbor signal (required by contract)
        reward = self._read_reward(log_dir / "reward.txt", trial_result)

        # 2. score_report.json -- rubric dimensions + max_score
        score_path = log_dir / "score_report.json"
        score_report = self._read_json(score_path)
        max_score = float(score_report.get("max_score", 100.0)) or 100.0
        total_score = float(score_report.get("total_score", reward * max_score))
        rubric_dimensions = self._parse_rubric_dimensions(score_report)

        # 3. outcome_report.json + process_report.json
        outcome_report = self._read_json(log_dir / "outcome_report.json")
        process_report = self._read_json(log_dir / "process_report.json")
        outcome_passed = self._all_groups_pass(outcome_report)
        process_passed = self._all_groups_pass(process_report)

        # 4. failed tests (from outcome + process, including any pytest json fallback)
        failed_tests: list[FailedTest] = []
        failed_tests.extend(self._failed_from_script_report(outcome_report, "outcome"))
        failed_tests.extend(self._failed_from_script_report(process_report, "process"))
        # Harbor pytest fallback: outcome.json / process.json (in older runs).
        for path, group in [
            (log_dir / "outcome.json", "outcome"),
            (log_dir / "process.json", "process"),
        ]:
            failed_tests.extend(self._failed_from_pytest_report(path, group))

        # 5. trajectory.json path (Harbor writes this under /logs/agent/)
        trajectory_path = self._resolve_trajectory_path(log_dir, trial_result)

        # 6. trial_dir (Harbor's directory for this trial, if available)
        trial_dir = self._resolve_trial_dir(log_dir, trial_result)

        # 7. agent-side token + USD from trial_result.context (Harbor
        # populates this from trajectory.json:final_metrics for ATIF-aware
        # agent CLIs -- claude-code, kimi-cli at minimum). When absent the
        # fields stay 0 / "" and CostReport will say "unknown".
        n_input, n_output, n_cache, cost_usd, cost_source = (
            self._parse_agent_cost(trial_result, model_name=task_id)
        )

        return TrialOutcome(
            task_id=task_id,
            verifier_passed=(reward >= 1.0),
            reward=reward,
            max_score=max_score,
            normalized_score=(total_score / max_score) if max_score else 0.0,
            outcome_passed=outcome_passed,
            process_passed=process_passed,
            failed_tests=failed_tests,
            failure_summary=self._summarize_failures(failed_tests),
            rubric_dimensions=rubric_dimensions,
            trial_dir=trial_dir,
            trajectory_path=trajectory_path,
            n_input_tokens=n_input,
            n_output_tokens=n_output,
            n_cache_tokens=n_cache,
            cost_usd=cost_usd,
            cost_source=cost_source,
        )

    @staticmethod
    def _parse_agent_cost(
        trial_result: Any, *, model_name: str = "",
    ) -> tuple[int, int, int, float, str]:
        """Pull token + cost from Harbor's TrialResult.

        Harbor 0.6+ exposes the agent's token / cost telemetry on
        ``TrialResult.agent_result`` (an ``AgentContext`` Pydantic model).
        Older code looked for a non-existent ``trial_result.context``
        attribute and silently returned all zeros, so every replay record
        had ``n_*_tokens=0`` / ``cost_usd=0.0`` regardless of what the
        agent actually consumed.

        Returns (n_input, n_output, n_cache, cost_usd, cost_source).
        Falls back to all-zero / "" when agent_result is absent or empty.
        Computes cost from tokens via the price table when the agent
        didn't self-report ``cost_usd``.
        """
        if trial_result is None:
            return (0, 0, 0, 0.0, "")
        # Harbor 0.6+ canonical name; keep ``context`` as a back-compat
        # alias so older Harbor releases / our test fixtures still work.
        ctx = getattr(trial_result, "agent_result", None)
        if ctx is None:
            ctx = getattr(trial_result, "context", None)
        if ctx is None:
            return (0, 0, 0, 0.0, "")
        n_input  = int(getattr(ctx, "n_input_tokens", 0) or 0)
        n_output = int(getattr(ctx, "n_output_tokens", 0) or 0)
        n_cache  = int(getattr(ctx, "n_cache_tokens", 0) or 0)
        reported = getattr(ctx, "cost_usd", None)
        if reported is not None and reported > 0:
            return (n_input, n_output, n_cache,
                    float(reported), "agent_reported")

        # Compute from tokens + price table.
        if n_input + n_output + n_cache == 0:
            return (0, 0, 0, 0.0, "")
        # Resolve the agent's model from trial_result.config (Harbor
        # passes this through). Fall back to model_name arg if absent.
        agent_model = ""
        cfg = getattr(trial_result, "config", None)
        if cfg is not None:
            agents = getattr(cfg, "agents", None) or []
            if agents:
                agent_model = getattr(agents[0], "model_name", "") or ""
        from skillevolbench.metrics.cost import compute_cost_usd
        usd = compute_cost_usd(agent_model, n_input, n_output, n_cache)
        if usd is None:
            return (n_input, n_output, n_cache, 0.0, "unknown")
        return (n_input, n_output, n_cache, usd, "computed_from_tokens")

    @staticmethod
    def _read_reward(path: Path, trial_result: Any) -> float:
        if path.exists():
            try:
                return float(path.read_text().strip())
            except (ValueError, OSError):
                _LOG.warning("VerifierAdapter: bad reward.txt at %s", path)
        # Fallback to Harbor's TrialResult.verifier_result.rewards if present.
        if trial_result is not None:
            try:
                rewards = trial_result.verifier_result.rewards  # type: ignore[union-attr]
                if rewards:
                    return float(next(iter(rewards.values())))
            except AttributeError:
                pass
        return 0.0

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            _LOG.warning("VerifierAdapter: malformed json at %s", path)
            return {}

    @staticmethod
    def _parse_rubric_dimensions(report: dict[str, Any]) -> list[RubricDimension]:
        dims = report.get("dimensions", []) or []
        out: list[RubricDimension] = []
        for d in dims:
            try:
                out.append(RubricDimension.model_validate(d))
            except Exception:
                continue
        return out

    @staticmethod
    def _all_groups_pass(report: dict[str, Any]) -> Optional[bool]:
        """For *_report.json, every present group's passed == total -> True."""
        if not report:
            return None
        relevant = []
        for key in ("public", "hidden"):
            grp = report.get(key)
            if isinstance(grp, dict) and grp.get("total", 0) > 0:
                relevant.append(grp)
        if not relevant:
            return None
        return all(g.get("passed", 0) == g.get("total", 0) for g in relevant)

    @staticmethod
    def _failed_from_script_report(
        report: dict[str, Any], group: str
    ) -> list[FailedTest]:
        """Extract failed tests from outcome_report.json / process_report.json."""
        failed: list[FailedTest] = []
        for section in ("public", "hidden"):
            sec = report.get(section)
            if not isinstance(sec, dict):
                continue
            for r in sec.get("results", []) or []:
                if not r.get("passed", True):
                    failed.append(
                        FailedTest(
                            name=r.get("name", "?"),
                            message=str(r.get("error") or r.get("detail") or ""),
                            group=group,
                        )
                    )
        return failed

    @staticmethod
    def _failed_from_pytest_report(path: Path, group: str) -> list[FailedTest]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return []
        out: list[FailedTest] = []
        for t in data.get("tests", []) or []:
            if t.get("outcome") == "passed":
                continue
            call = t.get("call") or {}
            out.append(
                FailedTest(
                    name=t.get("nodeid", "?"),
                    message=str(call.get("longrepr") or "")[:500],
                    group=group,
                )
            )
        return out

    @staticmethod
    def _summarize_failures(failed: list[FailedTest]) -> str:
        if not failed:
            return ""
        return "\n".join(f"- [{t.group}] {t.name}: {t.message}" for t in failed)

    # ------------------------------------------------------------------
    # Trial-dir / trajectory resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _path_from_uri_or_str(value: Any) -> Path:
        """Normalize a Harbor trial-dir reference into a real filesystem Path.

        Harbor passes ``trial_uri`` as a ``file:///abs/path`` URI (string or
        ``Path``-stringified). Naively wrapping it with ``Path(str(v))``
        yields ``PosixPath('file:/abs/path')`` (pathlib collapses ``//``)
        which never resolves -- this is the bug that caused every replay
        record to store ``trajectory_compact.text == "(trajectory
        unavailable)"`` and ``trial_dir == "file:/home/..."``.

        Strip the ``file://`` prefix here so callers always get a path
        ``.exists()`` can answer truthfully.
        """
        s = str(value)
        if s.startswith("file://"):
            s = s[len("file://"):]
        return Path(s)

    @staticmethod
    def _resolve_log_dir(trial_result: Any) -> Path:
        """Compute the verifier log dir for this trial."""
        # Harbor convention: <trial_dir>/verifier/
        for attr in ("trial_uri", "trial_dir", "trial_path"):
            v = getattr(trial_result, attr, None)
            if v is not None:
                return VerifierAdapter._path_from_uri_or_str(v) / "verifier"
        raise ValueError(
            "VerifierAdapter: cannot resolve trial directory from trial_result"
        )

    @staticmethod
    def _resolve_trial_dir(log_dir: Path, trial_result: Any) -> Optional[Path]:
        """Trial dir is the parent of the verifier subdir."""
        if log_dir.name == "verifier":
            return log_dir.parent
        return None

    @staticmethod
    def _resolve_trajectory_path(
        log_dir: Path, trial_result: Any
    ) -> Optional[Path]:
        """Locate the trial's trajectory file under ``<trial_dir>/agent/``.

        Each agent CLI writes a slightly different filename:
          * claude-code / codex / kimi-cli  -> ``trajectory.json`` (ATIF)
          * gemini-cli                     -> ``gemini-cli.trajectory.json``
                                              (or ``.jsonl`` if conversion
                                              failed; agents_port/preinstalled.py
                                              copies one of them into place
                                              on shutdown)
          * openclaw                       -> ``openclaw-result.json`` / ``.txt``

        Returns the first existing candidate; falls back to a glob over
        ``*.trajectory.json*`` so future agent additions don't silently
        produce ``(trajectory unavailable)``.
        """
        if log_dir.name != "verifier":
            return None
        trial_dir = log_dir.parent
        # Harbor 0.6+ archives JobConfig.artifacts paths to
        # ``<trial_dir>/artifacts/<basename>`` (verified empirically on a real
        # claude-opus-4.5 trial: trajectory.json sits at
        # ``<trial>/artifacts/trajectory.json``, NOT ``<trial>/agent/``).
        # Older Harbor versions used ``<trial_dir>/agent/`` instead. We probe
        # both, ``artifacts/`` first since it's the current convention.
        # Each agent CLI writes a different filename: ATIF-aware CLIs
        # (claude-code, kimi-cli) emit ``trajectory.json``; gemini-cli is
        # post-processed into ``gemini-cli.trajectory.{json,jsonl}`` by
        # ``agents_port/preinstalled.py``; codex/oracle write raw stdout.
        for agent_dir in (trial_dir / "artifacts", trial_dir / "agent"):
            if not agent_dir.exists():
                continue
            candidates = [
                # 1. ATIF canonical
                agent_dir / "trajectory.json",
                # 2. gemini-cli (post-processed jsonl preferred since
                #    preinstalled.py's converter occasionally drops events)
                agent_dir / "gemini-cli.trajectory.json",
                agent_dir / "gemini-cli.trajectory.jsonl",
                # 3. openclaw
                agent_dir / "openclaw-result.json",
                agent_dir / "openclaw.txt",
                # 4. Per-CLI raw text logs (no ATIF: tee'd stdout).
                #    TrajectoryCompactor's plain-text branch handles these.
                agent_dir / "oracle.txt",
                agent_dir / "claude-code.txt",
                agent_dir / "kimi-cli.txt",
                agent_dir / "codex.txt",
                agent_dir / "gemini-cli.txt",
            ]
            for c in candidates:
                if c.exists():
                    return c
            # Glob fallbacks within this dir (ordered by compaction quality):
            for c in sorted(agent_dir.glob("*.trajectory.json*")):
                return c
            for c in sorted(agent_dir.glob("*.json")):
                return c
            for c in sorted(agent_dir.glob("*.txt")):
                return c

        # Diagnostic: log what each candidate dir actually contains so the
        # next failing trial leaves a breadcrumb in stdout.
        for d in (trial_dir / "artifacts", trial_dir / "agent"):
            if d.exists():
                _LOG.warning(
                    "VerifierAdapter: no trajectory file found in %s; "
                    "directory contains: %s",
                    d, sorted(p.name for p in d.iterdir()),
                )
            else:
                _LOG.warning(
                    "VerifierAdapter: candidate dir missing: %s", d,
                )
        return None

    @staticmethod
    def _resolve_task_id(trial_result: Any) -> str:
        """Best-effort task-id from ``trial_result``.

        Harbor 0.5 had ``trial_result.task_id`` as a plain ``str``. Harbor
        0.6+ moved it to a typed Pydantic model (``LocalTaskId`` /
        ``GitTaskId`` / ``PackageTaskId``) whose ``str()`` returns the
        BaseModel repr ``"path=PosixPath('...')"``, not a path -- naive
        ``Path(str(v))`` produced garbage like ``"path=PosixPath('...')")"``
        and the canonical fallback ``return str(v)`` baked that repr into
        ``CompactedTrajectory.task_id`` (which then surfaced in retrieval
        prompts as ``# Trajectory summary for path=PosixPath(...)`` etc.).

        Resolution order:
          1. ``LocalTaskId.path`` (Pydantic structured form, 0.6+)
          2. ``task_name`` (str; equals ``"harbor-task-copy"`` for our
             runtime layout, so we walk up via the Path's parent dir name)
          3. ``trial_uri`` (URI string -- strip ``file://`` first)

        Final fallback ``"?"`` is the original behavior; our hook ALSO sets
        a canonical task_id on the ReplayRecord from ``TaskRegistry``, so
        a degraded outcome.task_id only affects the cosmetic trajectory
        summary header.
        """
        # 1. Pydantic LocalTaskId — has a .path attribute pointing at the
        #    actual on-disk task dir (typically <runtime_dir>/<task_id>/
        #    harbor-task-copy/). Walk up to recover task_id.
        tid = getattr(trial_result, "task_id", None)
        if tid is not None:
            tid_path = getattr(tid, "path", None)
            if tid_path is not None:
                p = Path(str(tid_path))
                if p.name == "harbor-task-copy":
                    return p.parent.name
                return p.name

        # 2. task_name as str. Either a plain id (``"E1-LS1-T1"``) or the
        #    harbor-task-copy basename whose parent dir IS the id.
        tname = getattr(trial_result, "task_name", None)
        if isinstance(tname, str) and tname:
            p = Path(tname)
            if p.name == "harbor-task-copy":
                # When task_name is the bare basename ("harbor-task-copy"),
                # parent.name is "" -- in that case we have no other source
                # to walk from, fall through to trial_uri.
                if p.parent.name:
                    return p.parent.name
            else:
                return tname

        # 3. trial_uri (file:// URI) as a last resort -- walk up the URI's
        #    path components.
        turi = getattr(trial_result, "trial_uri", None)
        if turi:
            p = VerifierAdapter._path_from_uri_or_str(turi)
            # turi typically points at the trial dir, whose basename is
            # ``<task_id>__<random7>``. Strip the suffix.
            name = p.name
            if "__" in name:
                return name.rsplit("__", 1)[0]
            if p.name == "harbor-task-copy" and p.parent.name:
                return p.parent.name
            return name or "?"

        return "?"


__all__ = ["VerifierAdapter"]
