"""Skill retrievers (Part 6 §6.1).

Two implementations of the same interface:

* :class:`EmbeddingRetriever` -- dense retrieval over the live skill library.
                                  Pluggable :class:`Embedder` (defaults to
                                  :class:`HashEmbedder` for reproducibility on
                                  CI; production uses :class:`LiteLLMEmbedder`
                                  configured via ``configs/llm.yaml``).
* :class:`OracleRetriever`    -- returns the T6 ``required_skills`` from the
                                  task spec verbatim. Used by dual-T6
                                  shadow evaluation.

Both produce the same :class:`RetrievalResult` schema.
"""

from __future__ import annotations

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from typing import Any, Iterable, Optional, Protocol, Sequence

from skillevolbench.schemas import (
    RetrievalResult,
    RetrievedSkill,
    SkillManifestEntry,
)


_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedder protocol + two implementations
# ---------------------------------------------------------------------------


class Embedder(Protocol):
    """Anything that turns a string into a fixed-length float vector."""

    dim: int

    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic hash-based embedder.

    Produces a 256-dim vector from a SHA-256 of the input plus 8 sub-hashes
    folded into floats in [-1, 1]. NOT semantic; intended for tests +
    development. Reproducible across machines without any model files.
    """

    dim: int = 256

    def embed(self, text: str) -> list[float]:
        text = text or ""
        # Generate dim/32 SHA-256 digests by varying the salt; concat to dim
        # bytes then map to floats.
        out: list[float] = []
        n_chunks = self.dim // 32
        for i in range(n_chunks):
            digest = hashlib.sha256(f"{i}:{text}".encode("utf-8")).digest()
            for b in digest:
                out.append((b - 127.5) / 127.5)
        return out[: self.dim]


class LiteLLMEmbedder:
    """Production embedder backed by litellm.embedding(...).

    ``model_name`` follows the litellm convention ("openai/text-embedding-3-small",
    "huggingface/Qwen/Qwen3-Embedding-4B", etc.). Lazy-imports litellm so
    machines without it still import this module.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-4B",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        dim: int = 1024,
    ) -> None:
        self.model_name = model_name
        self.api_base = api_base
        self.api_key = api_key
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        import litellm  # lazy
        resp = litellm.embedding(
            model=self.model_name,
            input=[text or ""],
            api_base=self.api_base,
            api_key=self.api_key,
        )
        return list(resp["data"][0]["embedding"])


# ---------------------------------------------------------------------------
# Retriever interface
# ---------------------------------------------------------------------------


