"""``BaselineRuntime`` -- the dependency-injection container (Part 8 §8.1).

One ``BaselineRuntime`` per ``LifelongRunner.run()``. It bundles every store
+ every component + the strategy into the single object that the Part 4 hook
dispatches against (satisfies ``RuntimeProtocol`` from ``harbor_ext/types.py``).

The :meth:`build` factory:

1. Runs **8 hard asserts** on the ``BaselineConfig`` -- defense-in-depth
   redundancy with the Pydantic validators in Part 3 (§3.2). The asserts
   are the protocol's last guard before a run starts; if any one fails,
   the run aborts before Harbor opens a single container.
2. Allocates the run-root subtree (``library/``, ``stores/``,
   ``runtime/`` parents).
3. Wires stores: ``LibraryStore`` (or ``NullLibrary`` for control
   baselines), ``ReplayStore``, ``EventStore``, ``RetrievalStore``,
   ``SnapshotStore``.
4. Wires components: retriever / trajectory_retriever / history_retriever
   are non-None only when the corresponding ``baseline.use_*`` flag is on.
   ``evolver`` and ``judge`` are non-None only when the corresponding
   evolution capability is on.
5. Wires :class:`LibraryFreezeController` with an optional
   :class:`LifecycleMaintainer`.
6. Builds the strategy via :func:`skillevolbench.strategies.build_strategy`.

The factory is **LLM-injectable**: tests pass deterministic stubs via
``llm_author_call`` / ``llm_judge_call`` / ``embedder``; production leaves
them at None and gets the LiteLLM-backed defaults.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from skillevolbench.components import (
    BaseRetriever,
    EmbeddingRetriever,
    Embedder,
    HashEmbedder,
    HistoryRetriever,
    LiteLLMClient,
    LLMSelfRetriever,
    LibraryFreezeController,
    LifecycleMaintainer,
    MaintenanceConfig,
    SkillAuthor,
    TrajectoryCompactor,
    TrajectoryExtractor,
    TrajectoryRetriever,
    VerifierAdapter,
)
from skillevolbench.prompting import PromptBuilder
from skillevolbench.runtime_builder import RuntimeBuilder
from skillevolbench.schemas import (
    BaselineConfig,
    RunConfig,
    StrategyConfig,
    Track,
)
from skillevolbench.stores import (
    EventStore,
    LibraryStore,
    NullLibrary,
    ReplayStore,
    RetrievalStore,
    SnapshotStore,
)
from skillevolbench.strategies import (
    EvolutionStrategy,
    build_strategy,
)


_LOG = logging.getLogger(__name__)


# Type aliases for injection points.
SyncCall = Callable[[str], str]


# ---------------------------------------------------------------------------
# BaselineRuntime
# ---------------------------------------------------------------------------


@dataclass
class BaselineRuntime:
    """Aggregated runtime that satisfies ``RuntimeProtocol``.

    All fields are populated by :meth:`build`. The Part 4 hook reads them
    via :class:`skillevolbench.harbor_ext.types.RuntimeProtocol`.
    """

    # --- Part 3 config ---
    baseline: BaselineConfig
    strategy_config: StrategyConfig
    run_config: RunConfig

    # --- Part 5 stores ---
    library: Any                       # LibraryStore | NullLibrary
    replay_store: ReplayStore
    event_store: EventStore
    retrieval_store: RetrievalStore
    snapshot_store: Optional[SnapshotStore]

    # --- Part 6 components ---
    retriever: Optional[BaseRetriever]
    trajectory_retriever: Optional[TrajectoryRetriever]
    history_retriever: Optional[HistoryRetriever]
    evolver: Optional[SkillAuthor]
    judge: None      # RGPE removed -- placeholder; always None
    freeze_ctrl: LibraryFreezeController
    verifier_adapter: VerifierAdapter
    compactor: TrajectoryCompactor
    # Sibling compactor with rough budgets (reasoning dropped, brief obs,
    # small budget). Used to populate ``ReplayRecord.trajectory_compact_rough``
    # which TrajectoryRetriever (raw_trajectory_rag baseline) reads. Kept
    # separate from ``compactor`` (the rich one for SkillAuthor) so the
    # raw-experience baseline doesn't silently benefit from abstraction-
    # friendly preprocessing.
    compactor_rough: TrajectoryCompactor
    trajectory_extractor: TrajectoryExtractor

    # --- Builders (created here, used by the hook) ---
    runtime_builder: RuntimeBuilder
    prompt_builder: PromptBuilder

    # --- Part 7 strategy ---
    strategy: EvolutionStrategy

    # --- Run identity ---
    run_root: Path

    # --- Cost tracking ---
    # All LiteLLMClient instances the runtime owns (host-side LLM
    # consumers: SkillAuthor's author model, LLMSelfRetriever, etc).
    # ReportGenerator iterates these to sum host token + USD spend
    # at run end. Instances retain cumulative counters across the run.
    host_llm_clients: list = field(default_factory=list)

    # --- Per-env library bookkeeping (only used when
    #     baseline.library_scope == "environment") ---
    # Pool of LibraryStores keyed by env_id. Populated lazily by
    # ``switch_env`` on each env's first task. ``library`` (above) is
    # swapped to the current env's instance + freeze_ctrl / snapshot_store
    # are rebuilt to point at it. Container mount path stays stable
    # because ``library/active`` is a symlink whose target switches.
    library_pool: dict[str, Any] = field(default_factory=dict)
    library_root: Optional[Path] = None
    library_scope: str = "global"
    _maintenance_config_template: Optional[Any] = None

    # ------------------------------------------------------------------
    # Public factory
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        config: RunConfig,
        *,
        llm_author_call: Optional[SyncCall] = None,
        # Deprecated compatibility alias for older tests/extensions.
        llm_patch_call: Optional[SyncCall] = None,
        llm_judge_call: Optional[SyncCall] = None,
        embedder: Optional[Embedder] = None,
        maintenance_config: Optional[MaintenanceConfig] = None,
    ) -> "BaselineRuntime":
        """Compose every store / component / strategy from a ``RunConfig``.

        Parameters
        ----------
        config
            Fully-validated :class:`RunConfig` (Part 3).
        llm_author_call / llm_judge_call
            Optional LLM call overrides. When ``None``, the production
            defaults wire ``LiteLLMClient`` against the configured model.
            Tests pass deterministic stubs.
        embedder
            Optional :class:`Embedder` override. Defaults to
            :class:`HashEmbedder` for reproducibility on CI; production
            should swap in :class:`LiteLLMEmbedder`.
        maintenance_config
            Optional :class:`MaintenanceConfig` for the lifecycle
            maintainer. Defaults to the threshold values declared in
            :class:`MaintenanceConfig`.
        """
        if llm_author_call is None:
            llm_author_call = llm_patch_call

        baseline = config.baseline
        strategy_cfg = config.strategy
        run_root = config.run_dir.resolve()

        # ===== 1. Hard asserts (defense in depth) =====
        cls._assert_protocol_invariants(baseline, strategy_cfg, config)

        # ===== 2. Run-root scaffold =====
        run_root.mkdir(parents=True, exist_ok=True)

        # ===== 3. Stores =====
        # Library lifetime is controlled by ``baseline.library_scope``:
        #   - "global"      -- single LibraryStore at run_root/library/.
        #                      Same git repo + manifest across all 6 envs.
        #   - "environment" -- per-env LibraryStores at
        #                      run_root/library/<env_id>/. Each env has
        #                      its own git repo + manifest. ``runtime.library``
        #                      is swapped on env transition (see switch_env).
        #                      Container mount source ``library/active`` is a
        #                      symlink whose target is updated to the active
        #                      env's subdir; the mount path stays stable so
        #                      env.py and the agent CLIs see no difference.
        library_scope = getattr(baseline, "library_scope", "global")
        library_root = run_root / "library"
        library_pool: dict[str, Any] = {}
        if baseline.use_skill_library:
            library_root.mkdir(parents=True, exist_ok=True)
            if library_scope == "environment":
                # Don't init any env-specific LibraryStore yet -- switch_env
                # at the first trial does the lazy init for that env. The
                # active symlink also created on first switch_env.
                library: Any = NullLibrary()   # placeholder until switch_env
                snapshot_store: Optional[SnapshotStore] = None
            else:
                library = LibraryStore.init(library_root)
                library_pool["__global__"] = library
                snapshot_store = SnapshotStore(library)
        else:
            library = NullLibrary()
            snapshot_store = None

        replay_store = ReplayStore(run_root / "stores" / "replay")
        event_store = EventStore(run_root / "stores" / "events")
        retrieval_store = RetrievalStore(run_root / "stores" / "retrieval")

        # ===== 4. Stateless components =====
        verifier_adapter = VerifierAdapter()
        compactor = TrajectoryCompactor()
        compactor_rough = TrajectoryCompactor.make_rough()
        trajectory_extractor = TrajectoryExtractor()

        # Track all LiteLLMClient instances we construct so the cost
        # report at run end can sum host-side tokens / USD across
        # SkillAuthor + LLMSelfRetriever (etc).
        host_llm_clients: list = []

        # Memory channels -- only allocated when the baseline uses them.
        retriever: Optional[BaseRetriever] = None
        if baseline.use_skill_library:
            retriever = cls._build_retriever(
                baseline=baseline, run_config=config, embedder=embedder,
                host_llm_clients=host_llm_clients,
            )

        trajectory_retriever: Optional[TrajectoryRetriever] = None
        if baseline.use_trajectory_rag:
            trajectory_retriever = TrajectoryRetriever(replay_store=replay_store)

        history_retriever: Optional[HistoryRetriever] = None
        if baseline.use_history_context:
            history_retriever = HistoryRetriever(replay_store=replay_store)

        # ===== 5. LLM-backed components =====
        evolver = cls._build_evolver(
            baseline=baseline, strategy_cfg=strategy_cfg, run_config=config,
            llm_author_call=llm_author_call,
            host_llm_clients=host_llm_clients,
        )
        # RGPE removed: no judge component is constructed.
        judge = None
        _ = llm_judge_call   # accepted for back-compat but unused

        # ===== 6. Lifecycle maintainer + freeze controller =====
        maintainer: Optional[LifecycleMaintainer] = None
        if baseline.allow_post_eval_maintenance:
            maintainer = LifecycleMaintainer(
                library=library,
                event_store=event_store,
                config=maintenance_config or MaintenanceConfig(),
            )
        freeze_ctrl = LibraryFreezeController(
            library=library,
            event_store=event_store,
            maintainer=maintainer,
        )

        # ===== 7. Builders =====
        prompt_builder = PromptBuilder()
        runtime_builder = RuntimeBuilder(prompt_builder=prompt_builder)

        # ===== 8. Strategy =====
        strategy = build_strategy(
            name=strategy_cfg.name,
            evolver=evolver,
            retriever=retriever,
            library=library,
            replay_store=replay_store,
            event_store=event_store,
            config=strategy_cfg,
        )

        # Sanity post-conditions for the wiring.
        cls._assert_wiring_consistency(
            baseline=baseline, strategy_cfg=strategy_cfg,
            library=library, retriever=retriever,
            evolver=evolver,
            strategy=strategy,
        )

        return cls(
            baseline=baseline,
            strategy_config=strategy_cfg,
            run_config=config,
            library=library,
            replay_store=replay_store,
            event_store=event_store,
            retrieval_store=retrieval_store,
            snapshot_store=snapshot_store,
            retriever=retriever,
            trajectory_retriever=trajectory_retriever,
            history_retriever=history_retriever,
            evolver=evolver,
            judge=judge,
            freeze_ctrl=freeze_ctrl,
            verifier_adapter=verifier_adapter,
            compactor=compactor,
            compactor_rough=compactor_rough,
            trajectory_extractor=trajectory_extractor,
            runtime_builder=runtime_builder,
            prompt_builder=prompt_builder,
            strategy=strategy,
            run_root=run_root,
            host_llm_clients=host_llm_clients,
            library_pool=library_pool,
            library_root=library_root,
            library_scope=library_scope,
            _maintenance_config_template=maintenance_config,
        )

    # ------------------------------------------------------------------
    # Per-env library swap (library_scope=="environment" only)
    # ------------------------------------------------------------------

    def switch_env(self, env_id: str) -> None:
        """Swap ``self.library`` to the LibraryStore for ``env_id``.

        Only runs when ``baseline.library_scope == "environment"``. Lazy-
        inits the per-env LibraryStore (own git repo + manifest) on first
        encounter, then rebuilds ``snapshot_store`` / ``maintainer`` /
        ``freeze_ctrl`` so they hold a reference to the new library.

        Container mount paths are NOT touched here -- env.py computes the
        right per-env path on each trial from ``trial_paths.task_id``, so
        the host-side runtime only needs to keep the in-process Python
        objects in sync with the current env.

        No-op when ``library_scope == "global"`` (single library wired at
        build() time) or when the baseline uses NullLibrary.

        Idempotent: calling with the current env_id is cheap (dict
        lookup + reassignment); the LibraryStore for that env is reused.
        """
        if self.library_scope == "global" or not self.baseline.use_skill_library:
            return
        assert self.library_root is not None
        if env_id not in self.library_pool:
            env_subdir = self.library_root / env_id
            self.library_pool[env_id] = LibraryStore.init(env_subdir)
        new_library = self.library_pool[env_id]
        # Already on this env? no rebuild needed.
        if self.library is new_library:
            return
        self.library = new_library
        # Rebuild components that hold a library ref bound at init time.
        self.snapshot_store = SnapshotStore(new_library)
        new_maintainer: Optional[LifecycleMaintainer] = None
        if self.baseline.allow_post_eval_maintenance:
            new_maintainer = LifecycleMaintainer(
                library=new_library,
                event_store=self.event_store,
                config=self._maintenance_config_template or MaintenanceConfig(),
            )
        self.freeze_ctrl = LibraryFreezeController(
            library=new_library,
            event_store=self.event_store,
            maintainer=new_maintainer,
        )

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_host_litellm(
        *,
        run_config: RunConfig,
        fallback_model: str,
    ) -> tuple[str, Optional[str], Optional[str]]:
        """Pick (model, api_base, api_key) for host-side LLM calls.

        Precedence (high → low):
          1. SEVB_HOST_LITELLM_* env vars (set by scripts/run.py when a
             --model-yaml is passed -- this is the "run's LLM" routing)
          2. fallback_model + run_config.api_base/api_key (used when no
             model preset is active; e.g. test runs)

        Result: when running with --model-yaml=configs/models/X.yaml,
        ALL host-side LLM components (LLMSelfRetriever, SkillAuthor,
        ) end up calling X via the same Bedrock/Azure/Gemini/Mantle
        endpoint as the agent in the container.
        """
        import os
        return (
            os.environ.get("SEVB_HOST_LITELLM_MODEL") or fallback_model,
            os.environ.get("SEVB_HOST_LITELLM_API_BASE") or run_config.api_base,
            os.environ.get("SEVB_HOST_LITELLM_API_KEY") or run_config.api_key,
        )

    @staticmethod
    def _build_retriever(
        *,
        baseline: BaselineConfig,
        run_config: RunConfig,
        embedder: Optional[Embedder],
        host_llm_clients: list,
    ) -> BaseRetriever:
        """Pick the retriever class based on baseline.retriever_type.

        - "embedding" (default): EmbeddingRetriever with the configured embedder
        - "llm_self":            LLMSelfRetriever using the run's host-side
                                 LiteLLM routing (see _resolve_host_litellm)
        - "oracle":              OracleRetriever (T6 oracle ablation only)

        Any LiteLLMClient created here is appended to ``host_llm_clients``
        so the run-end CostReport can sum its host-side token + USD spend.
        """
        rtype = getattr(baseline, "retriever_type", "embedding")
        if rtype == "llm_self":
            model, api_base, api_key = BaselineRuntime._resolve_host_litellm(
                run_config=run_config,
                fallback_model=baseline.model_name,
            )
            client = LiteLLMClient(
                model=model,
                api_base=api_base,
                api_key=api_key,
                temperature=0.0,
                max_tokens=1024,
                json_mode=True,
                tag="llm_self_retriever",
            )
            host_llm_clients.append(client)
            return LLMSelfRetriever(call_fn=client.__call__)
        if rtype == "oracle":
            from skillevolbench.components.retriever import OracleRetriever
            # Wrap an EmbeddingRetriever as the non-T6 fallback. Without
            # this, T1-T5 would always get empty retrieval (because
            # OracleRetriever.required_skills is T6-only) and the agent
            # would never see any skill in learning.
            inner = EmbeddingRetriever(
                embedder=embedder or HashEmbedder(),
                family_boost=getattr(baseline, "retrieval_family_boost", 0.0),
                phase_aware=getattr(baseline, "retrieval_phase_aware", True),
            )
            return OracleRetriever(inner=inner)
        # default
        return EmbeddingRetriever(
            embedder=embedder or HashEmbedder(),
            family_boost=getattr(baseline, "retrieval_family_boost", 0.0),
            phase_aware=getattr(baseline, "retrieval_phase_aware", True),
        )

    @staticmethod
    def _build_evolver(
        *,
        baseline: BaselineConfig,
        strategy_cfg: StrategyConfig,
        run_config: RunConfig,
        llm_author_call: Optional[SyncCall],
        host_llm_clients: list,
    ) -> Optional[SkillAuthor]:
        """Build the SkillAuthor evolver.

        When a real LiteLLMClient is constructed, it is appended to
        ``host_llm_clients`` so the run-end CostReport can sum its tokens
        + USD spend. Test stubs (``llm_author_call`` not None) bypass this.
        """
        needs_evolver = (
            baseline.allow_self_gen_induction
            or baseline.allow_zero_shot_creation
            or baseline.allow_revision
        )
        if not needs_evolver:
            return None
        if llm_author_call is not None:
            return SkillAuthor(
                sync_call=llm_author_call,
                feedback_level=baseline.feedback_level,
            )
        # When --model-yaml is active, route authoring through the
        # run's LLM (same provider/model as the agent); otherwise fall back
        # to strategy_cfg.author_model (controlled-constant SkillFlow style).
        model, api_base, api_key = BaselineRuntime._resolve_host_litellm(
            run_config=run_config,
            fallback_model=strategy_cfg.author_model,
        )
        client = LiteLLMClient(
            model=model,
            api_base=api_base,
            api_key=api_key,
            temperature=strategy_cfg.author_temperature,
            max_tokens=strategy_cfg.author_max_tokens,
            tag="skill_author",
        )
        host_llm_clients.append(client)
        return SkillAuthor(
            sync_call=client.__call__,
            async_call=client.acall,
            feedback_level=baseline.feedback_level,
        )

    # ------------------------------------------------------------------
    # Hard asserts (Engineering Design §14.1)
    # ------------------------------------------------------------------

    @staticmethod
    def _assert_protocol_invariants(
        baseline: BaselineConfig,
        strategy_cfg: StrategyConfig,
        run_config: RunConfig,
    ) -> None:
        """8 invariants that must hold for the protocol to be valid.

        These are *redundant* with the Pydantic validators in Part 3, but
        the engineering design explicitly says these are hard asserts at
        runtime build time -- the schema validators only catch shape
        problems, while the asserts here are the documented contract that
        any future caller must honor.
        """
        # 1. Path-A baselines never read curated content
        track_value = (
            baseline.track.value if hasattr(baseline.track, "value")
            else str(baseline.track)
        )
        if track_value == Track.PATH_A.value:
            assert baseline.skill_init != "curated", (
                f"Path-A baseline {baseline.name!r} has skill_init='curated' "
                "(would leak curated SKILL.md into a self-generated track)"
            )
            assert not baseline.allow_curated_inject, (
                f"Path-A baseline {baseline.name!r} has allow_curated_inject=True"
            )

        # 2. No-Skill: no memory channels of any kind
        if baseline.name == "no_skill":
            assert not baseline.use_skill_library, (
                "No-Skill must have use_skill_library=False"
            )
            assert not baseline.use_trajectory_rag, (
                "No-Skill must have use_trajectory_rag=False"
            )
            assert not baseline.use_history_context, (
                "No-Skill must have use_history_context=False"
            )
            assert not baseline.use_feedback_memory, (
                "No-Skill must have use_feedback_memory=False"
            )

        # 3. Post-eval maintenance requires at least one mutation channel
        if baseline.allow_post_eval_maintenance:
            assert baseline.allow_retirement or baseline.allow_quarantine, (
                f"baseline {baseline.name!r}: allow_post_eval_maintenance=True "
                "requires allow_retirement OR allow_quarantine"
            )

        # 4. Lifelong protocol requires single-trial execution
        assert run_config.harbor_n_concurrent_trials == 1, (
            "harbor_n_concurrent_trials must be 1 for the lifelong protocol; "
            f"got {run_config.harbor_n_concurrent_trials}"
        )

        # 5. Strategy.name == "none" iff baseline does not revise/induce
        baseline_uses_strategy = (
            baseline.allow_self_gen_induction or baseline.allow_revision
        )
        if not baseline_uses_strategy:
            assert strategy_cfg.name in {"none", "chain"}, (
                f"baseline {baseline.name!r} does not use a strategy "
                f"(allow_self_gen_induction={baseline.allow_self_gen_induction}, "
                f"allow_revision={baseline.allow_revision}); cannot pair with "
                f"strategy {strategy_cfg.name!r}. Use 'chain' as placeholder."
            )

        # 6. Path-B baselines must inject curated v0
        if track_value == Track.PATH_B.value:
            assert baseline.skill_init == "curated", (
                f"Path-B baseline {baseline.name!r} must have skill_init='curated'"
            )
            assert baseline.allow_curated_inject, (
                f"Path-B baseline {baseline.name!r} must allow_curated_inject=True"
            )

        # 7. Control baselines do not use the skill library
        if track_value == Track.CONTROL.value:
            assert not baseline.use_skill_library, (
                f"Control baseline {baseline.name!r} must have "
                "use_skill_library=False"
            )

        # 8. Zero-shot iff allow_zero_shot_creation
        if baseline.skill_init == "zero_shot":
            assert baseline.allow_zero_shot_creation, (
                f"baseline {baseline.name!r} skill_init='zero_shot' requires "
                "allow_zero_shot_creation=True"
            )

    @staticmethod
    def _assert_wiring_consistency(
        *,
        baseline: BaselineConfig,
        strategy_cfg: StrategyConfig,
        library: Any,
        retriever: Optional[BaseRetriever],
        evolver: Optional[SkillAuthor],
        strategy: EvolutionStrategy,
    ) -> None:
        """Post-build sanity: the wiring matches what the baseline asked for."""
        if baseline.use_skill_library:
            scope = getattr(baseline, "library_scope", "global")
            if scope == "environment":
                # Per-env libraries are lazy-init'd by switch_env on each
                # env's first task. At build time, ``library`` is a
                # NullLibrary placeholder -- the wiring becomes valid
                # after the first ``runtime.switch_env(env_id)`` call.
                assert isinstance(library, NullLibrary), (
                    "library_scope='environment' should leave library as a "
                    "NullLibrary placeholder until switch_env runs"
                )
            else:
                assert isinstance(library, LibraryStore), (
                    "use_skill_library=True (global scope) but library is "
                    "not a LibraryStore"
                )
            assert retriever is not None, (
                "use_skill_library=True but retriever is None"
            )
        else:
            assert isinstance(library, NullLibrary), (
                "use_skill_library=False but library is not a NullLibrary"
            )
            assert retriever is None, (
                "use_skill_library=False but retriever is not None"
            )

        # Strategy <-> evolver
        if strategy_cfg.name == "none":
            # NullStrategy never calls evolver -- can be None.
            pass
        elif strategy_cfg.name in {"chain", "chain_tier3"}:
            if (baseline.allow_self_gen_induction or baseline.allow_revision):
                assert evolver is not None, (
                    f"strategy {strategy_cfg.name!r} requires an evolver "
                    f"when baseline allows induction/revision"
                )

    # ------------------------------------------------------------------
    # Convenience properties (the hook never reads these but tests do)
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Composite identifier for log lines."""
        return (
            f"{self.baseline.name}__{self.strategy.name}__"
            f"seed{self.run_config.order_seed}"
        )


__all__ = ["BaselineRuntime"]
