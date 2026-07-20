"""TrajectoryCompactor -- summarise a raw trajectory into a token-budgeted text.

The :class:`CompactedTrajectory` is what gets persisted into ReplayStore +
fed into SkillAuthor / RGPE judge prompts. Raw trajectories can be hundreds
of KB; we want a roughly 2k-token summary.

Strategy (deterministic, no LLM):

1. Parse known agent trajectory shapes (claude-code, gemini, openclaw,
   plain text).
2. Extract a flat sequence of (event_type, content) tuples.
3. Keep:
   * the first ``head`` events (tool-use / system / user)
   * the last ``tail`` events (final assistant text + tool errors)
   * any event whose content matches a "signal" regex (errors, stack
     traces, ``/skills/`` reads).
4. Render as a markdown block with one bullet per kept event.

Token counting is approximate (chars / 4); good enough for budgeting.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from skillevolbench.schemas import CompactedTrajectory, TrialOutcome


_LOG = logging.getLogger(__name__)

_SIGNAL_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r"Error:|Exception:|FAILED|ERROR\b"),
    re.compile(r"/skills/"),
    re.compile(r"reward\.txt|verifier"),
]


class TrajectoryCompactor:
    def __init__(
        self,
        head: int = 8,
        tail: int = 12,
        # ``max_event_chars`` bumped to 8000 so a single event with
        # full reasoning (3000) + full observation (3000) + tool_calls
        # (~600) + some structural overhead survives the per-event
        # truncation in ``_render``.
        max_event_chars: int = 8000,
        # ``max_total_tokens`` bumped to 8000 per trial (~32K chars).
        # Combined with cumulative-trace concatenation in chain.py,
        # T3 propose() sees up to ~24K tokens of trace history (T1+T2+T3),
        # which fits comfortably under modern context windows even
        # before the system-prompt cache discount kicks in.
        max_total_tokens: int = 8000,
        # Per-step budgets used by ``_render_atif_step``.
        # ``max_reasoning_chars=None`` means NO truncation in rich mode --
        # empirical observation: Claude opus-4.6 / sonnet-4.6 produce
        # reasoning up to 7758 chars per step (avg 1200-1400 when present);
        # the previous 3000 cap silently truncated the high-value outliers
        # by 60%+. The per-event cap (max_event_chars=8000) is the global
        # safety net for runaway reasoning. Set to 0 in rough mode (raw
        # baseline) to drop reasoning entirely. Set to a positive int to
        # truncate at that limit (legacy behaviour, kept for ablations).
        max_reasoning_chars: Optional[int] = None,
        # ``max_message_chars=None`` means NO truncation -- agent messages
        # are usually short (50-300 chars) but the final summary can hit
        # 500-1500 chars and is the agent's own end-of-task synthesis;
        # truncating at 400 (the previous default) silently lost summary
        # content. SkillFlow also doesn't truncate. The per-event cap
        # (max_event_chars=8000) is the global safety net.
        max_message_chars: Optional[int] = None,
        max_observation_chars: int = 3000,
        max_tool_args_chars: int = 200,
    ) -> None:
        self.head = head
        self.tail = tail
        self.max_event_chars = max_event_chars
        self.max_reasoning_chars = max_reasoning_chars
        self.max_message_chars = max_message_chars
        self.max_observation_chars = max_observation_chars
        self.max_tool_args_chars = max_tool_args_chars
        self.max_total_tokens = max_total_tokens

    @classmethod
    def make_rough(cls) -> "TrajectoryCompactor":
        """Return a compactor configured for ROUGH compaction.

        Used by raw_trajectory_rag baseline to surface past episodic
        experience to the agent. The ONLY semantic difference vs rich
        mode is that ``reasoning_content`` is dropped (rough is meant
        to be a NO-ABSTRACTION baseline -- including the agent's own
        meta-reasoning would let "thinking" leak into the supposedly
        raw trace, which is itself a form of abstraction).

        Every OTHER budget mirrors rich mode for a fair comparison
        between selfgen (skill-summarized trace fed to SkillAuthor)
        and raw_trajectory_rag (raw event-stream fed to the agent).
        If rough's per-event / per-message / per-obs budgets are
        tighter than rich's, raw_trajectory_rag is silently penalised
        by being given a thinner signal than the selfgen pipeline
        sees -- that confounds the abstraction-value measurement.

        Concretely:
          - reasoning_content: DROPPED (max_reasoning_chars=0)
                  ← THE ONLY DIFFERENCE FROM RICH MODE
          - message:           NO CAP (matches rich)
          - tool_call args:    100 chars (mirrors SkillFlow budget)
          - observation:       3000 chars (matches rich)
          - max_event_chars:   8000 (matches rich)
          - max_total_tokens:  8000 (matches rich)

        Pair: rich-mode trace fed to SkillAuthor; rough-mode trace fed
        to TrajectoryRetriever (raw_trajectory_rag's agent prompt).
        Both are computed at trial-end and stored side-by-side in
        ``ReplayRecord``.
        """
        return cls(
            head=4,
            tail=8,
            max_event_chars=8000,         # match rich
            max_total_tokens=8000,        # match rich
            max_reasoning_chars=0,        # ← THE ONLY DIFFERENCE FROM RICH
            max_message_chars=None,       # match rich (no cap)
            max_observation_chars=3000,   # match rich
            max_tool_args_chars=100,      # SkillFlow-equivalent budget
        )

    def compact(
        self,
        trajectory_path: Optional[Path],
        outcome: TrialOutcome,
    ) -> CompactedTrajectory:
        if trajectory_path is None or not Path(trajectory_path).exists():
            return CompactedTrajectory(
                task_id=outcome.task_id,
                n_events=0,
                text="(trajectory unavailable)",
                n_tokens=0,
                skills_referenced=[],
                raw_path=None,
            )

        path = Path(trajectory_path)
        events = self._parse_events(path)
        kept_idx = self._select_events(events)
        kept_events = [events[i] for i in kept_idx]

        rendered = self._render(kept_events, outcome=outcome)
        if len(rendered) // 4 > self.max_total_tokens:
            rendered = rendered[: self.max_total_tokens * 4]

        skills = self._referenced_skills(events)

        return CompactedTrajectory(
            task_id=outcome.task_id,
            n_events=len(events),
            text=rendered,
            n_tokens=len(rendered) // 4,
            skills_referenced=skills,
            raw_path=path,
        )

    # ------------------------------------------------------------------
    # Trajectory parsing
    # ------------------------------------------------------------------

    def _parse_events(self, path: Path) -> list[dict[str, Any]]:
        """Best-effort parse into a flat list of ``{kind, text}`` dicts."""
        text = path.read_text(errors="replace")

        # Try whole-file JSON first (ATIF / openclaw / claude-code shapes).
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None

        if data is not None:
            return self._events_from_json(data)

        # JSONL fallback (Gemini's session-*.jsonl / kimi-cli newline-delimited).
        # Use only when at least 2 non-blank lines all parse as JSON objects;
        # otherwise fall through to the plain-text branch.
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2:
            jsonl_events: list[dict[str, Any]] = []
            for ln in lines:
                try:
                    obj = json.loads(ln)
                except json.JSONDecodeError:
                    jsonl_events = []
                    break
                if isinstance(obj, dict):
                    jsonl_events.append(
                        {"kind": str(obj.get("type") or obj.get("role") or "jsonl"),
                         "text": json.dumps(obj, default=str)[:2000]}
                    )
                else:
                    jsonl_events.append(
                        {"kind": "jsonl", "text": json.dumps(obj, default=str)[:2000]}
                    )
            if jsonl_events:
                return jsonl_events

        # Plain text trajectory (Claude .txt). Split on blank lines.
        return [
            {"kind": "line", "text": line}
            for line in text.splitlines()
            if line.strip()
        ]

    def _events_from_json(self, data: Any) -> list[dict[str, Any]]:
        # Harbor ATIF (Agent Trajectory Interchange Format).
        # Schema: {schema_version: "ATIF-vX.Y", session_id, agent, steps: [...], final_metrics}.
        # All supported ATIF-aware CLIs (including OpenCode)
        # converge on this format -- writing canonical trajectory.json.
        if (
            isinstance(data, dict)
            and isinstance(data.get("steps"), list)
            and (
                isinstance(data.get("schema_version"), str)
                or "agent" in data
            )
        ):
            return [
                self._render_atif_step(step)
                for step in data["steps"]
            ]

        # Common shape A: {events: [...]}
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            return [
                {"kind": "event", "text": json.dumps(ev, default=str)[:2000]}
                for ev in data["events"]
            ]
        # Common shape B: {messages: [...]}
        if isinstance(data, dict) and isinstance(data.get("messages"), list):
            return [
                {"kind": "msg", "text": json.dumps(m, default=str)[:2000]}
                for m in data["messages"]
            ]
        # OpenClaw shape
        if isinstance(data, dict) and "trace" in data:
            trace = data["trace"]
            if isinstance(trace, list):
                return [
                    {"kind": "trace", "text": json.dumps(t, default=str)[:2000]}
                    for t in trace
                ]
        # Generic top-level list
        if isinstance(data, list):
            return [
                {"kind": "item", "text": json.dumps(it, default=str)[:2000]}
                for it in data
            ]
        # Fallback: dump the whole object as one event.
        return [{"kind": "blob", "text": json.dumps(data, default=str)[:5000]}]

    def _render_atif_step(self, step: dict[str, Any]) -> dict[str, str]:
        """Pretty-render a single ATIF step into a one-event dict.

        ATIF Step fields we care about (per Harbor's docs):
          - step_id           (sequential)
          - source            ("user" / "agent" / "system")
          - message           (text)
          - reasoning_content (agent thinking; agent steps only)
                              -- HIGHEST-VALUE field for skill induction;
                              gets the largest per-step budget
          - tool_calls        (list of {name, arguments})
          - observation       ({text, error?, exit_code?, stdout?, ...})
        Other fields (timestamp / metrics / model_name / step_id ordering)
        are dropped to keep the event text token-cheap.
        """
        if not isinstance(step, dict):
            return {"kind": "step", "text": json.dumps(step, default=str)[:1500]}
        source = step.get("source") or step.get("role") or "?"
        sid = step.get("step_id") or step.get("id") or ""
        parts: list[str] = []
        sid_prefix = f"[{sid}] " if sid else ""

        msg = step.get("message")
        if isinstance(msg, str) and msg.strip():
            text = msg.strip()
            if self.max_message_chars is not None:
                text = text[:self.max_message_chars]
            parts.append(f"{sid_prefix}msg: {text}")

        # Three modes via ``max_reasoning_chars``:
        #   - None         : preserve full reasoning (rich/SkillAuthor)
        #   - 0            : DROP entirely (rough/raw_trajectory_rag --
        #                    raw episodic experience baseline must not
        #                    inherit the agent's private abstraction)
        #   - positive int : truncate at that limit (legacy / ablation)
        # Empirical sparsity: 0% on Codex, 1% on Gemini, 3-10% on Claude
        # (4.5 vs 4.6+); avg 200-1400 chars when present, max 7758. So
        # most steps have no reasoning anyway -- this branch is a no-op
        # 90%+ of the time but bears all the high-value cases on Claude.
        if self.max_reasoning_chars is None or self.max_reasoning_chars > 0:
            reasoning = step.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning.strip():
                text = reasoning.strip()
                if self.max_reasoning_chars is not None:
                    text = text[:self.max_reasoning_chars]
                parts.append(f"reasoning: {text}")

        tool_calls = step.get("tool_calls") or []
        if isinstance(tool_calls, list):
            for tc in tool_calls[:3]:
                if not isinstance(tc, dict):
                    continue
                name = tc.get("name") or tc.get("tool") or "?"
                args = tc.get("arguments") or tc.get("args") or tc.get("input") or {}
                limit = self.max_tool_args_chars
                if isinstance(args, dict):
                    args_text = json.dumps(args, default=str)[:limit]
                else:
                    args_text = str(args)[:limit]
                parts.append(f"tool_call {name}({args_text})")

        obs = step.get("observation")
        if isinstance(obs, dict):
            obs_text = (
                obs.get("error")
                or obs.get("text")
                or obs.get("stdout")
                or json.dumps(obs, default=str)[:300]
            )
            if obs_text:
                parts.append(
                    f"obs: {str(obs_text)[:self.max_observation_chars]}"
                )
        elif isinstance(obs, str) and obs.strip():
            parts.append(
                f"obs: {obs.strip()[:self.max_observation_chars]}"
            )

        if not parts:
            parts.append(json.dumps(step, default=str)[:300])

        return {"kind": f"step:{source}", "text": " | ".join(parts)}

    # ------------------------------------------------------------------
    # Selection + rendering
    # ------------------------------------------------------------------

    def _select_events(self, events: list[dict[str, Any]]) -> list[int]:
        """Indices of events to keep: head + tail + every signal event."""
        n = len(events)
        head = list(range(min(self.head, n)))
        tail = list(range(max(0, n - self.tail), n))
        signals = [
            i for i, ev in enumerate(events)
            if any(pat.search(ev.get("text", "")) for pat in _SIGNAL_PATTERNS)
        ]
        kept = sorted(set(head + tail + signals))
        return kept

    def _render(
        self,
        events: list[dict[str, Any]],
        outcome: TrialOutcome,
    ) -> str:
        verdict = "PASSED" if outcome.verifier_passed else "FAILED"
        lines = [
            f"# Trajectory summary for {outcome.task_id} ({verdict}, "
            f"reward={outcome.reward:.2f})",
        ]
        if outcome.failure_summary:
            lines.append("\n**Verifier failure summary:**\n")
            lines.append(outcome.failure_summary[: self.max_event_chars])
            lines.append("")
        lines.append("## Selected trajectory events\n")
        for ev in events:
            text = ev.get("text", "").strip()
            if len(text) > self.max_event_chars:
                text = text[: self.max_event_chars] + "..."
            lines.append(f"- [{ev.get('kind', '?')}] {text}")
        return "\n".join(lines)

    @staticmethod
    def _referenced_skills(events: list[dict[str, Any]]) -> list[str]:
        from skillevolbench.components.trajectory_extractor import (
            _SKILL_REF_RE,
        )
        seen: set[str] = set()
        for ev in events:
            for m in _SKILL_REF_RE.finditer(ev.get("text", "")):
                seen.add(m.group(1).rstrip("./"))
        return sorted(seen)


__all__ = ["TrajectoryCompactor"]