class BaseRetriever(ABC):
    """Common interface used by the Part 4 hook."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        library: Any,
        k: int,
        *,
        task_id: Optional[str] = None,
    ) -> RetrievalResult: ...


# ---------------------------------------------------------------------------
# EmbeddingRetriever -- dense retrieval over the live library
# ---------------------------------------------------------------------------


class EmbeddingRetriever(BaseRetriever):
    """Cosine-similarity retrieval against a library's active skills.

    Caches:

    * ``_skill_emb_cache``:  ``(skill_id, version)`` -> vector. Survives
      across calls; invalidated automatically because the key includes
      ``current_version``.
    * ``_result_cache``:     ``(library_hash, query_hash, k)`` -> result.
      Hit when the same query is issued against an unchanged library
      (e.g. multiple components on the same trial).
    """

    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        *,
        family_boost: float = 0.0,
        phase_aware: bool = True,
    ) -> None:
        self.embedder: Embedder = embedder or HashEmbedder()
        # Additive bonus applied to same-family skills when the current
        # task is NOT a T6 composition. 0.0 = current pure-cosine
        # behaviour. See BaselineConfig.retrieval_family_boost docstring
        # for picking a value.
        self.family_boost: float = float(family_boost)
        # Phase-aware retrieval scope (Scheme B; default ON):
        #   T1-T3 (learning) -- candidate pool restricted to SAME FAMILY.
        #     Direct hand-off of the family's own skill(s) to the agent;
        #     no cosine across cross-family/cross-env library skills.
        #     If the family has multiple active skills (e.g. LLM created
        #     a sibling via the create-new revision rule), all of them
        #     are passed; cosine just orders them within k.
        #   T4-T5 (eval, single-skill)         -- restricted to SAME ENV.
        #   T6   (eval, composition)           -- restricted to SAME ENV
        #     (benchmark spec: required_skills always stay within env --
        #     verified empirically on all 30 T6 tasks).
        # When False, falls back to legacy "global cosine over full
        # library" behaviour. Use the *_global_retrieval ablation yamls
        # to opt out and measure the cross-env transfer effect.
        self.phase_aware: bool = bool(phase_aware)
        self._skill_emb_cache: dict[tuple[str, int], list[float]] = {}
        # Cache key now also includes the scope tag (family / env / "")
        # so different roles of the same query never alias.
        self._result_cache: dict[
            tuple[str, int, int, str, str, int], RetrievalResult
        ] = {}

    @staticmethod
    def _parse_family_and_role_index(task_id: Optional[str]) -> tuple[str, int]:
        """task_id format is ``<env>-LS<n>-T<role_index>`` e.g. ``E1-LS1-T6``.
        Returns (family_id, role_index) or ("", 0) if unparsable."""
        if not task_id or "-T" not in task_id:
            return "", 0
        try:
            family, t_part = task_id.rsplit("-T", 1)
            return family, int(t_part)
        except (ValueError, TypeError):
            return "", 0

    def retrieve(
        self,
        query: str,
        library: Any,
        k: int,
        *,
        task_id: Optional[str] = None,
    ) -> RetrievalResult:
        active = library.list_active() if hasattr(library, "list_active") else []
        if not active:
            return RetrievalResult(skills=[], scores=[], full_ranking=[],
                                   query_text=query)

        task_family, role_index = self._parse_family_and_role_index(task_id)
        task_env = task_family.split("-", 1)[0] if task_family and "-" in task_family else ""

        # ---- Phase-aware candidate scope (Scheme B) ----
        # Filters the active library to the role-appropriate subset BEFORE
        # cosine ranking. See __init__ docstring for the rule per role.
        scope_tag = ""
        if self.phase_aware and task_family:
            if 1 <= role_index <= 3:
                # Learning: hand off the family's own skills only.
                active = [s for s in active if s.family_id == task_family]
                scope_tag = f"fam={task_family}"
            elif 4 <= role_index <= 6 and task_env:
                # Eval: cross-family within env (T6 require_skills always
                # stay in same env -- verified empirically on all 30 T6).
                active = [s for s in active if s.family_id.startswith(task_env + "-")]
                scope_tag = f"env={task_env}"
        if not active:
            return RetrievalResult(skills=[], scores=[], full_ranking=[],
                                   query_text=query)

        # Decide whether the family boost fires for this call. T6
        # (role_index == 6) needs cross-family retrieval, so we exempt it.
        boost = self.family_boost if (
            self.family_boost > 0.0
            and task_family
            and role_index != 6
        ) else 0.0

        # Result cache key (include task_family + scope tag so different
        # tasks of the same query never alias).
        try:
            lib_hash_str = library.compute_hash()
        except Exception:
            lib_hash_str = ""
        cache_key = (
            lib_hash_str, hash(query or ""), int(k),
            task_family if boost > 0 else "",
            scope_tag,
            1 if boost > 0 else 0,
        )
        if cache_key in self._result_cache:
            return self._result_cache[cache_key]

        # Compute / fetch skill embeddings
        skill_vecs: list[list[float]] = []
        for entry in active:
            ek = (entry.skill_id, entry.current_version)
            if ek not in self._skill_emb_cache:
                self._skill_emb_cache[ek] = self.embedder.embed(
                    self._skill_text(entry)
                )
            skill_vecs.append(self._skill_emb_cache[ek])

        query_vec = self.embedder.embed(query or "")

        scored: list[tuple[SkillManifestEntry, float]] = [
            (entry, _cosine(qv, sv))
            for entry, qv, sv in zip(active, [query_vec] * len(active), skill_vecs)
        ]
        if boost > 0.0:
            scored = [
                (entry, score + (boost if entry.family_id == task_family else 0.0))
                for entry, score in scored
            ]
        scored.sort(key=lambda x: -x[1])

        top = scored[: max(0, int(k))]
        full = [(e.skill_id, s) for e, s in scored]

        result = RetrievalResult(
            skills=[
                RetrievedSkill(
                    skill_id=e.skill_id,
                    score=float(s),
                    name=e.name,
                    description=e.description,
                )
                for e, s in top
            ],
            scores=[float(s) for _, s in top],
            full_ranking=full,
            query_text=query,
        )
        self._result_cache[cache_key] = result
        return result

    @staticmethod
    def _skill_text(entry: SkillManifestEntry) -> str:
        parts = [entry.name, entry.description or ""]
        if entry.applicability.include:
            parts.append("applicable: " + ", ".join(entry.applicability.include))
        if entry.applicability.exclude:
            parts.append("not applicable: " + ", ".join(entry.applicability.exclude))
        return " | ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# OracleRetriever -- dual-T6 shadow retrieval
# ---------------------------------------------------------------------------


class LLMSelfRetriever(BaseRetriever):
    """Retrieval via the **same** LLM that solves the task.

    Instead of a dedicated embedding model, we ask the agent's own model
    (e.g. ``anthropic/claude-sonnet-4-6``) to pick top-k from the library.
    Each call:

    1. Builds a prompt with the task instruction + numbered list of all
       active skills (id + name + description).
    2. Invokes ``call_fn(prompt)`` -- a sync LLM caller, typically
       backed by ``LiteLLMClient`` configured with the same model_name as
       the baseline's task-execution agent.
    3. Parses a JSON list of selected skill_ids; falls back to lexical
       overlap if parsing fails.

    Trade-offs vs ``EmbeddingRetriever``:

    * + retrieval semantics match the agent's own reasoning model
    * + no embedding-model dependency
    * - costs one extra LLM call per task (prompt: library + task; ~500-2k tok)
    * - non-deterministic when temperature > 0
    """

    def __init__(
        self,
        call_fn: Any,
        *,
        max_library_skills: int = 80,
        max_description_chars: int = 240,
    ) -> None:
        self._call = call_fn
        self._max_library_skills = max_library_skills
        self._max_description_chars = max_description_chars

    def retrieve(
        self,
        query: str,
        library: Any,
        k: int,
        *,
        task_id: Optional[str] = None,
    ) -> RetrievalResult:
        active = list(library.list_active())
        if not active:
            return RetrievalResult(skills=[], k=k)
        if len(active) <= k:
            # No need to retrieve -- library is already <= k.
            return RetrievalResult(
                skills=[_to_retrieved(s, score=1.0) for s in active],
                k=k,
            )

        # Cap library size in prompt to keep token cost bounded.
        skills = active[: self._max_library_skills]
        prompt = self._build_prompt(query, skills, k)
        try:
            raw = self._call(prompt)
            chosen_ids = self._parse_ids(raw, valid_ids={s.skill_id for s in skills})
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("LLMSelfRetriever LLM call failed: %s; falling back to lexical", exc)
            chosen_ids = self._lexical_fallback(query, skills, k)

        # Take in original library order (stable) and trim to k.
        keep: list[SkillManifestEntry] = [s for s in skills if s.skill_id in chosen_ids][:k]
        if len(keep) < k:
            # Pad to k with lexical fallback for missing slots.
            already = {s.skill_id for s in keep}
            extras = [s for s in skills if s.skill_id not in already]
            extras = self._rank_by_lexical(query, extras)
            keep.extend(extras[: k - len(keep)])

        return RetrievalResult(
            skills=[_to_retrieved(s, score=1.0) for s in keep],
            k=k,
        )

    def _build_prompt(self, query: str, skills: list, k: int) -> str:
        lines = [
            f"Pick the {k} skills most relevant to the task below.",
            "Return STRICT JSON: {\"skill_ids\": [\"id1\", \"id2\", ...]}.",
            "",
            "## Task",
            "",
            query[:2000],
            "",
            f"## Available skills (showing {len(skills)} of {len(skills)})",
            "",
        ]
        for s in skills:
            desc = (getattr(s, "description", "") or "")[: self._max_description_chars]
            name = getattr(s, "name", s.skill_id)
            lines.append(f"- `{s.skill_id}` ({name}): {desc}")
        lines.append("")
        lines.append(f"Return JSON with the {k} most relevant skill_ids only.")
        return "\n".join(lines)

    @staticmethod
    def _parse_ids(raw: str, valid_ids: set[str]) -> list[str]:
        import json
        import re
        text = (raw or "").strip()
        # Try direct JSON first
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                return []
            obj = json.loads(m.group(0))
        ids = obj.get("skill_ids") if isinstance(obj, dict) else None
        if not isinstance(ids, list):
            return []
        return [str(i) for i in ids if str(i) in valid_ids]

    @staticmethod
    def _lexical_fallback(query: str, skills: list, k: int) -> list[str]:
        ranked = LLMSelfRetriever._rank_by_lexical(query, skills)
        return [s.skill_id for s in ranked[:k]]

    @staticmethod
    def _rank_by_lexical(query: str, skills: list) -> list:
        """Cheap word-overlap fallback when LLM call fails."""
        q_tokens = set(query.lower().split())
        scored: list[tuple[float, Any]] = []
        for s in skills:
            text = (getattr(s, "name", "") + " " + (getattr(s, "description", "") or "")).lower()
            t_tokens = set(text.split())
            score = len(q_tokens & t_tokens) / max(len(q_tokens | t_tokens), 1)
            scored.append((score, s))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]


def _to_retrieved(entry: SkillManifestEntry, *, score: float) -> RetrievedSkill:
    return RetrievedSkill(
        skill_id=entry.skill_id,
        name=entry.name,
        description=entry.description or "",
        score=score,
    )


class OracleRetriever(BaseRetriever):
    """Return the T6 task's ``required_skills`` from the task spec verbatim.

    For non-T6 tasks (or tasks with no required_skills), behaviour falls
    back to the wrapped ``inner`` retriever (default: empty result). The
    fall-back keeps dual-T6 shadow retrieval comparable -- we only force-oracle
    on T6.

    ``task_registry`` may be passed eagerly OR left None. When None, the
    registry is lazy-loaded from the default ``benchmark/`` paths on the
    first call. This lets ``BaselineRuntime._build_retriever`` instantiate
    the OracleRetriever without having to plumb the registry down from
    ``LifelongRunner.run``.
    """

    def __init__(
        self,
        task_registry: Optional[Any] = None,
        inner: Optional[BaseRetriever] = None,
    ) -> None:
        self.task_registry = task_registry
        self.inner = inner

    def _ensure_registry(self) -> Optional[Any]:
        if self.task_registry is not None:
            return self.task_registry
        try:
            from skillevolbench.discovery import (
                TaskRegistry, default_skills_root, default_tasks_root,
            )
            self.task_registry = TaskRegistry.from_disk(
                default_skills_root(), default_tasks_root(),
            )
        except Exception:
            _LOG.warning(
                "OracleRetriever: failed to lazy-load TaskRegistry; "
                "falling back to inner retriever for all tasks."
            )
            self.task_registry = None
        return self.task_registry

    def retrieve(
        self,
        query: str,
        library: Any,
        k: int,
        *,
        task_id: Optional[str] = None,
    ) -> RetrievalResult:
        if task_id is None:
            return self._fallback(query, library, k)

        registry = self._ensure_registry()
        if registry is None:
            return self._fallback(query, library, k)

        try:
            record = registry.task(task_id)
        except Exception:
            return self._fallback(query, library, k)

        required = list(record.spec.required_skills or [])
        if not required:
            return self._fallback(query, library, k)

        skills: list[RetrievedSkill] = []
        for sid in required:
            if hasattr(library, "has_skill") and library.has_skill(sid):
                entry = library.get_manifest_entry(sid)
                skills.append(RetrievedSkill(
                    skill_id=sid, score=1.0, name=entry.name,
                    description=entry.description,
                ))
            else:
                skills.append(RetrievedSkill(
                    skill_id=sid, score=1.0, name=sid.split(".", 1)[-1],
                ))
        return RetrievalResult(
            skills=skills,
            scores=[1.0] * len(skills),
            full_ranking=[(s.skill_id, 1.0) for s in skills],
            query_text=query,
        )

    def _fallback(self, query: str, library: Any, k: int) -> RetrievalResult:
        if self.inner is not None:
            return self.inner.retrieve(query, library, k)
        return RetrievalResult(skills=[], scores=[], full_ranking=[], query_text=query)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


__all__ = [
    "Embedder",
    "HashEmbedder",
    "LiteLLMEmbedder",
    "BaseRetriever",
    "EmbeddingRetriever",
    "LLMSelfRetriever",
    "OracleRetriever",
]
