#!/usr/bin/env python3
"""Build a Chinese Markdown and standalone interactive HTML T4-T6 report."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import yaml


MODELS = ("qwen3.7-max", "sig-fable")
CONDITIONS = ("self_generated", "exact_oracle", "no_skill", "curated_all")
ENVS = tuple(f"E{i}" for i in range(1, 7))
TIERS = (4, 5, 6)
EXPECTED_TASKS_PER_ENV = 15
AP_CLUSTER = "hk-benchmark-dev"

MATRIX_STAGE_META = {
    "qwen_exact_oracle": ("qwen3.7-max", "exact_oracle"),
    "qwen_no_skill": ("qwen3.7-max", "no_skill"),
    "qwen_curated_all": ("qwen3.7-max", "curated_all"),
    "fable_exact_oracle": ("sig-fable", "exact_oracle"),
    "fable_no_skill": ("sig-fable", "no_skill"),
    "fable_curated_all": ("sig-fable", "curated_all"),
}

CONDITION_ZH = {
    "self_generated": "模型自生成 skill",
    "exact_oracle": "精确 Curated 子集（Oracle）",
    "no_skill": "无 skill",
    "curated_all": "Env 全量 curated skills",
}
CLASS_ZH = {
    "strict_pass": "严格通过",
    "process_only_failure": "功能通过，仅过程失败",
    "outcome_only_failure": "功能失败，仅过程通过",
    "outcome_and_process_failure": "功能与过程均失败",
    "unknown": "状态未知",
}
CAUSE_ZH = {
    "functional_gap": "功能实现错误或不完整",
    "verified_verifier_false_negative": "已核实的 process verifier 假阴性",
    "substantive_process_gap": "有实际泛化意义的过程约束缺失",
    "shape_sensitive_process_only": "源码形态敏感的 process-only 失败",
    "unresolved_process_only": "尚待人工复核的 process-only 失败",
}
DERIVABILITY_ZH = {
    "captured_from_visible_evidence": "T1–T3 可见且 generated 捕获",
    "oracle_captures_visible_generated_misses": "T1–T3 可见，oracle 捕获但 generated 漏掉",
    "visible_missing_from_both_skills": "T1–T3 可见，两种 skill 都漏掉",
    "oracle_adds_unseen_concept": "仅 oracle 补入的 T1–T3 未见概念",
    "both_skills_add_unseen_concept": "generated 与 oracle 都补入未见概念",
    "model_adds_beyond_visible_evidence": "generated 自行补入未见概念",
    "missing_from_both_learning_and_oracle": "T1–T3、generated 与 oracle 都未覆盖",
}
MEASUREMENT_VALIDITY_ZH = {
    "history_supported": "高级要求均有 T1–T3 历史证据",
    "mixed_history_and_on_task": "部分来自历史，部分需现场处理",
    "on_task_only": "高级要求只在当前题面明示",
    "unseen_not_explicit": "历史未见且题面未充分明示",
    "missing_learning_evidence": "T1–T3 轨迹证据尚不完整",
    "unclassified_no_controlled_concept": "受控词表未覆盖",
}

CASE_DEFINITIONS = {
    "E2-LS1-T6": {
        "title": "Oracle 建议的 structured error 与隐藏 ValueError 契约冲突",
        "kind": "Oracle scope / hidden-contract 冲突",
        "interpretation": (
            "exact-oracle 的 pre-call skill 明确推荐返回 structured error；任务正文只说 missing fields "
            "should fail locally，没有声明 validate_record 必须抛 ValueError。Fable 按 skill 返回错误列表并在批处理中跳过，"
            "还修改 requests.json 构造公开测试所需的 invalid case；隐藏测试却直接要求 ValueError。"
            "这不是单纯的模型能力不足，而是 oracle 指导、可见契约和隐藏判分接口没有对齐。"
        ),
        "conditions": ["exact_oracle"],
        "files": ["transactions.py", "requests.json", "fallback_policy.py"],
    },
    "E2-LS2-T6": {
        "title": "注入的 retry skill 反而让 circuit-breaker 超额请求下游",
        "kind": "Oracle mapping 负迁移",
        "interpretation": (
            "该题要求 circuit breaker，但注入的两个 oracle skills 只覆盖固定三次重试和简单两步 API chain，"
            "完全没有 breaker 状态机知识。Fable 主动把三次 retry 与 breaker 组合，导致隐藏检查统计到过多 503；"
            "同时 cooldown 已按 recovery_timeout 正确实现，却因源码仍含 success_budget 字样被 process verifier 判失败。"
            "这里 exact-oracle 既缺关键知识，又引入了与目标约束冲突的动作。"
        ),
        "conditions": ["exact_oracle"],
        "files": ["breaker_client.py", "cooldown_policy.py"],
    },
    "E2-LS1-T5": {
        "title": "有效的模块化实现被单文件字面检查误判",
        "kind": "强假阴性证据",
        "interpretation": (
            "两模型都通过全部 outcome tests，并在 local_rules.py 实现本地校验，"
            "client.py 调用该函数；process verifier 却只读取 client.py 并搜索字面量 def validate。"
        ),
        "files": ["client.py", "local_rules.py"],
    },
    "E2-LS2-T5": {
        "title": "401/503 策略拆到辅助模块后被误判",
        "kind": "强假阴性证据",
        "interpretation": (
            "两模型都通过全部 outcome tests。状态码与 token_expired 分支位于 auth_policy.py，"
            "process verifier 只扫描 auth_client.py，因此把正确的职责分离判成缺失。"
        ),
        "files": ["auth_client.py", "auth_policy.py", "token_session.py"],
    },
    "E2-LS3-T6": {
        "title": "组合任务实现正确，但 verifier 要求逻辑集中在 solution.py",
        "kind": "强假阴性证据",
        "interpretation": (
            "两模型全部 outcome tests 通过；重试、去重、排序分别位于独立模块。"
            "process verifier 仅扫描 solution.py 的 503、seen/setdefault、sorted 等字面量。"
        ),
        "files": ["solution.py", "regional_sync.py", "retry_policy.py", "merge_index.py", "ordering_policy.py"],
    },
    "E2-LS5-T5": {
        "title": "功能过拟合当前输入，过程失败具有实际含义",
        "kind": "合理的过程约束",
        "interpretation": (
            "两模型当前 outcome tests 都通过，但 fetch_users.py 没有读取 api_docs.md，"
            "而是硬编码 schema。它可能通过当前数据却无法适应未来契约变化，不能当作 verifier 假阴性。"
        ),
        "files": ["fetch_users.py", "field_aliases.py", "compat_projection.py"],
    },
    "E2-LS5-T6": {
        "title": "等价的价格校验写法被字面量约束误判",
        "kind": "强假阴性证据",
        "interpretation": (
            "两模型用 price < 0 判非法，全部 outcome tests 通过；process verifier 要求源码必须包含"
            "字面量 price >= 0。这是语义等价实现的表面形式误判。"
        ),
        "files": ["record_validator.py", "fetch_products.py", "merge_policy.py"],
    },
}

CONCEPT_PATTERNS = {
    "exponential backoff": r"exponential(?:\s+backoff)?",
    "jitter": r"\bjitter\b",
    "Retry-After": r"retry-after",
    "idempotency": r"idempoten",
    "circuit breaker": r"circuit[- ]breaker|half[_ -]?open",
    "token refresh": (
        r"token(?:[_ -]+is)?[_ -]+expired|"
        r"refresh(?:es|ed|ing)?[_ -]+(?:the[_ -]+)?token|token[_ -]+refresh"
    ),
    "cursor pagination": r"cursor",
    "concurrent inserts/growth": r"concurrent(?:ly)?\s+insert|total[_ -]?growth|growing total",
    "deduplication": r"dedup|duplicate",
    "checksum": r"checksum|sha256|digest",
    "DST/IANA zone": r"\bdst\b|zoneinfo|iana|daylight saving",
    "meeting buffer": r"buffer[_ -]?minutes|buffer[- ]safe|buffer time",
    "soft preferences": r"soft[_ -]?preference",
    "thread history": r"thread[_ -]?history|earlier round|prior thread",
    "implicit action": r"implicit[_ -]?(?:action|delegation|commitment)",
    "relative dates": r"relative[_ -]?date|next occurrence|last monday|quarter",
    "source provenance": r"provenance|source[_ -]?(?:line|attribution)|evidence[_ -]?(?:map|source)",
    "conflict surfacing": r"conflict|disagreement|per-source",
    "roundtrip types": r"round[- ]?trip|type preservation|preserve.*(?:bool|null|leading.zero)",
    "cycle detection": r"cycle|circular reference|recursion stack",
    "locale-aware normalization": r"locale|umlaut|accent|unicode",
    "sentinel-aware nulls": r"sentinel|missing marker",
    "content fingerprint": r"fingerprint",
}

ENVIRONMENT_PROFILES = {
    "E1": {
        "name": "软件调试、依赖与多文件修复",
        "capability": "从症状定位根因，并在依赖升级、重构和跨层修改中保持行为与测试一致。",
        "provisional_read": (
            "现有 Fable 结果里，T5/T6 多数功能测试已经通过，strict 失败主要来自指定文件、"
            "指定 API 或覆盖率形态；真正的功能失败集中在数据库会话迁移与跨文件错误传播。"
            "因此 E1 当前更像 verifier 形态敏感与少量组合执行失败的混合，而不是 T5/T6 普遍不可解。"
        ),
    },
    "E2": {
        "name": "API 客户端可靠性与编排",
        "capability": "验证、鉴权、重试、分页、响应回退以及多步 API pipeline 的组合。",
        "provisional_read": (
            "两模型的 T5 outcome 均为 5/5，T6 outcome 均为 4/5；大量 strict 失败来自"
            "verifier 只扫描固定文件或要求特定字面量。E2 是目前最强的证据：低 strict 并不等于"
            "模型没有掌握功能。唯一稳定的功能缺口是 validate-normalize-enrich pipeline。"
        ),
    },
    "E3": {
        "name": "表格数据清洗、合并与校验",
        "capability": "schema 检查、类型归一化、join key 对齐、空值语义与结果一致性校验。",
        "provisional_read": (
            "T5 只有同一个 wrong-join-key trap 被两模型共同做错；T6 则在复合排序、模糊合并和"
            "多源空值规则上出现真实功能失败。这里更像单项 skill 能写进 library，但模型在组合任务中"
            "没有把多个不变量同时落实。"
        ),
    },
    "E4": {
        "name": "文档抽取、格式迁移与版本比较",
        "capability": "结构化抽取、跨格式保真、上下文填表、多版本 diff 与冲突保留。",
        "provisional_read": (
            "已审计的 Qwen run 中，T5/T6 outcome 都是 3/5。失败集中在矛盾值必须并列保留、缺失字段"
            "不得臆造、PDF→JSON→DOCX 数值保真和多轮版本变化覆盖，属于真实的文档语义与链式执行缺口。"
            "需等待 Fable 与 oracle/no-skill 对照判断是 skill 质量还是模型执行上限。"
        ),
    },
    "E5": {
        "name": "研究检索、证据归因与综合",
        "capability": "多源筛选、证据化比较、引用核验、受约束总结与矛盾审计。",
        "provisional_read": (
            "已审计的 Qwen run 中，T5 outcome 3/5、T6 outcome 1/5。主要问题是没有读取 grounding files、"
            "丢失 provenance、引用问题标签不精确，以及一个 pipeline 直接运行失败；这不是单纯"
            "process verifier 噪声。"
        ),
    },
    "E6": {
        "name": "邮件、会议与行动项工作流",
        "capability": "优先级判断、上下文回复、行动项抽取、时区排期以及 thread 级综合。",
        "provisional_read": (
            "两模型 T6 outcome 都是 0/5，且失败横跨优先级、必含内容、隐式行动、DST 排期和状态汇总。"
            "generated skills 往往已经写到这些概念，但执行产物仍不符合契约；同时部分 curated oracle"
            "只覆盖基础 fixed-offset/explicit-action 流程。E6 是最需要 exact-oracle 与 no-skill 解耦的环境。"
        ),
    },
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def load_json_optional(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return load_json(path)


def load_yaml_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def protocol_design_audit(audit: dict[str, Any]) -> dict[str, Any]:
    tasks_root = Path(str(audit.get("tasks_root") or "benchmark/tasks"))
    skills_root = tasks_root.parent / "skills"
    role_counts: Counter[str] = Counter()
    for path in tasks_root.glob("*/task-spec.yaml"):
        spec = load_yaml_optional(path)
        if not spec:
            continue
        role_counts[
            f"T{spec.get('task_index')}:{spec.get('role')}:{spec.get('phase')}"
        ] += 1

    skill_metas = [
        meta
        for path in skills_root.glob("*/meta.yaml")
        if (meta := load_yaml_optional(path))
    ]
    gap_summaries = [
        str(meta.get(key) or "")
        for meta in skill_metas
        for key in ("gap_1_summary", "gap_2_summary")
        if meta.get(key)
    ]
    return {
        "family_count": len(skill_metas),
        "gap_summary_count": len(gap_summaries),
        "gap_summaries_explicitly_limiting_curated": sum(
            "curated skill" in summary.lower() for summary in gap_summaries
        ),
        "role_counts": dict(sorted(role_counts.items())),
        "exact_oracle_semantics": (
            "gold task-to-skill selection over deliberately gap-exposed curated "
            "skills; not an oracle solution or a guaranteed sufficient policy"
        ),
    }


def rate(passed: int, total: int) -> float | None:
    return passed / total if total else None


def pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.1f}%"


def wilson(passed: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if not total:
        return None
    center = (passed + z * z / 2) / (total + z * z)
    margin = z * math.sqrt((passed * (total - passed) / total + z * z / 4) / total) / (total + z * z)
    return max(0.0, center - margin), min(1.0, center + margin)


def selected_rows(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row for row in evidence.get("tasks", [])
        if isinstance(row, dict) and row.get("selected_run", True)
    ]


def selected_runs(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row for row in evidence.get("runs", [])
        if isinstance(row, dict) and row.get("selected_run", True)
    ]


def condition_coverage(rows: list[dict[str, Any]], runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["model"], row["condition"], row["environment_id"])].append(row)
    run_map = {(run["model"], run["condition"], run["environment_id"]): run for run in runs}
    result = []
    for model in MODELS:
        for condition in CONDITIONS:
            for env in ENVS:
                key = (model, condition, env)
                task_rows = grouped[key]
                n = len(task_rows)
                run = run_map.get(key)
                if condition == "exact_oracle":
                    invalid_tasks = [row["task_id"] for row in task_rows if row.get("oracle_injection_exact") is not True]
                elif condition == "no_skill":
                    invalid_tasks = [row["task_id"] for row in task_rows if row.get("no_skill_empty") is not True]
                elif condition == "curated_all":
                    invalid_tasks = [
                        row["task_id"]
                        for row in task_rows
                        if row.get("curated_all_library_complete") is not True
                    ]
                else:
                    invalid_tasks = []
                protocol_valid = not invalid_tasks
                result.append({
                    "model": model,
                    "condition": condition,
                    "environment_id": env,
                    "observed": n,
                    "expected": EXPECTED_TASKS_PER_ENV,
                    "complete": n == EXPECTED_TASKS_PER_ENV and protocol_valid,
                    "protocol_valid": protocol_valid,
                    "protocol_invalid_tasks": invalid_tasks,
                    "job_id": run.get("job_id") if run else None,
                    "ap_status": run.get("ap_status") if run else "missing",
                })
    return result


def aggregates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["model"], row["condition"], row["environment_id"], int(row["tier"]))].append(row)
    result = []
    for key, group in sorted(grouped.items()):
        model, condition, env, tier = key
        n = len(group)
        strict = sum(row.get("strict_pass") is True for row in group)
        outcome = sum(row.get("outcome_pass") is True for row in group)
        process = sum(row.get("process_pass") is True for row in group)
        result.append({
            "model": model, "condition": condition, "environment_id": env, "tier": tier,
            "n": n, "strict": strict, "outcome": outcome, "process": process,
            "strict_rate": rate(strict, n), "outcome_rate": rate(outcome, n), "process_rate": rate(process, n),
            "classifications": dict(Counter(str(row.get("classification")) for row in group)),
        })
    return result


def task_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(row["model"], row["condition"], row["task_id"]): row for row in rows}
    result = []
    task_ids = sorted({row["task_id"] for row in rows if int(row["tier"]) in TIERS})
    for model in MODELS:
        for task_id in task_ids:
            conditions = {condition: indexed.get((model, condition, task_id)) for condition in CONDITIONS}
            if not any(conditions.values()):
                continue
            base = next(row for row in conditions.values() if row)
            self_row = conditions["self_generated"]
            oracle = conditions["exact_oracle"]
            verdict = "awaiting_matched_controls"
            if self_row and oracle:
                if oracle.get("outcome_pass") is not True:
                    verdict = "oracle_outcome_failure"
                elif self_row.get("outcome_pass") is not True:
                    verdict = "oracle_rescues_outcome"
                elif oracle.get("strict_pass") is True and self_row.get("strict_pass") is not True:
                    verdict = "oracle_rescues_strict_only"
                else:
                    verdict = "no_oracle_rescue_needed_or_observed"
            condition_payload = {
                name: ({
                    "strict": row.get("strict_pass"),
                    "outcome": row.get("outcome_pass"),
                    "process": row.get("process_pass"),
                    "score": row.get("normalized_score"),
                    "classification": row.get("classification"),
                    "oracle_injection_exact": row.get("oracle_injection_exact"),
                    "oracle_content_verification": row.get(
                        "oracle_content_verification"
                    ) or {},
                    "oracle_skill_ids": row.get("oracle_skill_ids") or [],
                    "skills_actually_used": row.get("skills_actually_used") or [],
                    "no_skill_empty": row.get("no_skill_empty"),
                    "curated_all_library_complete": row.get(
                        "curated_all_library_complete"
                    ),
                    "curated_all_visible_slugs": row.get(
                        "curated_all_visible_slugs"
                    ) or [],
                    "failed_tests": row.get("failed_tests") or [],
                    "job_id": row.get("job_id"),
                    "record_path": row.get("record_path"),
                    "trajectory_path": row.get("local_trajectory_path"),
                    "artifact_path": row.get("local_artifact_task_path"),
                } if row else None)
                for name, row in conditions.items()
            }
            result.append({
                "model": model,
                "task_id": task_id,
                "environment_id": base["environment_id"],
                "tier": int(base["tier"]),
                "task_slug": base.get("task_slug"),
                "primary_skill": base.get("primary_skill"),
                "required_skills": base.get("required_skills") or [],
                "verdict": verdict,
                "conditions": condition_payload,
                "causal": causal_diagnosis(condition_payload),
            })
    return result


def causal_diagnosis(
    conditions: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    if any(conditions.get(name) is None for name in CONDITIONS):
        observed = sum(conditions.get(name) is not None for name in CONDITIONS)
        return {
            "complete": False,
            "category": "awaiting_four_conditions",
            "label": "等待四条件",
            "pattern": None,
            "explanation": f"当前只有 {observed}/4 个匹配条件，禁止作因果判定。",
        }

    outcomes = {
        name: conditions[name].get("outcome") is True  # type: ignore[union-attr]
        for name in CONDITIONS
    }
    self_pass = outcomes["self_generated"]
    exact_pass = outcomes["exact_oracle"]
    all_pass = outcomes["curated_all"]
    no_skill_pass = outcomes["no_skill"]
    pattern = " ".join(
        f"{short}={'1' if outcomes[name] else '0'}"
        for short, name in (
            ("S", "self_generated"),
            ("E", "exact_oracle"),
            ("A", "curated_all"),
            ("N", "no_skill"),
        )
    )

    if no_skill_pass:
        if self_pass and exact_pass and all_pass:
            category = "low_skill_demand"
            label = "无需 skill 也能做"
            explanation = "四条件均通过；该题不能提供强 skill-evolve 增益证据。"
        elif not self_pass:
            category = "self_generated_harm"
            label = "生成 skill 造成干扰"
            explanation = "无 skill 通过而 self-generated 失败，生成 skill 对本题产生负迁移。"
        else:
            category = "curated_skill_harm_or_selection_noise"
            label = "Curated/选择造成干扰"
            explanation = "无 skill 已通过，但至少一种 curated 条件失败；skill 内容或选择引入干扰。"
    elif self_pass:
        category = "self_evolution_benefit"
        label = "生成 skill 带来增益"
        explanation = "无 skill 失败而 self-generated 通过，是直接的 skill-evolve 正向证据。"
    elif exact_pass and all_pass:
        category = "curated_content_benefit_generated_gap"
        label = "Curated 内容有效，生成 skill 不足"
        explanation = "无 skill 与 self-generated 失败，但 exact 和 curated-all 均通过；主要差距在生成 skill 内容。"
    elif exact_pass and not all_pass:
        category = "annotation_selection_prior"
        label = "Gold 子集选择/注意力优势"
        explanation = (
            "只有 exact-oracle 通过；gold task→skill 子集减少了选择与阅读负担。"
            "该差值不能进一步区分标注映射信息和注意力/搜索成本。"
        )
    elif all_pass:
        category = "all_library_helps_gold_subset_insufficient"
        label = "全库有益，Gold 子集不足"
        explanation = "curated-all 通过但 exact-oracle 失败；gold 子集可能遗漏有用 skill，或选择造成干扰。"
    else:
        category = "all_model_conditions_fail"
        label = "四种模型条件都失败"
        explanation = "官方标准解可通过时，这表示模型执行上限、oracle scope 不足或任务难度；不能单凭此判题目坏。"
    return {
        "complete": True,
        "category": category,
        "label": label,
        "pattern": pattern,
        "explanation": explanation,
    }


def causal_diagnosis_summary(
    comparisons: list[dict[str, Any]],
) -> dict[str, Any]:
    records = [row for row in comparisons if int(row["tier"]) in (5, 6)]
    complete = [row for row in records if row["causal"]["complete"]]
    return {
        "expected": len(MODELS) * len(ENVS) * 5 * 2,
        "observed": len(records),
        "complete": len(complete),
        "category_counts": dict(
            Counter(row["causal"]["category"] for row in complete)
        ),
    }


def skill_use_adherence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for model in MODELS:
        for condition in CONDITIONS:
            for tier in TIERS:
                group = [
                    row
                    for row in rows
                    if row.get("model") == model
                    and row.get("condition") == condition
                    and int(row.get("tier", -1)) == tier
                ]
                any_use = [bool(row.get("skills_actually_used")) for row in group]
                used_rows = [row for row, used in zip(group, any_use) if used]
                unused_rows = [row for row, used in zip(group, any_use) if not used]
                exact_full_use: int | None = None
                if condition == "exact_oracle":
                    exact_full_use = sum(
                        set(row.get("oracle_skill_ids") or []).issubset(
                            set(row.get("skills_actually_used") or [])
                        )
                        for row in group
                    )
                result.append(
                    {
                        "model": model,
                        "condition": condition,
                        "tier": tier,
                        "n": len(group),
                        "any_skill_used": sum(any_use),
                        "exact_expected_skills_fully_used": exact_full_use,
                        "used_outcome_passed": sum(
                            row.get("outcome_pass") is True for row in used_rows
                        ),
                        "used_n": len(used_rows),
                        "unused_outcome_passed": sum(
                            row.get("outcome_pass") is True for row in unused_rows
                        ),
                        "unused_n": len(unused_rows),
                    }
                )
    return result


def matched_effects(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    contrasts = (
        ("exact_oracle", "self_generated"),
        ("self_generated", "no_skill"),
        ("exact_oracle", "no_skill"),
        ("exact_oracle", "curated_all"),
        ("curated_all", "no_skill"),
        ("curated_all", "self_generated"),
    )
    for model in MODELS:
        for tier in TIERS:
            group = [row for row in comparisons if row["model"] == model and row["tier"] == tier]
            for treatment, reference in contrasts:
                for metric in ("strict", "outcome", "process"):
                    matched = [
                        row for row in group
                        if row["conditions"][treatment] is not None
                        and row["conditions"][reference] is not None
                    ]
                    treatment_pass = sum(row["conditions"][treatment][metric] is True for row in matched)
                    reference_pass = sum(row["conditions"][reference][metric] is True for row in matched)
                    rescued = sum(
                        row["conditions"][reference][metric] is not True
                        and row["conditions"][treatment][metric] is True
                        for row in matched
                    )
                    harmed = sum(
                        row["conditions"][reference][metric] is True
                        and row["conditions"][treatment][metric] is not True
                        for row in matched
                    )
                    result.append({
                        "model": model, "tier": tier, "metric": metric,
                        "treatment": treatment, "reference": reference,
                        "n": len(matched), "treatment_pass": treatment_pass,
                        "reference_pass": reference_pass,
                        "delta": rate(treatment_pass - reference_pass, len(matched)),
                        "rescued": rescued, "harmed": harmed,
                    })
    return result


def exact_sign_test(left_only: int, right_only: int) -> float | None:
    discordant = left_only + right_only
    if not discordant:
        return None
    tail = sum(math.comb(discordant, k) for k in range(min(left_only, right_only) + 1)) / (2**discordant)
    return min(1.0, 2.0 * tail)


def model_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(row["model"], row["condition"], row["task_id"]): row for row in rows}
    result = []
    for condition in CONDITIONS:
        for tier in TIERS:
            task_ids = sorted({
                row["task_id"] for row in rows
                if row["condition"] == condition and int(row["tier"]) == tier
                and all((model, condition, row["task_id"]) in indexed for model in MODELS)
            })
            for metric in ("strict_pass", "outcome_pass", "process_pass"):
                pairs = [
                    (indexed[(MODELS[0], condition, task_id)], indexed[(MODELS[1], condition, task_id)])
                    for task_id in task_ids
                ]
                left = sum(pair[0].get(metric) is True for pair in pairs)
                right = sum(pair[1].get(metric) is True for pair in pairs)
                left_only = sum(pair[0].get(metric) is True and pair[1].get(metric) is not True for pair in pairs)
                right_only = sum(pair[1].get(metric) is True and pair[0].get(metric) is not True for pair in pairs)
                result.append({
                    "condition": condition,
                    "tier": tier,
                    "metric": metric.removesuffix("_pass"),
                    "n": len(pairs),
                    "qwen_pass": left,
                    "fable_pass": right,
                    "qwen_only": left_only,
                    "fable_only": right_only,
                    "both_pass": sum(pair[0].get(metric) is True and pair[1].get(metric) is True for pair in pairs),
                    "neither_pass": sum(pair[0].get(metric) is not True and pair[1].get(metric) is not True for pair in pairs),
                    "sign_test_p": exact_sign_test(left_only, right_only),
                })
    return result


def failure_map(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for model in MODELS:
        for env in ENVS:
            for tier in (5, 6):
                group = [
                    row for row in rows
                    if row.get("model") == model
                    and row.get("condition") == "self_generated"
                    and row.get("environment_id") == env
                    and int(row.get("tier", 0)) == tier
                ]
                failed = [row for row in group if row.get("strict_pass") is not True]
                result.append({
                    "model": model,
                    "environment_id": env,
                    "tier": tier,
                    "observed": len(group),
                    "strict_failures": len(failed),
                    "classifications": dict(Counter(str(row.get("classification")) for row in group)),
                    "tasks": [
                        {
                            "task_id": row["task_id"],
                            "task_slug": row.get("task_slug"),
                            "primary_skill": row.get("primary_skill"),
                            "required_skills": row.get("required_skills") or [],
                            "classification": row.get("classification"),
                            "failed_outcome": [
                                {"name": item.get("name"), "message": item.get("message")}
                                for item in row.get("failed_outcome_tests") or []
                            ],
                            "failed_process": [
                                {"name": item.get("name"), "message": item.get("message")}
                                for item in row.get("failed_process_tests") or []
                            ],
                        }
                        for row in failed
                    ],
                })
    return result


def build_cases(rows: list[dict[str, Any]], audit: dict[str, Any], raw_root: Path) -> list[dict[str, Any]]:
    audit_by_id = {row["task_id"]: row for row in audit.get("tasks", [])}
    result = []
    for task_id, definition in CASE_DEFINITIONS.items():
        verifier = audit_by_id.get(task_id, {})
        observations = []
        conditions = set(definition.get("conditions", ["self_generated"]))
        for row in rows:
            if row.get("task_id") != task_id or row.get("condition") not in conditions:
                continue
            files = []
            rel = row.get("local_artifact_task_path")
            if rel:
                task_root = raw_root / rel
                for name in definition["files"]:
                    path = task_root / name
                    if path.exists():
                        files.append({
                            "name": name,
                            "path": str(path.resolve()),
                            "content": path.read_text(encoding="utf-8", errors="replace"),
                        })
            observations.append({
                "model": row["model"],
                "condition": row.get("condition"),
                "strict": row.get("strict_pass"),
                "outcome": row.get("outcome_pass"),
                "process": row.get("process_pass"),
                "score": row.get("normalized_score"),
                "failed_process_tests": row.get("failed_process_tests") or [],
                "files": files,
            })
        if not observations:
            continue
        process_path = Path(str(verifier.get("process", {}).get("path", "")))
        result.append({
            "task_id": task_id,
            **definition,
            "process_verifier_path": str(process_path) if process_path else None,
            "process_verifier": (
                process_path.read_text(encoding="utf-8", errors="replace")
                if process_path.is_file() else ""
            ),
            "observations": observations,
        })
    return result


def skill_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    skills = [
        row for row in evidence.get("skills", [])
        if isinstance(row, dict) and row.get("selected_run", True) and row.get("condition") == "self_generated"
    ]
    result: dict[str, Any] = {"rows": skills, "by_model": {}}
    for model in MODELS:
        group = [row for row in skills if row.get("model") == model]
        jac = sorted(float(row["word_jaccard"]) for row in group if row.get("word_jaccard") is not None)
        ratios = sorted(
            row["generated_chars"] / row["curated_chars"]
            for row in group if row.get("curated_chars")
        )
        result["by_model"][model] = {
            "n": len(group),
            "renamed": sum(row.get("renamed_from_oracle") is True for row in group),
            "exact_equal": sum(row.get("exact_equal") is True for row in group),
            "median_word_jaccard": median(jac) if jac else None,
            "median_length_ratio": median(ratios) if ratios else None,
        }
    return result


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()))


def token_recall(reference: str, evidence: str) -> float | None:
    reference_tokens = tokens(reference)
    return len(reference_tokens & tokens(evidence)) / len(reference_tokens) if reference_tokens else None


def detected_concepts(text: str) -> list[str]:
    return [
        name
        for name, pattern in CONCEPT_PATTERNS.items()
        if re.search(pattern, text, re.IGNORECASE)
    ]


def learning_analysis(evidence: dict[str, Any]) -> dict[str, Any]:
    learning = [
        row for row in evidence.get("learning_tasks", [])
        if isinstance(row, dict) and row.get("selected_run", True)
    ]
    skills = [
        row for row in evidence.get("skills", [])
        if isinstance(row, dict)
        and row.get("selected_run", True)
        and row.get("condition") == "self_generated"
    ]
    marker_re = re.compile(
        r"\b(?:verifier|process tests?|hidden tests?|source-visible|source scan|"
        r"grep|literal(?:ly)?|static analysis|rubric)\b",
        re.IGNORECASE,
    )
    by_model: dict[str, Any] = {}
    for model in MODELS:
        tasks = [row for row in learning if row.get("model") == model]
        model_skills = [row for row in skills if row.get("model") == model]
        family_counts = Counter(str(row.get("family_id")) for row in model_skills)
        unique_oracles = {
            str(row.get("expected_oracle_skill_slug")): str(row.get("curated_text") or "")
            for row in model_skills
        }
        by_model[model] = {
            "learning_tasks": len(tasks),
            "learning_attempts": sum(int(row.get("learning_attempts") or 0) for row in tasks),
            "terminal_strict_passes": sum(row.get("terminal_verifier_passed") is True for row in tasks),
            "repaired_to_pass": sum(row.get("repaired_to_pass") is True for row in tasks),
            "same_session_failures": sum(row.get("all_attempts_same_session_verified") is not True for row in tasks),
            "active_skills": len(model_skills),
            "families": len(family_counts),
            "families_with_multiple_skills": sum(count > 1 for count in family_counts.values()),
            "skills_with_verifier_markers": sum(bool(marker_re.search(str(row.get("generated_text") or ""))) for row in model_skills),
            "oracle_skills_with_verifier_markers": sum(bool(marker_re.search(text)) for text in unique_oracles.values()),
        }

    family_rows = []
    keys = sorted({(str(row.get("model")), str(row.get("family_id"))) for row in skills})
    for model, family_id in keys:
        generated = [row for row in skills if row.get("model") == model and str(row.get("family_id")) == family_id]
        observed = [row for row in learning if row.get("model") == model and str(row.get("family_id")) == family_id]
        if not generated:
            continue
        curated_text = str(generated[0].get("curated_text") or "")
        generated_text = "\n\n".join(str(row.get("generated_text") or "") for row in generated)
        learning_text = "\n".join(
            str(part)
            for row in observed
            for part in (
                row.get("instruction") or "",
                json.dumps(row.get("failed_tests") or [], ensure_ascii=False),
                json.dumps(row.get("reflection_feedback") or {}, ensure_ascii=False),
            )
        )
        family_rows.append({
            "model": model,
            "environment_id": generated[0].get("environment_id"),
            "family_id": family_id,
            "learning_task_count": len(observed),
            "learning_attempts": sum(int(row.get("learning_attempts") or 0) for row in observed),
            "terminal_strict_passes": sum(row.get("terminal_verifier_passed") is True for row in observed),
            "repaired_to_pass": sum(row.get("repaired_to_pass") is True for row in observed),
            "generated_skill_count": len(generated),
            "generated_slugs": [str(row.get("skill_slug")) for row in generated],
            "generated_versions": [row.get("current_version") for row in generated],
            "expected_oracle_slug": generated[0].get("expected_oracle_skill_slug"),
            "best_word_jaccard": max((float(row.get("word_jaccard") or 0.0) for row in generated), default=0.0),
            "oracle_token_recall_from_learning_evidence": token_recall(curated_text, learning_text),
            "generated_token_recall_from_learning_evidence": token_recall(generated_text, learning_text),
            "generated_verifier_marker_hits": len(marker_re.findall(generated_text)),
            "oracle_verifier_marker_hits": len(marker_re.findall(curated_text)),
            "learning_concepts": detected_concepts(learning_text),
            "generated_concepts": detected_concepts(generated_text),
            "curated_concepts": detected_concepts(curated_text),
            "curated_text": curated_text,
            "generated_text": generated_text,
            "learning_evidence_excerpt": learning_text[:12000],
        })
    for model in MODELS:
        complete = [
            row for row in family_rows
            if row["model"] == model and row["learning_task_count"] == 3
        ]
        for key in (
            "oracle_token_recall_from_learning_evidence",
            "generated_token_recall_from_learning_evidence",
            "best_word_jaccard",
        ):
            values = sorted(float(row[key]) for row in complete if row.get(key) is not None)
            by_model[model][f"median_{key}"] = median(values) if values else None
    return {"by_model": by_model, "families": family_rows}


def derivability_analysis(
    learning: dict[str, Any],
    oracle_scope: dict[str, Any],
) -> dict[str, Any]:
    families = {
        (str(row.get("model")), str(row.get("family_id"))): row
        for row in learning.get("families", [])
        if isinstance(row, dict)
    }
    records = []
    for task in oracle_scope.get("rows", []):
        task_id = str(task.get("task_id") or "")
        match = re.match(r"^(E\d+-LS\d+)-T[456]$", task_id)
        if not match:
            continue
        primary_family_id = match.group(1)
        family_ids = list(
            dict.fromkeys(
                str(skill_id).split(".", 1)[0]
                for skill_id in (task.get("oracle_skill_ids") or [])
                if str(skill_id).strip()
            )
        ) or [primary_family_id]
        for model in MODELS:
            task_families = [families.get((model, family_id)) for family_id in family_ids]
            if any(family is None for family in task_families):
                continue
            learning_concepts = {
                concept
                for family in task_families
                for concept in (family or {}).get("learning_concepts", [])
            }
            generated_concepts = {
                concept
                for family in task_families
                for concept in (family or {}).get("generated_concepts", [])
            }
            curated_concepts = set(task.get("oracle_concepts") or [])
            author_gap_concepts = set(task.get("author_gap_concepts") or [])
            for concept in task.get("task_concepts") or []:
                in_learning = concept in learning_concepts
                in_generated = concept in generated_concepts
                in_oracle = concept in curated_concepts
                in_author_gap = concept in author_gap_concepts
                if in_learning:
                    if in_generated:
                        category = "captured_from_visible_evidence"
                    elif in_oracle:
                        category = "oracle_captures_visible_generated_misses"
                    else:
                        category = "visible_missing_from_both_skills"
                elif in_generated and in_oracle:
                    category = "both_skills_add_unseen_concept"
                elif in_oracle:
                    category = "oracle_adds_unseen_concept"
                elif in_generated:
                    category = "model_adds_beyond_visible_evidence"
                else:
                    category = "missing_from_both_learning_and_oracle"
                records.append(
                    {
                        "model": model,
                        "environment_id": task.get("environment_id"),
                        "family_id": primary_family_id,
                        "source_family_ids": family_ids,
                        "task_id": task_id,
                        "tier": task.get("tier"),
                        "concept": concept,
                        "in_t1_t3_evidence": in_learning,
                        "in_generated_skill": in_generated,
                        "in_curated_oracle": in_oracle,
                        "in_author_gap_metadata": in_author_gap,
                        "category": category,
                    }
                )
    summaries = []
    for model in MODELS:
        selected = [row for row in records if row["model"] == model]
        summaries.append(
            {
                "model": model,
                "concept_instances": len(selected),
                "category_counts": dict(Counter(row["category"] for row in selected)),
                "author_gap_metadata_hits": sum(
                    row["in_author_gap_metadata"] for row in selected
                ),
                "author_gap_unseen_in_t1_t3": sum(
                    row["in_author_gap_metadata"]
                    and not row["in_t1_t3_evidence"]
                    for row in selected
                ),
                "author_gap_missing_from_all_model_visible_sources": sum(
                    row["in_author_gap_metadata"]
                    and not row["in_t1_t3_evidence"]
                    and not row["in_generated_skill"]
                    and not row["in_curated_oracle"]
                    for row in selected
                ),
            }
        )
    return {
        "method": (
            "controlled concept-pattern screen over T5/T6 instructions and verifier check "
            "names versus T1-T3 visible instructions/feedback and both skill texts"
        ),
        "records": records,
        "summaries": summaries,
    }


def measurement_validity_analysis(
    derivability: dict[str, Any],
    oracle_scope: dict[str, Any],
) -> dict[str, Any]:
    """Screen whether each held-out task can identify historical skill transfer."""
    indexed: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in derivability.get("records", []):
        if isinstance(row, dict):
            indexed[(str(row.get("model")), str(row.get("task_id")))].append(row)

    records: list[dict[str, Any]] = []
    for task in oracle_scope.get("rows", []):
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id") or "")
        concepts = list(dict.fromkeys(task.get("task_concepts") or []))
        instruction_concepts = set(task.get("instruction_concepts") or [])
        oracle_concepts = set(task.get("oracle_concepts") or [])
        for model in MODELS:
            concept_rows = indexed.get((model, task_id), [])
            if not concepts:
                category = "unclassified_no_controlled_concept"
            elif not concept_rows:
                category = "missing_learning_evidence"
            else:
                visible = sum(
                    row.get("in_t1_t3_evidence") is True for row in concept_rows
                )
                if visible == len(concepts):
                    category = "history_supported"
                elif visible > 0:
                    category = "mixed_history_and_on_task"
                elif set(concepts) <= instruction_concepts:
                    category = "on_task_only"
                else:
                    category = "unseen_not_explicit"

            generated_count = sum(
                row.get("in_generated_skill") is True for row in concept_rows
            )
            oracle_count = sum(concept in oracle_concepts for concept in concepts)

            def coverage_label(count: int) -> str:
                if not concepts:
                    return "unclassified"
                if count == len(concepts):
                    return "all"
                if count:
                    return "partial"
                return "none"

            records.append(
                {
                    "model": model,
                    "environment_id": task.get("environment_id"),
                    "task_id": task_id,
                    "tier": task.get("tier"),
                    "task_slug": task.get("task_slug"),
                    "category": category,
                    "controlled_concepts": concepts,
                    "history_visible_count": sum(
                        row.get("in_t1_t3_evidence") is True
                        for row in concept_rows
                    ),
                    "instruction_explicit_count": sum(
                        concept in instruction_concepts for concept in concepts
                    ),
                    "generated_coverage": coverage_label(generated_count),
                    "oracle_coverage": coverage_label(oracle_count),
                    "author_gap_concepts": task.get("task_concepts_in_author_gaps")
                    or [],
                    "eligible_for_causal_skill_claim": category
                    in {"history_supported", "mixed_history_and_on_task"},
                }
            )

    summaries = []
    for model in MODELS:
        selected = [row for row in records if row["model"] == model]
        summaries.append(
            {
                "model": model,
                "task_count": len(selected),
                "controlled_task_count": sum(
                    row["category"] != "unclassified_no_controlled_concept"
                    for row in selected
                ),
                "category_counts": dict(
                    sorted(Counter(row["category"] for row in selected).items())
                ),
                "eligible_for_causal_skill_claim": sum(
                    row["eligible_for_causal_skill_claim"] for row in selected
                ),
                "oracle_all_concepts": sum(
                    row["oracle_coverage"] == "all" for row in selected
                ),
                "generated_all_concepts": sum(
                    row["generated_coverage"] == "all" for row in selected
                ),
            }
        )
    by_environment = []
    for model in MODELS:
        for environment_id in ENVS:
            selected = [
                row
                for row in records
                if row["model"] == model
                and row["environment_id"] == environment_id
            ]
            by_environment.append(
                {
                    "model": model,
                    "environment_id": environment_id,
                    "task_count": len(selected),
                    "controlled_task_count": sum(
                        row["category"] != "unclassified_no_controlled_concept"
                        for row in selected
                    ),
                    "category_counts": dict(
                        sorted(Counter(row["category"] for row in selected).items())
                    ),
                    "eligible_for_causal_skill_claim": sum(
                        row["eligible_for_causal_skill_claim"] for row in selected
                    ),
                }
            )
    return {
        "method": (
            "controlled-concept screen only; causal skill claims additionally require "
            "matched no-skill and treatment outcomes"
        ),
        "records": records,
        "summaries": summaries,
        "by_environment": by_environment,
    }


def oracle_scope_analysis(audit: dict[str, Any]) -> dict[str, Any]:
    tasks_root = Path(str(audit.get("tasks_root") or "benchmark/tasks"))
    skills_root = tasks_root.parent / "skills"
    rows = []
    for task in audit.get("tasks", []):
        if not isinstance(task, dict) or int(task.get("tier", 0)) not in {5, 6}:
            continue
        skill_ids = (
            list(task.get("required_skills") or [])
            if int(task["tier"]) == 6
            else [str(task.get("primary_skill"))]
        )
        oracle_parts = []
        oracle_paths = []
        meta_gap_parts = []
        meta_paths = []
        for skill_id in skill_ids:
            slug = skill_id.split(".", 1)[-1]
            path = skills_root / slug / "SKILL.md"
            if path.exists():
                oracle_parts.append(path.read_text(encoding="utf-8"))
                oracle_paths.append(str(path.resolve()))
            meta_path = skills_root / slug / "meta.yaml"
            meta = load_yaml_optional(meta_path)
            gap_values = [
                str(value)
                for key, value in sorted(meta.items())
                if str(key).startswith("gap_") and str(value).strip()
            ]
            if gap_values:
                meta_gap_parts.extend(gap_values)
                meta_paths.append(str(meta_path.resolve()))
        oracle_text = "\n\n".join(oracle_parts)
        meta_gap_text = "\n\n".join(meta_gap_parts)
        check_names = [
            str(name)
            for key in ("process", "outcome")
            for name in (task.get(key) or {}).get("check_names", [])
        ]
        instruction_surface = str(task.get("instruction") or "")
        verifier_surface = "\n".join(check_names)
        task_surface = instruction_surface + "\n" + verifier_surface
        task_concepts = [
            name for name, pattern in CONCEPT_PATTERNS.items()
            if re.search(pattern, task_surface, re.IGNORECASE)
        ]
        instruction_concepts = [
            name for name, pattern in CONCEPT_PATTERNS.items()
            if re.search(pattern, instruction_surface, re.IGNORECASE)
        ]
        verifier_concepts = [
            name for name, pattern in CONCEPT_PATTERNS.items()
            if re.search(pattern, verifier_surface, re.IGNORECASE)
        ]
        verifier_only_concepts = sorted(
            set(verifier_concepts) - set(instruction_concepts)
        )
        oracle_concepts = [
            name for name, pattern in CONCEPT_PATTERNS.items()
            if re.search(pattern, oracle_text, re.IGNORECASE)
        ]
        meta_gap_concepts = [
            name for name, pattern in CONCEPT_PATTERNS.items()
            if re.search(pattern, meta_gap_text, re.IGNORECASE)
        ]
        missing = sorted(set(task_concepts) - set(oracle_concepts))
        scope_lines = [
            line.strip() for line in oracle_text.splitlines()
            if line.strip().lower().startswith("scope:")
        ]
        restrictive = bool(re.search(
            r"\b(?:deliberately basic|simple|fixed delay|fixed utc offset|"
            r"two time zones|single-request|flat-format|one or two context)\b",
            oracle_text,
            re.IGNORECASE,
        ))
        risk = "high" if len(missing) >= 2 or (restrictive and missing) else "medium" if missing or restrictive else "low"
        rows.append({
            "task_id": task["task_id"],
            "environment_id": task.get("environment_id"),
            "tier": int(task["tier"]),
            "task_slug": task.get("task_slug"),
            "oracle_skill_ids": skill_ids,
            "oracle_paths": oracle_paths,
            "author_meta_paths": meta_paths,
            "task_concepts": task_concepts,
            "instruction_concepts": instruction_concepts,
            "verifier_concepts": verifier_concepts,
            "verifier_only_concepts": verifier_only_concepts,
            "oracle_concepts": oracle_concepts,
            "author_gap_concepts": meta_gap_concepts,
            "task_concepts_in_author_gaps": sorted(
                set(task_concepts) & set(meta_gap_concepts)
            ),
            "missing_concepts": missing,
            "restrictive_scope_language": restrictive,
            "scope_lines": scope_lines,
            "scope_risk": risk,
        })
    concept_rows = [
        (row, concept)
        for row in rows
        for concept in row["task_concepts"]
    ]
    return {
        "method": "heuristic screening; high-risk cases require manual task/skill review",
        "counts": dict(Counter(row["scope_risk"] for row in rows)),
        "concept_visibility": {
            "task_count": len(rows),
            "tasks_with_controlled_concepts": sum(
                bool(row["task_concepts"]) for row in rows
            ),
            "concept_instances": len(concept_rows),
            "instruction_explicit_instances": sum(
                concept in row["instruction_concepts"]
                for row, concept in concept_rows
            ),
            "verifier_only_instances": sum(
                concept in row["verifier_only_concepts"]
                for row, concept in concept_rows
            ),
            "tasks_with_verifier_only_concepts": sum(
                bool(row["verifier_only_concepts"]) for row in rows
            ),
            "author_gap_metadata_instances": sum(
                concept in row["author_gap_concepts"]
                for row, concept in concept_rows
            ),
            "tasks_with_author_gap_metadata_hits": sum(
                bool(row["task_concepts_in_author_gaps"]) for row in rows
            ),
        },
        "rows": rows,
    }


def verifier_shape_outcomes(rows: list[dict[str, Any]], audit: dict[str, Any]) -> list[dict[str, Any]]:
    risk_by_task = {
        str(task["task_id"]): str(task.get("process_shape_sensitivity") or "unknown")
        for task in audit.get("tasks", []) if isinstance(task, dict)
    }
    result = []
    for condition in CONDITIONS:
        for risk in ("high", "medium", "low"):
            group = [
                row for row in rows
                if row.get("condition") == condition
                and risk_by_task.get(str(row.get("task_id"))) == risk
            ]
            result.append({
                "condition": condition,
                "shape_risk": risk,
                "n": len(group),
                "process_only_failures": sum(row.get("classification") == "process_only_failure" for row in group),
                "outcome_passes": sum(row.get("outcome_pass") is True for row in group),
                "process_passes": sum(row.get("process_pass") is True for row in group),
                "strict_passes": sum(row.get("strict_pass") is True for row in group),
            })
    return result


def scope_condition_outcomes(
    comparisons: list[dict[str, Any]],
    oracle_scope: dict[str, Any],
) -> list[dict[str, Any]]:
    risk_by_task = {row["task_id"]: row["scope_risk"] for row in oracle_scope["rows"]}
    result = []
    for model in MODELS:
        for risk in ("high", "medium", "low"):
            group = [
                row for row in comparisons
                if row["model"] == model
                and risk_by_task.get(row["task_id"]) == risk
                and row["conditions"]["exact_oracle"] is not None
            ]
            result.append({
                "model": model,
                "scope_risk": risk,
                "n": len(group),
                "oracle_strict_passes": sum(row["conditions"]["exact_oracle"]["strict"] is True for row in group),
                "oracle_outcome_passes": sum(row["conditions"]["exact_oracle"]["outcome"] is True for row in group),
                "oracle_process_passes": sum(row["conditions"]["exact_oracle"]["process"] is True for row in group),
            })
    return result


def reference_integrity_analysis(reference_audit: dict[str, Any]) -> dict[str, Any]:
    tasks = [
        row
        for row in reference_audit.get("tasks", [])
        if isinstance(row, dict) and row.get("task_id")
    ]
    expected_ids = {
        f"E{environment}-LS{family}-T{tier}"
        for environment in range(1, 7)
        for family in range(1, 6)
        for tier in TIERS
    }
    actual_ids = {str(row["task_id"]) for row in tasks}
    rows = []
    for environment_id in ENVS:
        for tier in TIERS:
            selected = [
                row
                for row in tasks
                if row.get("environment_id") == environment_id
                and int(row.get("tier", -1)) == tier
            ]
            passed = sum(row.get("strict_pass") is True for row in selected)
            rows.append(
                {
                    "environment_id": environment_id,
                    "tier": tier,
                    "passed": passed,
                    "total": len(selected),
                    "pass_rate": rate(passed, len(selected)),
                }
            )
    failures = [row for row in tasks if row.get("strict_pass") is not True]
    complete = actual_ids == expected_ids and len(tasks) == 90
    return {
        "available": bool(tasks),
        "complete": complete,
        "passed": sum(row.get("strict_pass") is True for row in tasks),
        "total": len(tasks),
        "all_reference_solutions_pass": complete and not failures,
        "rows": rows,
        "failures": failures,
        "benchmark_revision": reference_audit.get("benchmark_revision"),
        "harbor_revision": reference_audit.get("harbor_revision"),
        "audit_type": reference_audit.get("audit_type"),
    }


def failure_attribution(
    rows: list[dict[str, Any]],
    verifier_audit: dict[str, Any],
    reference_integrity: dict[str, Any],
) -> dict[str, Any]:
    shape_by_task = {
        str(row.get("task_id")): str(row.get("process_shape_sensitivity") or "unknown")
        for row in verifier_audit.get("tasks", [])
        if isinstance(row, dict)
    }
    reference_by_task = {
        str(row.get("task_id")): row
        for row in reference_integrity.get("failures", [])
        if isinstance(row, dict)
    }
    verified_false_negatives = {
        task_id
        for task_id, definition in CASE_DEFINITIONS.items()
        if definition["kind"] == "强假阴性证据"
    }
    substantive_process = {
        task_id
        for task_id, definition in CASE_DEFINITIONS.items()
        if definition["kind"] == "合理的过程约束"
    }
    selected = [
        row
        for row in rows
        if row.get("condition") == "self_generated"
        and int(row.get("tier", -1)) in (5, 6)
    ]
    failed_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        if row.get("strict_pass") is not True:
            failed_by_task[str(row["task_id"])].append(row)

    failures = []
    for row in selected:
        if row.get("strict_pass") is True:
            continue
        task_id = str(row["task_id"])
        shape = shape_by_task.get(task_id, "unknown")
        if row.get("outcome_pass") is not True:
            cause = "functional_gap"
        elif task_id in verified_false_negatives:
            cause = "verified_verifier_false_negative"
        elif task_id in substantive_process:
            cause = "substantive_process_gap"
        elif shape in {"high", "medium"}:
            cause = "shape_sensitive_process_only"
        else:
            cause = "unresolved_process_only"
        peer_rows = [item for item in failed_by_task[task_id] if item.get("model") != row.get("model")]
        reference_status = "pending"
        if reference_integrity.get("complete"):
            reference_status = "failed" if task_id in reference_by_task else "passed"
        failures.append(
            {
                "model": row.get("model"),
                "environment_id": row.get("environment_id"),
                "tier": int(row.get("tier", -1)),
                "task_id": task_id,
                "task_slug": row.get("task_slug"),
                "cause": cause,
                "cause_zh": CAUSE_ZH[cause],
                "classification": row.get("classification"),
                "shape_sensitivity": shape,
                "failed_tests": row.get("failed_tests") or [],
                "failed_by_other_model": bool(peer_rows),
                "other_model_classifications": sorted(
                    {str(item.get("classification")) for item in peer_rows}
                ),
                "reference_solution_status": reference_status,
                "trajectory_path": row.get("local_trajectory_path"),
                "artifact_path": row.get("local_artifact_task_path"),
            }
        )

    summaries = []
    for environment_id in ENVS:
        for model in MODELS:
            for tier in (5, 6):
                observed = [
                    row
                    for row in selected
                    if row.get("environment_id") == environment_id
                    and row.get("model") == model
                    and int(row.get("tier", -1)) == tier
                ]
                failed = [
                    row
                    for row in failures
                    if row["environment_id"] == environment_id
                    and row["model"] == model
                    and row["tier"] == tier
                ]
                summaries.append(
                    {
                        "environment_id": environment_id,
                        "model": model,
                        "tier": tier,
                        "observed": len(observed),
                        "strict_passed": sum(row.get("strict_pass") is True for row in observed),
                        "failures": len(failed),
                        "cause_counts": dict(Counter(row["cause"] for row in failed)),
                    }
                )
    return {
        "taxonomy": CAUSE_ZH,
        "summaries": summaries,
        "failures": failures,
    }


def environment_diagnostics(
    rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    oracle_scope: dict[str, Any],
    attribution: dict[str, Any],
    reference_integrity: dict[str, Any],
) -> list[dict[str, Any]]:
    """Summarize the evidence needed to reason about each environment.

    This intentionally keeps observed facts separate from the prose profile.
    In particular, an official reference solution pass only establishes
    internal solvability; it is not counted as an oracle-skill model pass.
    """

    attribution_rows = [
        row
        for row in attribution.get("failures", [])
        if isinstance(row, dict)
    ]
    scope_rows = [
        row
        for row in oracle_scope.get("rows", [])
        if isinstance(row, dict)
    ]
    reference_rows = [
        row
        for row in reference_integrity.get("rows", [])
        if isinstance(row, dict)
    ]
    result = []
    for environment_id in ENVS:
        profile = ENVIRONMENT_PROFILES[environment_id]
        self_rows = [
            row
            for row in rows
            if row.get("environment_id") == environment_id
            and row.get("condition") == "self_generated"
            and int(row.get("tier", -1)) in (5, 6)
        ]
        env_comparisons = [
            row
            for row in comparisons
            if row.get("environment_id") == environment_id
            and int(row.get("tier", -1)) in (5, 6)
        ]
        by_model = []
        for model in MODELS:
            observed = [row for row in self_rows if row.get("model") == model]
            by_model.append(
                {
                    "model": model,
                    "observed": len(observed),
                    "strict_passed": sum(
                        row.get("strict_pass") is True for row in observed
                    ),
                    "outcome_passed": sum(
                        row.get("outcome_pass") is True for row in observed
                    ),
                    "process_passed": sum(
                        row.get("process_pass") is True for row in observed
                    ),
                    "functional_failures": sum(
                        row.get("outcome_pass") is not True for row in observed
                    ),
                    "process_only_failures": sum(
                        row.get("classification") == "process_only_failure"
                        for row in observed
                    ),
                }
            )

        paired = defaultdict(dict)
        for row in self_rows:
            paired[str(row.get("task_id"))][str(row.get("model"))] = row
        paired_tasks = [
            pair for pair in paired.values() if all(model in pair for model in MODELS)
        ]
        both_outcome_fail = sum(
            all(pair[model].get("outcome_pass") is not True for model in MODELS)
            for pair in paired_tasks
        )
        both_process_only = sum(
            all(
                pair[model].get("classification") == "process_only_failure"
                for model in MODELS
            )
            for pair in paired_tasks
        )

        controls: dict[str, dict[str, int]] = {}
        for condition in ("exact_oracle", "curated_all", "no_skill"):
            condition_rows = [
                row
                for row in rows
                if row.get("environment_id") == environment_id
                and row.get("condition") == condition
                and int(row.get("tier", -1)) in (5, 6)
            ]
            controls[condition] = {
                "observed": len(condition_rows),
                "strict_passed": sum(
                    row.get("strict_pass") is True for row in condition_rows
                ),
                "outcome_passed": sum(
                    row.get("outcome_pass") is True for row in condition_rows
                ),
                "process_passed": sum(
                    row.get("process_pass") is True for row in condition_rows
                ),
            }

        oracle_rescues = sum(
            row.get("verdict") == "oracle_rescues_outcome"
            for row in env_comparisons
        )
        oracle_outcome_failures = sum(
            row.get("conditions", {}).get("exact_oracle") is not None
            and row["conditions"]["exact_oracle"].get("outcome") is not True
            for row in env_comparisons
        )
        env_scope = [
            row for row in scope_rows if row.get("environment_id") == environment_id
        ]
        env_attribution = [
            row
            for row in attribution_rows
            if row.get("environment_id") == environment_id
        ]
        reference = [
            row
            for row in reference_rows
            if row.get("environment_id") == environment_id
            and int(row.get("tier", -1)) in (5, 6)
        ]
        control_complete = len(self_rows) == 20 and all(
            controls[name]["observed"] == 20
            for name in ("exact_oracle", "curated_all", "no_skill")
        )
        self_outcome_passed = sum(row["outcome_passed"] for row in by_model)
        matched_exact = [
            row
            for row in env_comparisons
            if row.get("conditions", {}).get("self_generated") is not None
            and row.get("conditions", {}).get("exact_oracle") is not None
        ]
        if control_complete:
            exact = controls["exact_oracle"]["outcome_passed"]
            curated = controls["curated_all"]["outcome_passed"]
            no_skill = controls["no_skill"]["outcome_passed"]
            current_read = (
                f"两模型 T5+T6 的 matched outcome 为 self-generated "
                f"{self_outcome_passed}/20、exact-oracle {exact}/20、"
                f"curated-all {curated}/20、no-skill {no_skill}/20。"
                f"Exact 相对 self 效应 {exact - self_outcome_passed:+d} 题，"
                f"curated-all 相对 no-skill 效应 {curated - no_skill:+d} 题，"
                f"exact 相对 curated-all 的选择先验效应 {exact - curated:+d} 题；"
                f"exact-oracle 仍有 {20 - exact} 个功能失败。"
            )
        elif matched_exact:
            paired_self = sum(
                row["conditions"]["self_generated"].get("outcome") is True
                for row in matched_exact
            )
            paired_exact = sum(
                row["conditions"]["exact_oracle"].get("outcome") is True
                for row in matched_exact
            )
            rescues = sum(
                row["conditions"]["self_generated"].get("outcome") is not True
                and row["conditions"]["exact_oracle"].get("outcome") is True
                for row in matched_exact
            )
            regressions = sum(
                row["conditions"]["self_generated"].get("outcome") is True
                and row["conditions"]["exact_oracle"].get("outcome") is not True
                for row in matched_exact
            )
            current_read = (
                profile["provisional_read"]
                + f" 当前已有 {len(matched_exact)} 个逐题匹配的 self/exact 样本："
                f"self-generated outcome {paired_self}/{len(matched_exact)}，"
                f"exact-oracle {paired_exact}/{len(matched_exact)}；"
                f"oracle 救回 {rescues} 题、相对退化 {regressions} 题。"
                "No-skill 与 curated-all 尚未齐全，不能把该差值解释为最终 skill 因果效应。"
            )
        else:
            current_read = profile["provisional_read"]
        result.append(
            {
                "environment_id": environment_id,
                "name": profile["name"],
                "capability": profile["capability"],
                "provisional_read": profile["provisional_read"],
                "current_read": current_read,
                "status": "matched_controls_complete" if control_complete else "provisional",
                "self_generated_by_model": by_model,
                "paired_task_count": len(paired_tasks),
                "both_models_outcome_fail": both_outcome_fail,
                "both_models_process_only_fail": both_process_only,
                "failure_cause_counts": dict(
                    Counter(str(row.get("cause")) for row in env_attribution)
                ),
                "scope_risk_counts": dict(
                    Counter(str(row.get("scope_risk")) for row in env_scope)
                ),
                "instruction_concept_instances": sum(
                    len(row.get("instruction_concepts") or []) for row in env_scope
                ),
                "verifier_only_concept_instances": sum(
                    len(row.get("verifier_only_concepts") or []) for row in env_scope
                ),
                "controls": controls,
                "oracle_outcome_rescues": oracle_rescues,
                "oracle_outcome_failures": oracle_outcome_failures,
                "reference_strict_passed": sum(
                    int(row.get("passed") or 0) for row in reference
                ),
                "reference_total": sum(int(row.get("total") or 0) for row in reference),
            }
        )
    return result


def compact_message(value: Any, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def execution_failure_kind(text: str) -> str:
    lowered = text.lower()
    if "learning_max_attempts > 1 requires" in lowered:
        return "invalid_eval_configuration"
    if "mirror sync in progress" in lowered or "file has unexpected size" in lowered:
        return "package_mirror_sync"
    if "agenttimeouterror" in lowered:
        return "agent_timeout"
    if "sanitize-output" in lowered or "output sanitization failed" in lowered:
        return "artifact_sanitization"
    if "download-assets" in lowered:
        return "asset_download"
    return "other_runtime_failure"


def execution_attempt_audit(
    raw_root: Path,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Separate failed AP attempts from accepted scientific task records."""
    selected_job_ids = {
        str(run.get("job_id"))
        for run in selected_runs(evidence)
        if run.get("job_id")
    }
    contributing_job_ids = {
        str(row.get("job_id"))
        for row in selected_rows(evidence)
        if row.get("job_id")
    }
    failures: list[dict[str, Any]] = []
    for metrics_path in sorted(
        raw_root.glob("*/ap-*/artifacts/output/metrics.json")
    ):
        label = metrics_path.parents[3].name
        if label.startswith("reference-oracle-"):
            continue
        metrics = load_json_optional(metrics_path)
        if metrics.get("status") != "failed":
            continue
        job_id = metrics_path.parents[2].name
        job_root = metrics_path.parents[2]
        exception_text = ""
        exception_paths = sorted(
            job_root.glob(
                "artifacts/output/runs/*/harbor-job/*/*/exception.txt"
            )
        )
        if exception_paths:
            exception_text = exception_paths[0].read_text(
                encoding="utf-8", errors="replace"
            )
        message = compact_message(metrics.get("message"), limit=420)
        raw_diagnostic = " ".join(
            part
            for part in (
                str(metrics.get("error_stage") or ""),
                message,
                exception_text,
            )
            if part
        )
        failures.append(
            {
                "label": label,
                "job_id": job_id,
                "error_stage": metrics.get("error_stage"),
                "message": message,
                "failure_kind": execution_failure_kind(raw_diagnostic),
                "selected_run_candidate": job_id in selected_job_ids,
                "contributes_t56_results": job_id in contributing_job_ids,
                "metrics_path": str(metrics_path.resolve()),
                "exception_path": (
                    str(exception_paths[0].resolve()) if exception_paths else None
                ),
            }
        )
    counts = Counter(row["failure_kind"] for row in failures)
    return {
        "failed_attempt_count": len(failures),
        "excluded_attempt_count": sum(
            row["contributes_t56_results"] is not True for row in failures
        ),
        "failed_attempts_contributing_t56": sum(
            row["contributes_t56_results"] is True for row in failures
        ),
        "failure_counts": dict(sorted(counts.items())),
        "failures": failures,
    }


def ap_console_url(kind: str, identifier: str | None) -> str | None:
    if not identifier:
        return None
    return (
        "https://agentplatform.aliyun-inc.com/?cluster="
        f"{AP_CLUSTER}#/{kind}/{identifier}"
    )


def runtime_progress_analysis(
    coverage: list[dict[str, Any]],
    inventory: dict[str, Any],
    matrix_state: dict[str, Any],
) -> dict[str, Any]:
    """Expose live AP/control progress without treating it as score evidence."""
    jobs = [job for job in inventory.get("jobs", []) if isinstance(job, dict)]
    active_statuses = {"Queued", "Pending", "Scheduling", "Running"}
    terminal_statuses = {"Succeeded", "Failed", "Cancelled"}
    stages = matrix_state.get("stages", {})
    rows: list[dict[str, Any]] = []
    for stage_name, (model, condition) in MATRIX_STAGE_META.items():
        stage = stages.get(stage_name, {}) if isinstance(stages, dict) else {}
        group_id = str(stage.get("group_id") or "") or None
        group_jobs = (
            [job for job in jobs if job.get("group_id") == group_id]
            if group_id
            else []
        )
        status_counts = Counter(
            str(job.get("status") or "Unknown") for job in group_jobs
        )
        if not status_counts and isinstance(stage.get("job_statuses"), dict):
            status_counts.update(
                {
                    str(key): int(value)
                    for key, value in stage["job_statuses"].items()
                }
            )
        cells = [
            row
            for row in coverage
            if row["model"] == model and row["condition"] == condition
        ]
        rows.append(
            {
                "stage": stage_name,
                "model": model,
                "condition": condition,
                "status": str(stage.get("status") or "pending"),
                "group_id": group_id,
                "group_url": ap_console_url("groups", group_id),
                "job_statuses": dict(sorted(status_counts.items())),
                "complete_cells": sum(bool(row["complete"]) for row in cells),
                "observed_tasks": sum(int(row["observed"]) for row in cells),
                "failed_group_count": len(stage.get("failed_groups") or []),
                "registered_for_export": (
                    stage.get("registered_with_evidence_watcher") is True
                ),
            }
        )

    repairs: list[dict[str, Any]] = []
    repair_specs = (
        ("qwen3.7-max", "E1", "qwen37max-e1-repair-v1-15"),
        ("sig-fable", "E4", "sig-fable-e4-repair-v1-15"),
    )
    for model, environment_id, label in repair_specs:
        candidates = [job for job in jobs if job.get("label") == label]
        candidates.sort(key=lambda job: str(job.get("created_at") or ""))
        job = candidates[-1] if candidates else {}
        repairs.append(
            {
                "model": model,
                "environment_id": environment_id,
                "label": label,
                "job_id": job.get("job_id"),
                "job_url": ap_console_url("jobs", job.get("job_id")),
                "status": str(job.get("status") or "missing"),
                "export_state": str(job.get("export_state") or "not_started"),
                "attempt_count": len(candidates),
            }
        )

    return {
        "inventory_updated_at_utc": inventory.get("updated_at_utc"),
        "matrix_updated_at_utc": matrix_state.get("updated_at_utc"),
        "complete_cells": sum(bool(row["complete"]) for row in coverage),
        "total_cells": len(coverage),
        "active_job_count": sum(job.get("status") in active_statuses for job in jobs),
        "terminal_waiting_export": sum(
            job.get("status") in terminal_statuses
            and job.get("export_state") != "complete"
            for job in jobs
        ),
        "stages": rows,
        "repairs": repairs,
        "interpretation": (
            "AP status only describes platform lifecycle. A stage contributes scientific "
            "results only after terminal export, artifact audit, and 15/15 task coverage."
        ),
    }


def conclusions(
    coverage: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    audit: dict[str, Any],
    protocol_design: dict[str, Any],
    learning: dict[str, Any],
    derivability: dict[str, Any],
    oracle_scope: dict[str, Any],
    reference_integrity: dict[str, Any],
    measurement_validity: dict[str, Any],
) -> list[dict[str, str]]:
    missing = [row for row in coverage if not row["complete"]]
    result = []
    if missing:
        result.append({
            "level": "pending",
            "title": "最终因果结论尚未解锁",
            "body": f"{len(coverage)} 个模型×条件×环境单元中仍有 {len(missing)} 个未达到 15/15 任务覆盖；当前结果只能作为诊断，不能回答 oracle 是否稳定救回 T5/T6。",
        })
    else:
        oracle_pairs = [row for row in comparisons if row["conditions"]["exact_oracle"]]
        failed = [row for row in oracle_pairs if row["conditions"]["exact_oracle"]["outcome"] is not True]
        rescued = [row for row in oracle_pairs if row["verdict"] == "oracle_rescues_outcome"]
        result.append({
            "level": "good" if rescued else "warn",
            "title": "Oracle 的功能性处理效应",
            "body": f"匹配任务中，oracle 在 {len(rescued)} 题上把 self-generated 的 outcome 失败救回；仍有 {len(failed)} 个 oracle outcome 失败。应逐题区分 skill 不足、模型执行失败和题目/环境缺陷。",
        })
    result.append({
        "level": "warn",
        "title": "Exact Oracle 实际是刻意留缺口的 Curated 子集",
        "body": (
            f"仓库共有 {protocol_design['family_count']} 个 curated skill family 和 "
            f"{protocol_design['gap_summary_count']} 条 gap summary，其中 "
            f"{protocol_design['gap_summaries_explicitly_limiting_curated']}/"
            f"{protocol_design['gap_summary_count']} 明确描述 curated skill 未覆盖的能力。"
            "T2 的 30 题是 enriched acquisition，T3 的 30 题是 variant acquisition；"
            "模型的目标是从 T1–T3 补全 scaffold，而不是复刻 curated 文本。"
            "因此 exact-oracle 失败不能推出题目坏，只能说明这个 gold-selected scaffold 对该模型/任务不充分。"
        ),
    })
    if not reference_integrity["complete"]:
        result.append({
            "level": "pending",
            "title": "官方 reference solution 完整性审计仍在运行",
            "body": (
                f"目前收集 {reference_integrity['total']}/90 个官方 solution/solve.sh → 官方 verifier 结果。"
                "这项审计与模型使用 oracle skill 不同：它直接检查仓库提供的标准解能否在真实容器中通过。"
            ),
        })
    elif reference_integrity["all_reference_solutions_pass"]:
        result.append({
            "level": "good",
            "title": "90/90 官方 reference solutions 通过真实 verifier",
            "body": (
                "这排除了 T4–T6 任务资产普遍不可解或标准解与 verifier 系统性冲突。"
                "模型拿 exact oracle skill 仍失败时，不能仅据此判题目坏；还需区分模型执行能力、skill scope 和 verifier 形态约束。"
            ),
        })
    else:
        result.append({
            "level": "warn",
            "title": "官方 reference solution 发现完整性失败",
            "body": (
                f"官方标准解严格通过 {reference_integrity['passed']}/{reference_integrity['total']}；"
                f"{len(reference_integrity['failures'])} 题需要优先视为题目、标准解、容器或 verifier 的完整性嫌疑，不能用于归因 skill evolve。"
            ),
        })
    summary = audit.get("summary", {})
    result.append({
        "level": "warn",
        "title": "Strict reward 混入了强代码形态约束",
        "body": f"{summary.get('tasks_with_literal_or_regex_process_checks', 0)}/90 题的 process verifier 含源码字面量或正则检查，{summary.get('tasks_with_effective_process_weight_50_percent', 0)}/90 题的过程部分有效权重为 50%。因此必须同时报告 strict 与 outcome。",
    })
    result.append({
        "level": "info",
        "title": "Exact oracle 同时包含 annotation prior",
        "body": "T4/T5 只暴露 primary skill、T6 只暴露 required skills，这不仅改变 skill 文本质量，也提供了标注者的任务→skill 选择。本研究已加入 curated-all-library：skill 内容全集相同，但不给 gold 子集。两者配对差衡量 gold 子集带来的选择/注意力优势；它仍把标注映射信息与少读几个无关 skill 的搜索成本合在一起，不能继续细分。",
    })
    qwen_learning = learning.get("by_model", {}).get("qwen3.7-max", {})
    fable_learning = learning.get("by_model", {}).get("sig-fable", {})
    result.append({
        "level": "warn",
        "title": "Self-generated skill 明显吸收 verifier 形态",
        "body": (
            f"Qwen 有 {qwen_learning.get('skills_with_verifier_markers', 0)}/{qwen_learning.get('active_skills', 0)} 个 active skills，"
            f"Fable 有 {fable_learning.get('skills_with_verifier_markers', 0)}/{fable_learning.get('active_skills', 0)} 个包含 verifier/process-test/source-scan 等术语。"
            "这说明模型确实从失败反馈学习，但也可能把测试实现细节当成可迁移知识。"
        ),
    })
    result.append({
        "level": "warn",
        "title": "Curated oracle 不是普遍充分的 solution manual",
        "body": (
            f"60 个 T5/T6 中，启发式 scope 筛查标记 {oracle_scope.get('counts', {}).get('high', 0)} 个高风险、"
            f"{oracle_scope.get('counts', {}).get('medium', 0)} 个中风险。已人工确认固定重试、基础分页、固定 UTC offset 等 oracle scope 与高级任务要求存在缺口；"
            "因此 oracle failure 不能单独证明题目坏。"
        ),
    })
    visibility = oracle_scope.get("concept_visibility", {})
    result.append({
        "level": "warn",
        "title": "T5/T6 题面已显式给出大部分高级要求",
        "body": (
            f"受控概念词表在 60 个 T5/T6 中识别到 "
            f"{visibility.get('concept_instances', 0)} 个 task-concept 实例，"
            f"其中 {visibility.get('instruction_explicit_instances', 0)} 个已在任务正文显式出现，"
            f"仅 {visibility.get('verifier_only_instances', 0)} 个只出现在 verifier check 命名中。"
            "这提示部分题对 skill 的增量需求可能偏弱；最终以 no-skill 与 skill 条件的配对差判定。"
        ),
    })
    validity_parts = []
    for item in measurement_validity.get("summaries", []):
        counts = item.get("category_counts", {})
        validity_parts.append(
            f"{item.get('model')}: history-eligible="
            f"{item.get('eligible_for_causal_skill_claim', 0)}/"
            f"{item.get('controlled_task_count', 0)}, "
            f"on-task-only={counts.get('on_task_only', 0)}, "
            f"missing-learning={counts.get('missing_learning_evidence', 0)}"
        )
    result.append({
        "level": "warn",
        "title": "并非所有 T5/T6 成功都能作为 Skill Evolution 证据",
        "body": (
            "受控概念筛查显示："
            + "; ".join(validity_parts)
            + "。只在当前题面出现的高级要求，即使模型做对，也只能证明现场执行能力；"
            "有 T1–T3 历史支持的任务也必须再由同题 no-skill 对照证明 skill 增量。"
            "另有一半任务未被受控词表覆盖，保持未分类，不能据词面筛查下结论。"
        ),
    })
    derivability_parts = []
    for item in derivability.get("summaries", []):
        counts = item.get("category_counts", {})
        derivability_parts.append(
            f"{item.get('model')}: oracle-only unseen="
            f"{counts.get('oracle_adds_unseen_concept', 0)}, "
            f"missing-everywhere="
            f"{counts.get('missing_from_both_learning_and_oracle', 0)}"
        )
    result.append({
        "level": "info",
        "title": "当前未观察到 Oracle 独有的未见高级概念",
        "body": (
            "在受控词表与当前已完整导出的 T1–T3 family 中，"
            + "; ".join(derivability_parts)
            + "。这不支持“oracle 文本偷偷写入了标注者额外解题知识”的假设；"
            "更明显的问题是一些 T5/T6 概念在 T1–T3、generated skill 和 oracle skill 中都不存在。"
            "这是词表筛查而非完整语义证明，且仍需 curated-all 实验测选择先验。"
        ),
    })
    author_gap_parts = []
    for item in derivability.get("summaries", []):
        author_gap_parts.append(
            f"{item.get('model')}: meta-hit={item.get('author_gap_metadata_hits', 0)}, "
            f"T1–T3-unseen={item.get('author_gap_unseen_in_t1_t3', 0)}, "
            "missing-from-visible-sources="
            f"{item.get('author_gap_missing_from_all_model_visible_sources', 0)}"
        )
    author_only_examples = sorted(
        {
            f"{row.get('task_id')}:{row.get('concept')}"
            for row in derivability.get("records", [])
            if row.get("in_author_gap_metadata")
            and not row.get("in_t1_t3_evidence")
            and not row.get("in_generated_skill")
            and not row.get("in_curated_oracle")
        }
    )
    result.append({
        "level": "warn",
        "title": "标注先验更多存在于 author-only gap metadata，而非 Oracle SKILL.md",
        "body": (
            "每个 family 的 meta.yaml 明确记录 curated skill 没覆盖的 gap；这些内容用于题目设计，"
            "但不会作为 skill 注入模型。受控概念统计为 "
            + "; ".join(author_gap_parts)
            + "。因此如果某个 T5/T6 概念只在 meta gap 中出现，应该归为题目作者掌握但模型不可见的设计先验，"
            "不能误称 oracle skill 向模型泄漏了知识。当前明确命中的例子："
            + ("、".join(author_only_examples) if author_only_examples else "无")
            + "。"
        ),
    })
    instruction_concepts_by_task = {
        str(row.get("task_id")): set(row.get("instruction_concepts") or [])
        for row in oracle_scope.get("rows", [])
        if isinstance(row, dict)
    }
    author_only_instruction_explicit = sorted(
        example
        for example in author_only_examples
        if example.split(":", 1)[1]
        in instruction_concepts_by_task.get(example.split(":", 1)[0], set())
    )
    result.append({
        "level": "warn",
        "title": "Author-only 新概念虽在当前题面明示，却不能证明来自 Skill Evolution",
        "body": (
            f"当前 {len(author_only_examples)} 个 author-only task-concept 中，"
            f"{len(author_only_instruction_explicit)} 个在对应 T5/T6 instruction 里直接出现："
            + ("、".join(author_only_instruction_explicit) if author_only_instruction_explicit else "无")
            + "。因此这些题不是隐藏契约导致的不可解；模型可现场按题面实现。"
            "但由于 T1–T3 和两种 skill 都没有该概念，做对也不能作为“此前总结出的 skill 发生迁移”的证据。"
            "最终应看 no-skill 是否同样做对，并把这类题与真正依赖历史 skill 的题分层报告。"
        ),
    })
    return result


def build_payload(
    evidence: dict[str, Any],
    audit: dict[str, Any],
    raw_root: Path,
    reference_audit: dict[str, Any] | None = None,
    inventory: dict[str, Any] | None = None,
    matrix_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = selected_rows(evidence)
    runs = selected_runs(evidence)
    coverage = condition_coverage(rows, runs)
    comparisons = task_comparisons(rows)
    protocol_design = protocol_design_audit(audit)
    learning = learning_analysis(evidence)
    oracle_scope = oracle_scope_analysis(audit)
    derivability = derivability_analysis(learning, oracle_scope)
    measurement_validity = measurement_validity_analysis(
        derivability, oracle_scope
    )
    reference_integrity = reference_integrity_analysis(reference_audit or {})
    attribution = failure_attribution(rows, audit, reference_integrity)
    environment_summary = environment_diagnostics(
        rows,
        comparisons,
        oracle_scope,
        attribution,
        reference_integrity,
    )
    execution_attempts = execution_attempt_audit(raw_root, evidence)
    runtime_progress = runtime_progress_analysis(
        coverage,
        inventory or {},
        matrix_state or {},
    )
    return {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "is_complete": all(row["complete"] for row in coverage),
        "coverage": coverage,
        "aggregates": aggregates(rows),
        "tasks": rows,
        "comparisons": comparisons,
        "protocol_design": protocol_design,
        "causal_diagnosis": causal_diagnosis_summary(comparisons),
        "skill_use_adherence": skill_use_adherence(rows),
        "effects": matched_effects(comparisons),
        "model_comparisons": model_comparisons(rows),
        "failure_map": failure_map(rows),
        "cases": build_cases(rows, audit, raw_root),
        "skills": skill_summary(evidence),
        "learning": learning,
        "derivability": derivability,
        "measurement_validity": measurement_validity,
        "oracle_scope": oracle_scope,
        "verifier_shape_outcomes": verifier_shape_outcomes(rows, audit),
        "scope_condition_outcomes": scope_condition_outcomes(comparisons, oracle_scope),
        "reference_integrity": reference_integrity,
        "failure_attribution": attribution,
        "environment_diagnostics": environment_summary,
        "execution_attempts": execution_attempts,
        "runtime_progress": runtime_progress,
        "verifier_audit": audit,
        "conclusions": conclusions(
            coverage,
            comparisons,
            audit,
            protocol_design,
            learning,
            derivability,
            oracle_scope,
            reference_integrity,
            measurement_validity,
        ),
        "paths": {
            "raw_root": str(raw_root.resolve()),
            "evidence": evidence.get("inventory_path"),
        },
    }


def render_markdown(data: dict[str, Any]) -> str:
    complete = data["is_complete"]
    lines = [
        "# SkillEvolBench T5/T6 与 Oracle Skill 因果诊断",
        "",
        f"> 状态：**{'完整证据' if complete else '进行中，禁止作最终因果结论'}**；生成时间 `{data['generated_at_utc']}`。",
        "",
        "## 研究问题与判定口径",
        "",
        "本报告比较同一模型、同一任务在 `self-generated`、`exact oracle`、`no skill`、`curated-all-library` 四个条件下的结果。后者提供同一 Env 的 curated 内容全集，但不暴露任务→skill 的 gold 子集。官方 strict pass 要求 outcome 与 process 同时通过；为识别 verifier 假阴性，另行报告纯功能 outcome pass。Oracle 仍失败只能说明 oracle 对该模型不足，不能单独证明题目有问题。",
        "",
        "## ‘Oracle’ 的协议边界",
        "",
        "这里的 `exact_oracle` 只是按 gold task→skill 映射注入仓库 curated skill 子集，"
        "不是 solution、完整策略或能力上界。仓库刻意让 curated skill 暴露 gap，"
        "再让模型从 acquisition 经验补全它。",
        "",
        "| 源码事实 | 数量 | 含义 |",
        "|---|---:|---|",
        f"| Curated skill families | {data['protocol_design']['family_count']} | 每个 Env 五个 family |",
        f"| Author gap summaries | {data['protocol_design']['gap_summary_count']} | 每个 family 两条刻意缺口 |",
        f"| 明确写出 curated skill 局限的 gap | {data['protocol_design']['gap_summaries_explicitly_limiting_curated']}/{data['protocol_design']['gap_summary_count']} | Exact curated 不是充分 oracle |",
        f"| T2 enriched acquisition | {data['protocol_design']['role_counts'].get('T2:enriched:learning', 0)} | 暴露基础 procedure 缺失的子能力 |",
        f"| T3 variant acquisition | {data['protocol_design']['role_counts'].get('T3:variant:learning', 0)} | 换表面形式继续学习同一 procedure |",
        "",
        "## 当前结论",
        "",
    ]
    for item in data["conclusions"]:
        lines += [f"### {item['title']}", "", item["body"], ""]
    lines += ["## 证据覆盖", "", "| 模型 | 条件 | 完整环境 | 任务记录 |", "|---|---:|---:|---:|"]
    for model in MODELS:
        for condition in CONDITIONS:
            rows = [row for row in data["coverage"] if row["model"] == model and row["condition"] == condition]
            lines.append(f"| {model} | {CONDITION_ZH[condition]} | {sum(row['complete'] for row in rows)}/6 | {sum(row['observed'] for row in rows)}/90 |")
    progress = data["runtime_progress"]
    lines += [
        "",
        "## 运行中的完整对照矩阵",
        "",
        f"当前科学证据完整单元 **{progress['complete_cells']}/{progress['total_cells']}**；"
        f"AP active jobs **{progress['active_job_count']}**；"
        f"已经终态但等待导出的 jobs **{progress['terminal_waiting_export']}**。"
        "下表的 `Running`/`Succeeded` 只是平台状态，只有导出并通过 artifact 审计且达到 15/15 才进入上面的证据覆盖。",
        "",
        "| 模型 | 条件 | Matrix 状态 | AP jobs | 完整 Env | 任务记录 | 历史失败组 | AP group |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in progress["stages"]:
        statuses = ", ".join(
            f"{key}={value}" for key, value in row["job_statuses"].items()
        ) or "—"
        group = (
            f"[{row['group_id']}]({row['group_url']})"
            if row.get("group_url")
            else "—"
        )
        lines.append(
            f"| {row['model']} | {CONDITION_ZH[row['condition']]} | "
            f"{row['status']} | {statuses} | {row['complete_cells']}/6 | "
            f"{row['observed_tasks']}/90 | {row['failed_group_count']} | {group} |"
        )
    lines += [
        "",
        "| Self-generated 修复 | Job 状态 | Artifact 导出 | 尝试数 | AP job |",
        "|---|---|---|---:|---|",
    ]
    for row in progress["repairs"]:
        job = (
            f"[{row['job_id']}]({row['job_url']})" if row.get("job_url") else "—"
        )
        lines.append(
            f"| {row['model']} / {row['environment_id']} | {row['status']} | "
            f"{row['export_state']} | {row['attempt_count']} | {job} |"
        )
    attempts = data["execution_attempts"]
    lines += [
        "",
        "## 实验执行健康与排除尝试",
        "",
        f"当前识别到 **{attempts['failed_attempt_count']}** 个模型实验 AP 失败尝试；"
        f"其中 **{attempts['excluded_attempt_count']}** 个未进入科学统计，"
        f"**{attempts['failed_attempts_contributing_t56']}** 个仍贡献了 T4–T6 记录。"
        "失败尝试保留作运行审计，但只有完整、可复核的环境 episode 才能形成 15/15 单元。",
        "",
        "| 类型 | 数量 |",
        "|---|---:|",
    ]
    for kind, count in attempts["failure_counts"].items():
        lines.append(f"| {kind} | {count} |")
    lines += [
        "",
        "| Label | Job | 类型 | Stage | 纳入分析 | 诊断 |",
        "|---|---|---|---|---:|---|",
    ]
    for row in attempts["failures"]:
        diagnostic = compact_message(row.get("message"), limit=160).replace(
            "|", "\\|"
        )
        lines.append(
            f"| {row['label']} | `{row['job_id']}` | {row['failure_kind']} | "
            f"{row.get('error_stage') or '—'} | "
            f"{'是' if row['contributes_t56_results'] else '否'} | "
            f"{diagnostic} |"
        )
    reference = data["reference_integrity"]
    lines += [
        "",
        "## 官方 Reference Solution × 官方 Verifier 完整性审计",
        "",
        "该对照不调用模型，也不注入 skill；Harbor `oracle` agent 在真实 task container 中执行仓库的 `solution/solve.sh`，再运行未修改的官方 verifier。它回答的是题目资产是否内部可解，不代表模型拿到 oracle skill 就必然能解题。",
        "",
        f"当前覆盖 **{reference['total']}/90**，严格通过 **{reference['passed']}/{reference['total'] or 0}**，完整性状态：**{'完整且全部通过' if reference['all_reference_solutions_pass'] else '完整但存在失败' if reference['complete'] else '运行中'}**。",
        "",
        "| Env | T4 | T5 | T6 |",
        "|---|---:|---:|---:|",
    ]
    for environment_id in ENVS:
        cells = []
        for tier in TIERS:
            row = next(
                item
                for item in reference["rows"]
                if item["environment_id"] == environment_id and item["tier"] == tier
            )
            cells.append(f"{row['passed']}/{row['total']}")
        lines.append(f"| {environment_id} | {' | '.join(cells)} |")
    if reference["failures"]:
        lines += ["", "失败的官方 reference solutions：", ""]
        for row in reference["failures"]:
            lines.append(
                f"- `{row.get('task_id')}`：score={row.get('normalized_score')}，"
                f"outcome={row.get('outcome_passed')}，process={row.get('process_passed')}，"
                f"exception=`{row.get('exception_info') or '无'}`。"
            )
    lines += ["", "## 分环境与层级结果", "", "| 模型 | 条件 | Env | Tier | n | Strict | Outcome | Process |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in data["aggregates"]:
        lines.append(
            f"| {row['model']} | {CONDITION_ZH.get(row['condition'], row['condition'])} | {row['environment_id']} | T{row['tier']} | {row['n']} | {row['strict']}/{row['n']} | {row['outcome']}/{row['n']} | {row['process']}/{row['n']} |"
        )
    lines += [
        "",
        "## 模型间配对比较（仅共同完成的同一任务）",
        "",
        "| 条件 | Tier | 指标 | 配对 n | Qwen | Fable | Qwen-only | Fable-only | Sign-test p |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in data["model_comparisons"]:
        if not item["n"]:
            continue
        p_value = "—" if item["sign_test_p"] is None else f"{item['sign_test_p']:.4f}"
        lines.append(
            f"| {CONDITION_ZH[item['condition']]} | T{item['tier']} | {item['metric']} | {item['n']} | {item['qwen_pass']}/{item['n']} | {item['fable_pass']}/{item['n']} | {item['qwen_only']} | {item['fable_only']} | {p_value} |"
        )
    lines += [
        "",
        "## Skill 条件的任务内配对效应",
        "",
        "| 模型 | Tier | 指标 | Treatment − Reference | n | Treatment | Reference | Δ | Rescue / Harm |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in data["effects"]:
        if not item["n"]:
            continue
        lines.append(
            f"| {item['model']} | T{item['tier']} | {item['metric']} | {CONDITION_ZH[item['treatment']]} − {CONDITION_ZH[item['reference']]} | {item['n']} | {item['treatment_pass']}/{item['n']} | {item['reference_pass']}/{item['n']} | {pct(item['delta'])} | {item['rescued']} / {item['harmed']} |"
        )
    causal = data["causal_diagnosis"]
    lines += [
        "",
        "## 四条件逐题因果判定",
        "",
        f"T5/T6 共期望 `{causal['expected']}` 个模型×任务配对；当前已有 "
        f"`{causal['complete']}` 个同时具备 Self / Exact / Curated-all / No-skill 四条件。"
        "不完整的配对一律显示为等待，不用缺失值推断效果。",
        "",
        "| 关键 outcome 模式 | 判定 | 能回答什么 |",
        "|---|---|---|",
        "| N=1，四条件都过 | 无需 skill 也能做 | 该题 skill 需求弱，不能作为强 evolve 证据 |",
        "| N=0，S=1 | 生成 skill 带来增益 | 直接支持模型从 T1–T3 总结的 skill 帮助迁移 |",
        "| N=1，S=0 | 生成 skill 造成干扰 | 直接说明 self-generated skill 发生负迁移 |",
        "| N=0，S=0，E=1，A=1 | Curated 内容有效，生成 skill 不足 | 差距主要来自 skill 内容质量 |",
        "| N=0，S=0，E=1，A=0 | Gold 子集选择/注意力优势 | gold 子集减少选择与阅读负担；不能拆分映射信息和搜索成本 |",
        "| N=0，E=0，A=1 | 全库有益，Gold 子集不足 | gold 子集遗漏有用 skill 或选择造成干扰 |",
        "| S=E=A=N=0 | 四种模型条件都失败 | 模型执行上限、oracle scope 或任务难度；reference 通过时不能直接判题目坏 |",
        "",
        "当前完整配对分类：`"
        + json.dumps(causal["category_counts"], ensure_ascii=False)
        + "`。",
        "",
        "## Skill 注入与实际读取是否一致",
        "",
        "`exact-oracle` 的目录/hash 审计证明 treatment 被正确挂载；"
        "`skills_actually_used` 则从真实工具调用判断模型是否打开 SKILL.md。"
        "前者是 treatment assignment，后者是 compliance，必须分开报告。"
        "No-skill 与 skill 条件的 prompt framing 也不同，因此两者差值是“提供并要求使用 skill library”的整体处理效应，"
        "不是纯文本内容效应；Exact 与 Curated-all 的 framing 相同，可更干净地识别 gold 子集的选择/注意力优势。"
        "但 Exact 只挂载相关子集、Curated-all 挂载全 Env 五个 skills，因此该差值仍同时包含标注映射信息和搜索/阅读负担。",
        "",
        "| 模型 | 条件 | Tier | n | 读取任意 skill | Exact 全部期望 skill 均读取 | 已读取时 Outcome | 未读取时 Outcome |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in data["skill_use_adherence"]:
        if not item["n"]:
            continue
        exact = (
            "—"
            if item["exact_expected_skills_fully_used"] is None
            else f"{item['exact_expected_skills_fully_used']}/{item['n']}"
        )
        lines.append(
            f"| {item['model']} | {CONDITION_ZH[item['condition']]} | T{item['tier']} | "
            f"{item['n']} | {item['any_skill_used']}/{item['n']} | {exact} | "
            f"{item['used_outcome_passed']}/{item['used_n']} | "
            f"{item['unused_outcome_passed']}/{item['unused_n']} |"
        )
    lines += [
        "",
        "## 六环境诊断总览",
        "",
        "这一节先给出可扫描的 Env 级判断。`当前解读`在三组匹配对照未齐时明确属于 provisional；"
        "官方 reference 只证明任务内部可解，不能代替模型拿 oracle skill 的结果。每个模型在一个 Env 的 T5+T6 共 10 题，"
        "因此每个对照条件两模型合计期望 20 条记录。",
        "",
    ]
    for item in data["environment_diagnostics"]:
        lines += [
            f"### {item['environment_id']} · {item['name']}",
            "",
            f"**能力对象：** {item['capability']}",
            "",
            f"**当前解读（{'匹配对照已齐' if item['status'] == 'matched_controls_complete' else '暂定'}）：** "
            f"{item['current_read']}",
            "",
            "| 证据 | Qwen | Fable / 合计 |",
            "|---|---:|---:|",
        ]
        model_rows = {row["model"]: row for row in item["self_generated_by_model"]}
        qwen = model_rows["qwen3.7-max"]
        fable = model_rows["sig-fable"]
        lines += [
            f"| Self-generated T5+T6 覆盖 | {qwen['observed']}/10 | {fable['observed']}/10 |",
            f"| Outcome 通过 | {qwen['outcome_passed']}/{qwen['observed']} | {fable['outcome_passed']}/{fable['observed']} |",
            f"| Strict 通过 | {qwen['strict_passed']}/{qwen['observed']} | {fable['strict_passed']}/{fable['observed']} |",
            f"| Process-only 失败 | {qwen['process_only_failures']} | {fable['process_only_failures']} |",
            f"| 双模型同题 outcome 失败 | — | {item['both_models_outcome_fail']}/{item['paired_task_count']} 对齐题 |",
            f"| 官方 reference strict | — | {item['reference_strict_passed']}/{item['reference_total']} |",
        ]
        for condition in ("exact_oracle", "curated_all", "no_skill"):
            control = item["controls"][condition]
            lines.append(
                f"| {CONDITION_ZH[condition]} outcome | — | "
                f"{control['outcome_passed']}/{control['observed']}（期望 20） |"
            )
        lines += [
            "",
            f"Oracle scope 风险：`{item['scope_risk_counts']}`；"
            f"题面明示受控概念 `{item['instruction_concept_instances']}` 个，"
            f"verifier-only `{item['verifier_only_concept_instances']}` 个；"
            f"当前 oracle outcome rescue `{item['oracle_outcome_rescues']}`，"
            f"oracle outcome failure `{item['oracle_outcome_failures']}`。",
            "",
        ]
    lines += ["", "## Self-generated 条件下逐 Env 的 T5/T6 失败原因", ""]
    for env in ENVS:
        lines += [f"### {env}", ""]
        for model in MODELS:
            for tier in (5, 6):
                item = next(
                    row for row in data["failure_map"]
                    if row["model"] == model and row["environment_id"] == env and row["tier"] == tier
                )
                lines.append(f"- **{model} / T{tier}**：观测 {item['observed']}/5，strict 失败 {item['strict_failures']}。")
                for task in item["tasks"]:
                    outcome_names = "; ".join(
                        f"{check['name']}: {compact_message(check['message'])}"
                        for check in task["failed_outcome"]
                    ) or "无"
                    process_names = "; ".join(
                        f"{check['name']}: {compact_message(check['message'])}"
                        for check in task["failed_process"]
                    ) or "无"
                    lines.append(
                        f"  - `{task['task_id']}`（{task['task_slug']}；skill: `{', '.join(task['required_skills']) or task['primary_skill']}`）{CLASS_ZH.get(str(task['classification']), task['classification'])}；outcome: `{outcome_names}`；process: `{process_names}`。"
                    )
        lines.append("")
    lines += [
        "## Self-generated 失败归因总览",
        "",
        "该表先区分功能失败与 process-only 失败。`已核实假阴性`仅用于已经逐代码确认“功能测试全过、实现存在、verifier 只扫固定文件或字面量”的案例；其余源码形态敏感项仍标为待复核，不把启发式判断冒充结论。",
        "",
        "| Env | Tier | 模型 | 覆盖 | Strict | 功能 gap | 已核实假阴性 | 实质过程 gap | 形态敏感 | 未决过程 |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in data["failure_attribution"]["summaries"]:
        counts = item["cause_counts"]
        lines.append(
            f"| {item['environment_id']} | T{item['tier']} | {item['model']} | {item['observed']}/5 | "
            f"{item['strict_passed']}/{item['observed']} | {counts.get('functional_gap', 0)} | "
            f"{counts.get('verified_verifier_false_negative', 0)} | {counts.get('substantive_process_gap', 0)} | "
            f"{counts.get('shape_sensitive_process_only', 0)} | {counts.get('unresolved_process_only', 0)} |"
        )
    lines += [
        "## T1–T3 学习证据与 Generated/Oracle Skill 差异",
        "",
        "| 模型 | 学习任务 | 总尝试 | 最终 strict 通过 | 失败后修复成功 | same-session 异常 | active skills / families | 多 skill family | 含 verifier 术语的 generated skills |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model in MODELS:
        item = data["learning"]["by_model"].get(model, {})
        lines.append(
            f"| {model} | {item.get('learning_tasks', 0)} | {item.get('learning_attempts', 0)} | {item.get('terminal_strict_passes', 0)} | {item.get('repaired_to_pass', 0)} | {item.get('same_session_failures', 0)} | {item.get('active_skills', 0)} / {item.get('families', 0)} | {item.get('families_with_multiple_skills', 0)} | {item.get('skills_with_verifier_markers', 0)} |"
        )
    lines += [
        "",
        "Generated skill 普遍比 curated oracle 更长、更贴近具体任务和 verifier 反馈；这可能增加可执行性，也可能是对当前测试的过拟合。下表的 `oracle evidence recall` 只是 oracle 词汇在 T1–T3 可见说明/失败反馈中的词面覆盖率，不能证明某个概念逻辑上一定可推出。",
        "",
        "| 模型 | Family | T1–T3 | 尝试 | 最终通过 | Generated skills | Best Jaccard | Oracle evidence recall | Generated verifier markers |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in data["learning"]["families"]:
        lines.append(
            f"| {item['model']} | {item['family_id']} | {item['learning_task_count']}/3 | {item['learning_attempts']} | {item['terminal_strict_passes']}/3 | {item['generated_skill_count']} | {item['best_word_jaccard']:.3f} | {pct(item['oracle_token_recall_from_learning_evidence'])} | {item['generated_verifier_marker_hits']} |"
        )
    lines += [
        "",
        "关键解释：`exact oracle` 的内容可能部分由 T1–T3 归纳得到，但它额外给出了标注者指定的 task→skill 子集，尤其是 T6 的 required-skill 组合。`curated-all-library` 使用同一 Env 的全部 5 个 curated skills，但不暴露 gold 子集；它与 exact-oracle 的差值衡量 gold 子集的选择/注意力优势，但不能再区分映射信息和减少无关 skill 阅读量这两部分。",
        "",
        "### T5/T6 概念能否由 T1–T3 推出？",
        "",
        "下面是受控概念词表的可推导性筛查。它分别检查 T5/T6 明示或 verifier 命名的高级概念，是否出现在 T1–T3 可见 instruction/失败反馈、generated skill 和 curated oracle 中。它能提供 annotation prior 的直接证据，但对未进入词表的语义仍需人工复核。",
        "",
        "| 模型 | 概念实例 | 可见且 generated 捕获 | 可见、oracle 捕获 | 可见、两种 skill 都漏 | Oracle 独有未见补入 | 两种 skill 均补入 | Generated 独有补入 | 三处都缺 | Author gap 命中 / T1–T3 未见 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in data["derivability"]["summaries"]:
        counts = item["category_counts"]
        lines.append(
            f"| {item['model']} | {item['concept_instances']} | "
            f"{counts.get('captured_from_visible_evidence', 0)} | "
            f"{counts.get('oracle_captures_visible_generated_misses', 0)} | "
            f"{counts.get('visible_missing_from_both_skills', 0)} | "
            f"{counts.get('oracle_adds_unseen_concept', 0)} | "
            f"{counts.get('both_skills_add_unseen_concept', 0)} | "
            f"{counts.get('model_adds_beyond_visible_evidence', 0)} | "
            f"{counts.get('missing_from_both_learning_and_oracle', 0)} | "
            f"{item.get('author_gap_metadata_hits', 0)} / "
            f"{item.get('author_gap_unseen_in_t1_t3', 0)} |"
        )
    lines += [
        "",
        "需要人工复核的非平凡概念实例：",
        "",
        "| 模型 | Task | 概念 | 分类 | T1–T3 | Generated | Oracle | Author gap meta |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for item in data["derivability"]["records"]:
        if item["category"] == "captured_from_visible_evidence":
            continue
        lines.append(
            f"| {item['model']} | {item['task_id']} | {item['concept']} | "
            f"{DERIVABILITY_ZH[item['category']]} | "
            f"{'✓' if item['in_t1_t3_evidence'] else '✗'} | "
            f"{'✓' if item['in_generated_skill'] else '✗'} | "
            f"{'✓' if item['in_curated_oracle'] else '✗'} | "
            f"{'✓' if item['in_author_gap_metadata'] else '✗'} |"
        )
    validity = data["measurement_validity"]
    lines += [
        "",
        "## 哪些 T5/T6 有资格测 Skill Evolution？",
        "",
        "这是一项 measurement-validity 筛查，而不是效果估计。只有高级要求在 T1–T3 有历史证据的任务，后续成功才有可能归因于 skill transfer；仍必须再由同任务 no-skill 对照证明增量。若高级要求只在当前 T5/T6 instruction 出现，模型做对最多说明现场执行能力，不能证明此前形成的 skill 有帮助。受控词表未覆盖的任务保持未分类。",
        "",
        "| 模型 | T5/T6 tasks | 有历史支持、可进入因果检验 | 仅当前题面 | 历史+现场混合 | 缺学习证据 | 词表未覆盖 | Oracle 覆盖全部概念 | Generated 覆盖全部概念 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in validity["summaries"]:
        counts = item["category_counts"]
        lines.append(
            f"| {item['model']} | {item['task_count']}（词表覆盖 {item['controlled_task_count']}） | "
            f"{item['eligible_for_causal_skill_claim']}/{item['controlled_task_count']} | "
            f"{counts.get('on_task_only', 0)} | "
            f"{counts.get('mixed_history_and_on_task', 0)} | "
            f"{counts.get('missing_learning_evidence', 0)} | "
            f"{counts.get('unclassified_no_controlled_concept', 0)} | "
            f"{item['oracle_all_concepts']}/{item['controlled_task_count']} | "
            f"{item['generated_all_concepts']}/{item['controlled_task_count']} |"
        )
    lines += [
        "",
        "| Env | 模型 | 可进入历史 skill 因果检验 | 仅当前题面 | 混合 | 缺学习证据 | 词表未覆盖 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in validity["by_environment"]:
        counts = item["category_counts"]
        lines.append(
            f"| {item['environment_id']} | {item['model']} | "
            f"{item['eligible_for_causal_skill_claim']}/{item['controlled_task_count']} | "
            f"{counts.get('on_task_only', 0)} | "
            f"{counts.get('mixed_history_and_on_task', 0)} | "
            f"{counts.get('missing_learning_evidence', 0)} | "
            f"{counts.get('unclassified_no_controlled_concept', 0)} |"
        )
    lines += [
        "",
        "当前最需要降级解释的任务（高级概念无 T1–T3 历史支持）：",
        "",
        "| 模型 | Task | 分类 | 高级概念 | Generated coverage | Oracle coverage |",
        "|---|---|---|---|---|---|",
    ]
    for item in validity["records"]:
        if item["category"] not in {"on_task_only", "unseen_not_explicit"}:
            continue
        lines.append(
            f"| {item['model']} | {item['task_id']} | "
            f"{MEASUREMENT_VALIDITY_ZH[item['category']]} | "
            f"{', '.join(item['controlled_concepts']) or '—'} | "
            f"{item['generated_coverage']} | {item['oracle_coverage']} |"
        )
    lines += [
        "",
        "## Curated Oracle 的任务覆盖范围审计",
        "",
        f"启发式筛查结果：`{json.dumps(data['oracle_scope']['counts'], ensure_ascii=False)}`。该筛查从任务说明与 verifier 提取受控概念，再检查绑定的 curated skill 是否覆盖；它用于定位人工复核对象，不把词面缺失直接当成语义缺失。",
        "",
        "### 题面是否已经把高级要求说透？",
        "",
        (
            f"受控词表覆盖 {data['oracle_scope']['concept_visibility']['tasks_with_controlled_concepts']}/60 题，"
            f"共 {data['oracle_scope']['concept_visibility']['concept_instances']} 个 task-concept 实例；"
            f"其中 {data['oracle_scope']['concept_visibility']['instruction_explicit_instances']} 个已在 instruction 显式出现，"
            f"{data['oracle_scope']['concept_visibility']['verifier_only_instances']} 个仅出现在 verifier check 命名。"
            "前者占比高意味着模型可能直接从题面完成要求，skill 的边际作用可能被压缩；这一点最终用 no-skill 配对对照确认。"
        ),
        "",
        "三个已人工确认的 scope gap：",
        "",
        "- E2 retry skill 明确采用简单固定延迟，却被用于 token refresh、jitter/idempotency 和 circuit-breaker 类 T5/T6。",
        "- E2 pagination skill 只覆盖基础页码分页，后续任务加入 cursor、并发插入、去重与跨 skill 组合。",
        "- E6 scheduling skill 明确使用 fixed UTC offsets，后续任务要求 DST/IANA zoneinfo、buffer 与 soft preferences。",
        "",
        "因此，oracle 仍失败有三种竞争解释：任务/模型太难、agent 没有正确执行 skill、curated skill 自身覆盖不足。不能只凭 oracle failure 判题目坏。",
        "",
        "| Task | Tier | Oracle skills | 风险 | Oracle 未覆盖的任务概念 | Scope 声明 |",
        "|---|---:|---|---|---|---|",
    ]
    for item in data["oracle_scope"]["rows"]:
        if item["scope_risk"] == "low":
            continue
        lines.append(
            f"| {item['task_id']} | T{item['tier']} | {', '.join(item['oracle_skill_ids'])} | {item['scope_risk']} | {', '.join(item['missing_concepts']) or '—'} | {'; '.join(item['scope_lines']) or '—'} |"
        )
    scope_results = [item for item in data["scope_condition_outcomes"] if item["n"]]
    if scope_results:
        lines += [
            "",
            "### Oracle 结果按 scope-risk 分层",
            "",
            "| 模型 | Scope risk | n | Oracle strict | Oracle outcome | Oracle process |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for item in scope_results:
            lines.append(
                f"| {item['model']} | {item['scope_risk']} | {item['n']} | {item['oracle_strict_passes']}/{item['n']} | {item['oracle_outcome_passes']}/{item['n']} | {item['oracle_process_passes']}/{item['n']} |"
            )
    lines += [
        "",
    ]
    lines += ["", "## Verifier 质量审计", ""]
    summary = data["verifier_audit"].get("summary", {})
    lines += [
        f"- 审计 T4–T6 共 {summary.get('task_count', 0)} 题；process checks {summary.get('process_checks_total', 0)} 个，outcome checks {summary.get('outcome_checks_total', 0)} 个。",
        f"- {summary.get('tasks_with_literal_or_regex_process_checks', 0)} 题含源码字面量/正则形态检查；{summary.get('tasks_with_exact_source_order_checks', 0)} 题要求源码 token 顺序。",
        f"- 有效过程权重分布：`{json.dumps(summary.get('effective_process_weight_histogram', {}), ensure_ascii=False)}`；没有未知权重。",
        f"- {summary.get('tasks_missing_rubric_yaml', 0)} 题缺 rubric.yaml；现有 test.sh 引用 rubric.yaml 的任务数为 {summary.get('tasks_whose_test_sh_reads_rubric_yaml', 0)}。",
        "",
        "### Process-only failure 按源码形态敏感度分层",
        "",
        "| 条件 | 形态风险 | n | Process-only | Outcome pass | Process pass | Strict pass |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in data["verifier_shape_outcomes"]:
        if not item["n"]:
            continue
        lines.append(
            f"| {CONDITION_ZH[item['condition']]} | {item['shape_risk']} | {item['n']} | {item['process_only_failures']}/{item['n']} | {item['outcome_passes']}/{item['n']} | {item['process_passes']}/{item['n']} | {item['strict_passes']}/{item['n']} |"
        )
    lines += [
        "",
        "## 代表性逐代码案例",
        "",
    ]
    for case in data["cases"]:
        lines += [f"### {case['task_id']}：{case['title']}", "", f"分类：**{case['kind']}**。{case['interpretation']}", ""]
        for obs in case["observations"]:
            failures = ", ".join(item.get("name", "") for item in obs["failed_process_tests"])
            condition = CONDITION_ZH.get(str(obs.get("condition")), str(obs.get("condition")))
            lines.append(f"- {obs['model']} / {condition}：strict={obs['strict']}，outcome={obs['outcome']}，process={obs['process']}，失败检查 `{failures}`。")
        lines.append("")
    lines += [
        "## 可靠性限制与下一步",
        "",
        "1. 每个 Env×Tier 只有 5 题，百分比必须连同分子/分母阅读。",
        "2. AP `Succeeded` 只表示平台执行结束，不能替代 verifier pass；本报告只从下载后的 replay records 与 verifier artifacts 计算。",
        "3. exact oracle 暴露标注者选定的 skill 子集；已加入同一内容全集、不暴露 gold 子集的 curated-all-library 控制。两者差值包含 gold 映射与搜索/注意力负担，不能进一步拆分。",
        "4. 最终结论必须在两个模型 × 六环境 × 四条件全部达到 15/15 后重算，并逐题审计 oracle 仍失败的轨迹。",
        "",
        "## 机器可复核证据",
        "",
        f"- 原始 artifacts：`{data['paths']['raw_root']}`",
        "- `t56_evidence.json`：任务结果、失败测试、轨迹和 skill 文本。",
        "- `t56_verifier_audit.json`：90 题 verifier 静态结构与有效评分权重。",
        "- `reference_solution_audit_all_envs.json`：90 个官方标准解在真实容器与官方 verifier 下的完整性审计。",
        "- `t56_report_data.json`：本报告的全部派生数据。",
        "",
    ]
    return "\n".join(lines)


def render_html(data: dict[str, Any]) -> str:
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    status = "完整证据" if data["is_complete"] else "研究进行中"
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SkillEvolBench T5/T6 Oracle 诊断</title>
<style>
:root{{--bg:#f5f7fb;--ink:#172033;--muted:#667085;--card:#fff;--line:#e4e9f2;--blue:#315efb;--cyan:#0aa6a6;--red:#d92d20;--amber:#dc8c00;--green:#16845b;--purple:#7c3aed;--shadow:0 12px 35px rgba(34,52,89,.08)}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(150deg,#f7f9ff 0,#f4f8f7 45%,#f8f5ff 100%);color:var(--ink);font:14px/1.55 Inter,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1480px;margin:auto;padding:32px}} .hero{{background:radial-gradient(circle at 85% 10%,rgba(255,255,255,.2),transparent 30%),linear-gradient(115deg,#152b61,#334fb4 58%,#7251c7);color:#fff;border-radius:24px;padding:32px 36px;box-shadow:var(--shadow)}}
.hero h1{{margin:6px 0 8px;font-size:30px;letter-spacing:-.5px}} .hero p{{max-width:930px;margin:0;color:#dce5ff}} .badge{{display:inline-block;padding:5px 11px;border-radius:20px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);font-weight:700}}
.grid{{display:grid;gap:16px}} .cards{{grid-template-columns:repeat(4,1fr);margin:18px 0}} .card,.panel{{background:var(--card);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}} .card{{padding:18px}} .card b{{display:block;font-size:28px;margin:4px 0}} .label{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.5px}}
.panel{{padding:22px;margin:18px 0}} h2{{font-size:20px;margin:0 0 16px}} h3{{font-size:16px;margin:0 0 6px}} .conclusion{{border-left:4px solid var(--blue);padding:12px 14px;margin:10px 0;background:#f8faff;border-radius:8px}} .conclusion.warn{{border-color:var(--amber);background:#fffaf0}} .conclusion.pending{{border-color:var(--red);background:#fff6f5}} .conclusion.good{{border-color:var(--green);background:#f2fbf7}}
.filters{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}} select,input{{padding:8px 10px;border:1px solid var(--line);border-radius:9px;background:#fff;color:var(--ink)}} table{{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}} th{{position:sticky;top:0;background:#f6f8fc;color:#475467;text-align:left;padding:9px;border-bottom:1px solid var(--line)}} td{{padding:9px;border-bottom:1px solid #edf0f5;vertical-align:top}} tr.click{{cursor:pointer}} tr.click:hover{{background:#f7f9ff}} .tablebox{{overflow:auto;max-height:620px;border:1px solid var(--line);border-radius:12px}}
.metric{{display:inline-flex;min-width:58px;justify-content:center;padding:4px 7px;border-radius:7px;font-weight:700}} .pass{{background:#e8f7ef;color:var(--green)}} .fail{{background:#fff0ef;color:var(--red)}} .missing{{background:#f1f3f6;color:#98a2b3}} .proc{{background:#fff6df;color:#9a6700}}
.heat{{display:grid;grid-template-columns:150px repeat(6,1fr);gap:5px;min-width:850px}} .heat>div{{padding:9px;border-radius:8px;text-align:center;background:#f3f5f9}} .heat .head{{font-weight:700;background:#eaf0ff}} .heat .v{{color:#fff;font-weight:800}} .v.high{{background:#16845b}} .v.mid{{background:#dc8c00}} .v.low{{background:#c84035}} .v.none{{background:#b3bac6}}
.two{{grid-template-columns:1fr 1fr}} .case{{padding:16px;border:1px solid var(--line);border-radius:14px;margin:10px 0}} .case .kind{{font-size:12px;color:var(--purple);font-weight:700}} details{{margin-top:8px}} pre{{white-space:pre-wrap;word-break:break-word;background:#111827;color:#dbeafe;padding:14px;border-radius:10px;max-height:420px;overflow:auto;font:12px/1.5 ui-monospace,SFMono-Regular,monospace}}
.drawer{{position:fixed;right:0;top:0;height:100vh;width:min(720px,95vw);background:#fff;box-shadow:-18px 0 45px rgba(18,29,55,.2);padding:24px;overflow:auto;transform:translateX(102%);transition:.25s;z-index:10}} .drawer.open{{transform:none}} .close{{float:right;border:0;background:#eef2f8;border-radius:20px;width:34px;height:34px;cursor:pointer}} .small{{font-size:12px;color:var(--muted)}} .bar{{height:9px;background:#e9edf4;border-radius:10px;overflow:hidden}} .bar span{{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--cyan))}}
@media(max-width:900px){{.wrap{{padding:14px}}.cards,.two{{grid-template-columns:1fr 1fr}}}} @media(max-width:600px){{.cards,.two{{grid-template-columns:1fr}}.hero{{padding:24px}}}}
</style></head><body><div class="wrap">
<section class="hero"><span class="badge">{status}</span><h1>T5/T6 为什么做不出来？</h1><p>Qwen 3.7 Max × SIG Fable · Self-generated / Exact Oracle / No skill / Curated-all-library 匹配对照。严格区分功能失败、过程 verifier 失败与 AP 执行失败。</p><div class="small" style="color:#dce5ff;margin-top:12px">生成于 {html.escape(data['generated_at_utc'])}</div></section>
<section class="grid cards" id="cards"></section>
<section class="panel"><h2>先看结论</h2><div id="conclusions"></div></section>
<section class="panel"><h2>先校正 “Oracle” 的含义</h2><p><code>exact_oracle</code> 是按 gold task→skill 映射注入仓库 curated 子集，不是任务 solution 或完整能力上界。curated skill 本身被设计为 gap-exposed scaffold，模型应从 T1–T3 补全它。</p><div class="grid cards" id="protocolDesign"></div></section>
<section class="panel"><h2>实验覆盖</h2><div class="heat" id="coverage"></div></section>
<section class="panel"><h2>运行中的完整对照矩阵</h2><p class="small">把 AP 生命周期与科学证据分开：Queued/Running/Succeeded 不等于已有可用结果；只有终态导出、artifact 审计通过且单元达到 15/15，才计入实验覆盖。</p><div id="runtimeProgress"></div></section>
<section class="panel"><h2>实验执行健康</h2><p class="small">AP 失败尝试与模型 T5/T6 结果分层展示。失败尝试保留作审计；只有完整、可复核的 episode 才能形成 15/15 科学单元。</p><div id="executionHealth"></div></section>
<section class="panel"><h2>题目资产完整性：官方标准解能否通过？</h2><p>这不是模型 baseline：Harbor oracle 直接执行仓库的 <code>solution/solve.sh</code>，再运行原 verifier，用来识别题目、标准解、容器或 verifier 的内部不一致。</p><div id="referenceIntegrity"></div></section>
<section class="panel"><h2>Pass rate 热力图</h2><div class="filters"><select id="hmModel"></select><select id="hmCond"></select><select id="hmMetric"><option value="strict">Strict</option><option value="outcome">Outcome</option><option value="process">Process</option></select><select id="hmTier"><option value="4">T4</option><option value="5" selected>T5</option><option value="6">T6</option></select></div><div class="heat" id="heatmap"></div><p class="small">每格最多 5 题；显示通过数/观测数，不能把小样本百分比当作稳定总体性能。</p></section>
<section class="grid two"><div class="panel"><h2>Qwen vs Fable 配对比较</h2><div class="tablebox"><table><thead><tr><th>条件/Tier/指标</th><th>n</th><th>Qwen</th><th>Fable</th><th>only Q/F</th><th>p</th></tr></thead><tbody id="modelCmpRows"></tbody></table></div></div><div class="panel"><h2>Skill 条件配对效应</h2><div class="tablebox"><table><thead><tr><th>模型/Tier/指标</th><th>对照</th><th>n</th><th>Δ</th><th>救回/损害</th></tr></thead><tbody id="effectRows"></tbody></table></div></div></section>
<section class="panel"><h2>四条件逐题因果判定</h2><p>每题同时看 Self-generated（S）、Exact oracle（E）、Curated-all（A）和 No-skill（N）的 outcome。四个条件不齐时保持“等待”，不把缺失记录当失败。</p><div id="causalDecision"></div></section>
<section class="panel"><h2>Skill 有挂载，但模型真的读了吗？</h2><p>目录/hash 是 treatment assignment；轨迹中的 SKILL.md 工具读取是 compliance。No-skill 与 skill 条件还存在“要求使用 library”的 prompt framing 差异，因此 no-skill 对比衡量整体处理效应；Exact 与 Curated-all framing 相同，更适合识别 gold 子集的选择/注意力优势。但 Exact 只挂载相关子集，而 Curated-all 挂载全 Env 五个 skills，所以该差值仍同时包含映射信息与搜索/阅读负担。</p><div class="tablebox"><table><thead><tr><th>模型/条件/Tier</th><th>n</th><th>读取任意 skill</th><th>Exact 全部期望均读取</th><th>读取时 Outcome</th><th>未读取时 Outcome</th></tr></thead><tbody id="skillUseRows"></tbody></table></div></section>
<section class="panel"><h2>六环境诊断总览</h2><p class="small">每张卡把 self-generated 的真实功能失败、process-only 噪声、双模型一致失败、官方标准解以及三组匹配对照放在一起。对照未齐的文字明确标为暂定。</p><div class="grid two" id="envCards"></div></section>
<section class="panel"><h2>逐 Env 的 T5/T6 失败地图</h2><div class="tablebox"><table><thead><tr><th>Env / Tier</th><th>Qwen 3.7 Max</th><th>SIG Fable</th></tr></thead><tbody id="failureRows"></tbody></table></div></section>
<section class="panel"><h2>失败归因总览</h2><p class="small">“已核实假阴性”要求逐代码证据；“形态敏感”只是筛查标签，仍需结合 exact-oracle/no-skill 与轨迹复核。</p><div class="tablebox"><table><thead><tr><th>Env/Tier</th><th>模型</th><th>覆盖/Strict</th><th>功能 gap</th><th>已核实假阴性</th><th>实质过程 gap</th><th>形态敏感</th><th>未决过程</th></tr></thead><tbody id="attributionRows"></tbody></table></div></section>
<section class="panel"><h2>T1–T3 学习与 Skill 来源审计</h2><div class="grid two" id="learningCards"></div><div class="filters" style="margin-top:16px"><select id="skillModel"></select><select id="skillEnv"></select><input id="skillSearch" placeholder="搜索 family / skill"></div><div class="tablebox"><table><thead><tr><th>Family</th><th>学习结果</th><th>生成 skill</th><th>Best Jaccard</th><th>Oracle evidence recall</th><th>Verifier markers</th></tr></thead><tbody id="skillRows"></tbody></table></div><p class="small">Evidence recall 仅是词面覆盖率，不代表逻辑可推导性。点击 family 查看 T1–T3 证据摘录、generated skill 与 curated oracle 全文。</p></section>
<section class="panel"><h2>T5/T6 概念可推导性与 Annotation Prior</h2><p>把每个高级概念分别放回 T1–T3 可见证据、generated skill、curated oracle 和仅题目作者可见的 gap metadata 中检查。重点看“可见但没总结”“oracle 补入未见概念”“两边都缺”三类。</p><div class="grid two" id="derivabilityCards"></div><div class="filters" style="margin-top:16px"><select id="derivabilityModel"><option value="all">全部模型</option><option value="qwen3.7-max">qwen3.7-max</option><option value="sig-fable">sig-fable</option></select><select id="derivabilityCategory"><option value="all">全部非平凡分类</option></select><input id="derivabilitySearch" placeholder="搜索 task / concept"></div><div class="tablebox"><table><thead><tr><th>Task / Family</th><th>模型</th><th>高级概念</th><th>分类</th><th>T1–T3</th><th>Generated</th><th>Oracle</th><th>Author gap meta</th></tr></thead><tbody id="derivabilityRows"></tbody></table></div><p class="small">Author gap meta 是 benchmark 作者的设计注释，不会注入模型。此处仍是受控词表筛查，不把词面缺失自动等同于逻辑不可推导。</p></section>
<section class="panel"><h2>哪些 T5/T6 真能测 Skill Evolution？</h2><p>先判断高级要求是否在 T1–T3 留下历史证据，再看匹配 no-skill 对照。若要求只在当前 T5/T6 题面出现，模型现场做对不能证明此前形成的 skill 有帮助；受控词表未覆盖的任务保持未分类。</p><div class="grid two" id="validityCards"></div><div class="tablebox"><table><thead><tr><th>模型/Env</th><th>可进入历史 skill 因果检验</th><th>仅当前题面</th><th>历史+现场混合</th><th>缺学习证据</th><th>词表未覆盖</th></tr></thead><tbody id="validityRows"></tbody></table></div><p class="small">“可进入因果检验”不等于已经证明 skill 有用；仍需同模型同任务的 Self / Exact / Curated-all / No-skill 四条件结果。</p></section>
<section class="panel"><h2>Curated Oracle 是否真的足以覆盖任务？</h2><p>仓库中的 curated skill 多数是基础工作流，不是 T5/T6 的 solution manual。Oracle 仍失败必须同时考虑 skill scope gap，不能直接判题目坏。</p><div id="scopeVisibility" class="grid cards"></div><div id="scopeCounts"></div><div class="tablebox"><table><thead><tr><th>Task</th><th>Oracle skills</th><th>风险</th><th>缺失概念</th><th>Author gap 命中</th><th>Verifier-only</th><th>Scope</th></tr></thead><tbody id="scopeRows"></tbody></table></div><h3 style="margin-top:16px">Oracle 结果按 scope risk 分层</h3><div id="scopeOutcomes" class="small"></div><p class="small">这是受控概念的启发式筛查。高风险项用于人工复核，不把词面缺失自动等同于语义缺失。</p></section>
<section class="panel"><h2>逐题匹配对照</h2><div class="filters"><select id="taskModel"></select><select id="taskEnv"></select><select id="taskTier"><option value="all">T4–T6</option><option value="4">T4</option><option value="5">T5</option><option value="6">T6</option></select><input id="taskSearch" placeholder="搜索 task / skill"></div><div class="tablebox"><table><thead><tr><th>Task</th><th>模型</th><th>Self-generated</th><th>Exact oracle</th><th>Curated all</th><th>No skill</th><th>判定</th></tr></thead><tbody id="taskRows"></tbody></table></div></section>
<section class="grid two"><div class="panel"><h2>Verifier 质量</h2><div id="audit"></div></div><div class="panel"><h2>Generated vs Oracle skill</h2><div id="skills"></div></div></section>
<section class="panel"><h2>逐代码案例</h2><p class="small">同一类 process-only failure 可能是真正缺少过程能力，也可能是 verifier 只接受某种源码形态；下面用真实 artifact 区分。</p><div id="cases"></div></section>
<section class="panel"><h2>解释边界</h2><ol><li>Oracle 失败不等于题目必坏；它可能仍超出模型执行能力。</li><li>Exact oracle 暴露标注者选择的 skill 子集；curated-all-library 提供同一 Env 的内容全集但不给 gold 子集。两者差值测的是选择/注意力优势，仍不能拆分映射信息与搜索成本。</li><li>最终结论要求两个模型、六环境、四条件全部 15/15，并审计每个 oracle 仍失败任务的轨迹。</li></ol></section>
</div><aside class="drawer" id="drawer"><button class="close" onclick="drawer.classList.remove('open')">×</button><div id="drawerBody"></div></aside>
<script>const D={blob};
const zh={{self_generated:'模型自生成',exact_oracle:'精确 Curated 子集（Oracle）',no_skill:'无 skill',curated_all:'Env 全量 Curated'}};
const derivabilityZh={{captured_from_visible_evidence:'T1–T3 可见且 generated 捕获',oracle_captures_visible_generated_misses:'T1–T3 可见，Oracle 捕获但 Generated 漏掉',visible_missing_from_both_skills:'T1–T3 可见，两种 skill 都漏掉',oracle_adds_unseen_concept:'仅 Oracle 补入的 T1–T3 未见概念',both_skills_add_unseen_concept:'Generated 与 Oracle 都补入未见概念',model_adds_beyond_visible_evidence:'仅 Generated 补入未见概念',missing_from_both_learning_and_oracle:'T1–T3、Generated 与 Oracle 都缺'}};
const validityZh={{history_supported:'高级要求均有 T1–T3 历史证据',mixed_history_and_on_task:'部分来自历史，部分需现场处理',on_task_only:'高级要求只在当前题面明示',unseen_not_explicit:'历史未见且题面未充分明示',missing_learning_evidence:'T1–T3 轨迹证据尚不完整',unclassified_no_controlled_concept:'受控词表未覆盖'}};
const verdict={{awaiting_matched_controls:'等待匹配对照',oracle_outcome_failure:'Oracle 功能仍失败',oracle_rescues_outcome:'Oracle 救回功能',oracle_rescues_strict_only:'仅救回 strict',no_oracle_rescue_needed_or_observed:'未观察到救回'}};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function status(c){{if(!c)return '<span class="metric missing">缺失</span>'; if(c.strict)return '<span class="metric pass">S✓ O✓</span>'; if(c.outcome)return '<span class="metric proc">S✗ O✓</span>'; return '<span class="metric fail">S✗ O✗</span>'}}
function options(el,vals,labels,all=false){{el.innerHTML=(all?'<option value="all">全部</option>':'')+vals.map(v=>`<option value="${{v}}">${{labels?.[v]||v}}</option>`).join('')}}
const complete=D.coverage.filter(x=>x.complete).length, total=D.coverage.length, selected=D.tasks.length, procOnly=D.tasks.filter(x=>x.classification==='process_only_failure').length;
cards.innerHTML=[['完整单元',`${{complete}}/${{total}}`],['已纳入任务记录',selected],['功能过但 strict 失败',procOnly],['源码形态敏感题',`${{D.verifier_audit.summary.tasks_with_literal_or_regex_process_checks}}/90`]].map(x=>`<div class="card"><span class="label">${{x[0]}}</span><b>${{x[1]}}</b></div>`).join('');
conclusions.innerHTML=D.conclusions.map(x=>`<div class="conclusion ${{x.level}}"><h3>${{esc(x.title)}}</h3>${{esc(x.body)}}</div>`).join('');
let pd=D.protocol_design;protocolDesign.innerHTML=[['Curated families',pd.family_count],['Author gap summaries',pd.gap_summary_count],['明确限制 curated',pd.gap_summaries_explicitly_limiting_curated+'/'+pd.gap_summary_count],['T2 enriched / T3 variant',(pd.role_counts['T2:enriched:learning']||0)+' / '+(pd.role_counts['T3:variant:learning']||0)]].map(x=>`<div class="card"><span class="label">${{x[0]}}</span><b>${{x[1]}}</b></div>`).join('');
coverage.innerHTML='<div class="head">模型 / 条件</div>'+['E1','E2','E3','E4','E5','E6'].map(x=>`<div class="head">${{x}}</div>`).join('')+['qwen3.7-max','sig-fable'].flatMap(m=>['self_generated','exact_oracle','curated_all','no_skill'].map(c=>{{let cells=D.coverage.filter(x=>x.model===m&&x.condition===c);return `<div>${{m}}<br><span class="small">${{zh[c]}}</span></div>`+cells.map(x=>`<div class="v ${{x.complete?'high':x.observed?'mid':'none'}}">${{x.observed}}/15</div>`).join('')}})).join('');
let rp=D.runtime_progress;let stageRows=rp.stages.map(x=>{{let counts=Object.entries(x.job_statuses).map(([k,v])=>`${{k}}=${{v}}`).join(', ')||'—';let group=x.group_url?`<a href="${{esc(x.group_url)}}" target="_blank" rel="noreferrer">${{esc(x.group_id)}}</a>`:'—';return `<tr><td><b>${{esc(x.model)}}</b><br><span class="small">${{zh[x.condition]}}</span></td><td>${{esc(x.status)}}</td><td>${{esc(counts)}}</td><td>${{x.complete_cells}}/6 · ${{x.observed_tasks}}/90</td><td>${{x.failed_group_count}}</td><td>${{group}}</td></tr>`}}).join('');let repairRows=rp.repairs.map(x=>{{let job=x.job_url?`<a href="${{esc(x.job_url)}}" target="_blank" rel="noreferrer">${{esc(x.job_id)}}</a>`:'—';return `<tr><td>${{esc(x.model)}} / ${{esc(x.environment_id)}}</td><td>${{esc(x.status)}}</td><td>${{esc(x.export_state)}}</td><td>${{x.attempt_count}}</td><td>${{job}}</td></tr>`}}).join('');runtimeProgress.innerHTML=`<div class="grid cards"><div class="card"><span class="label">科学证据完整单元</span><b>${{rp.complete_cells}}/${{rp.total_cells}}</b></div><div class="card"><span class="label">AP Active Jobs</span><b>${{rp.active_job_count}}</b></div><div class="card"><span class="label">终态待导出</span><b>${{rp.terminal_waiting_export}}</b></div><div class="card"><span class="label">Inventory 更新</span><b style="font-size:15px">${{esc(rp.inventory_updated_at_utc||'—')}}</b></div></div><div class="tablebox"><table><thead><tr><th>模型/条件</th><th>Matrix 状态</th><th>AP jobs</th><th>科学覆盖</th><th>历史失败组</th><th>AP group</th></tr></thead><tbody>${{stageRows}}</tbody></table></div><h3 style="margin-top:16px">Self-generated 缺失 Env 修复</h3><div class="tablebox"><table><thead><tr><th>模型/Env</th><th>Job 状态</th><th>Artifact 导出</th><th>尝试数</th><th>AP job</th></tr></thead><tbody>${{repairRows}}</tbody></table></div>`;
let eh=D.execution_attempts;executionHealth.innerHTML=`<div class="grid cards"><div class="card"><span class="label">失败 AP 尝试</span><b>${{eh.failed_attempt_count}}</b></div><div class="card"><span class="label">未纳入统计</span><b>${{eh.excluded_attempt_count}}</b></div><div class="card"><span class="label">贡献 T4–T6 的失败尝试</span><b>${{eh.failed_attempts_contributing_t56}}</b></div><div class="card"><span class="label">失败类型</span><b>${{Object.keys(eh.failure_counts).length}}</b></div></div><div>${{Object.entries(eh.failure_counts).map(([k,v])=>`<span class="metric fail">${{esc(k)}}: ${{v}}</span>`).join(' ')}}</div><details><summary>查看失败尝试证据</summary><div class="tablebox"><table><thead><tr><th>Label / Job</th><th>类型</th><th>Stage</th><th>进入 T4–T6</th><th>诊断</th></tr></thead><tbody>${{eh.failures.map(x=>`<tr><td>${{esc(x.label)}}<br><span class="small">${{esc(x.job_id)}}</span></td><td>${{esc(x.failure_kind)}}</td><td>${{esc(x.error_stage||'—')}}</td><td>${{x.contributes_t56_results?'是':'否'}}</td><td>${{esc(x.message||'—')}}</td></tr>`).join('')}}</tbody></table></div></details>`;
let ri=D.reference_integrity;let riRows=['E1','E2','E3','E4','E5','E6'].map(e=>{{let cells=[4,5,6].map(t=>ri.rows.find(x=>x.environment_id===e&&x.tier===t));return `<tr><td><b>${{e}}</b></td>${{cells.map(x=>`<td>${{x.passed}}/${{x.total}}</td>`).join('')}}</tr>`}}).join('');let riFailures=ri.failures.length?`<details><summary>查看 ${{ri.failures.length}} 个失败标准解</summary><pre>${{esc(JSON.stringify(ri.failures,null,2))}}</pre></details>`:'<p class="small">当前没有已观测的标准解失败。</p>';referenceIntegrity.innerHTML=`<div class="grid cards"><div class="card"><span class="label">覆盖</span><b>${{ri.total}}/90</b></div><div class="card"><span class="label">严格通过</span><b>${{ri.passed}}/${{ri.total||0}}</b></div><div class="card"><span class="label">状态</span><b style="font-size:20px">${{ri.all_reference_solutions_pass?'全部通过':ri.complete?'存在失败':'运行中'}}</b></div></div><div class="tablebox"><table><thead><tr><th>Env</th><th>T4</th><th>T5</th><th>T6</th></tr></thead><tbody>${{riRows}}</tbody></table></div>${{riFailures}}`;
options(hmModel,['qwen3.7-max','sig-fable']);options(hmCond,['self_generated','exact_oracle','curated_all','no_skill'],zh);options(taskModel,['qwen3.7-max','sig-fable'],null,true);options(taskEnv,['E1','E2','E3','E4','E5','E6'],null,true);
function renderHeat(){{let m=hmModel.value,c=hmCond.value,k=hmMetric.value,t=+hmTier.value;let rows=['E1','E2','E3','E4','E5','E6'].map(e=>D.aggregates.find(x=>x.model===m&&x.condition===c&&x.environment_id===e&&x.tier===t));heatmap.innerHTML='<div class="head">'+m+' · '+zh[c]+'</div>'+['E1','E2','E3','E4','E5','E6'].map(x=>`<div class="head">${{x}}</div>`).join('')+`<div>T${{t}} · ${{k}}</div>`+rows.map(x=>{{if(!x)return '<div class="v none">—</div>';let p=x[k]/x.n,cl=p>=.8?'high':p>=.4?'mid':'low';return `<div class="v ${{cl}}">${{x[k]}}/${{x.n}}</div>`}}).join('')}};[hmModel,hmCond,hmMetric,hmTier].forEach(x=>x.onchange=renderHeat);renderHeat();
modelCmpRows.innerHTML=D.model_comparisons.filter(x=>x.n).map(x=>`<tr><td>${{zh[x.condition]}} / T${{x.tier}} / ${{x.metric}}</td><td>${{x.n}}</td><td>${{x.qwen_pass}}</td><td>${{x.fable_pass}}</td><td>${{x.qwen_only}} / ${{x.fable_only}}</td><td>${{x.sign_test_p==null?'—':x.sign_test_p.toFixed(4)}}</td></tr>`).join('');
effectRows.innerHTML=D.effects.filter(x=>x.n).map(x=>`<tr><td>${{x.model}} / T${{x.tier}} / ${{x.metric}}</td><td>${{zh[x.treatment]}} − ${{zh[x.reference]}}</td><td>${{x.n}}</td><td>${{(100*x.delta).toFixed(1)}}pp</td><td>${{x.rescued}} / ${{x.harmed}}</td></tr>`).join('')||'<tr><td colspan="5" class="small">等待 oracle/no-skill 匹配结果</td></tr>';
let cd=D.causal_diagnosis;let cdCounts=Object.entries(cd.category_counts).map(([k,v])=>`<div class="case"><h3>${{esc(D.comparisons.find(x=>x.causal.category===k)?.causal.label||k)}}</h3><b style="font-size:24px">${{v}}</b><div class="small">个完整 T5/T6 模型×任务配对</div></div>`).join('');causalDecision.innerHTML=`<div class="grid cards"><div class="card"><span class="label">完整四条件</span><b>${{cd.complete}}/${{cd.expected}}</b></div><div class="card"><span class="label">已出现任务配对</span><b>${{cd.observed}}/${{cd.expected}}</b></div></div><div class="grid two">${{cdCounts||'<div class="case small">等待 matched controls</div>'}}</div><details><summary>判定规则</summary><div class="tablebox"><table><thead><tr><th>模式</th><th>解释</th></tr></thead><tbody><tr><td>N=1 且全部通过</td><td>无需 skill 也能做，skill 需求弱</td></tr><tr><td>N=0, S=1</td><td>生成 skill 带来直接正向迁移</td></tr><tr><td>N=1, S=0</td><td>生成 skill 造成负迁移</td></tr><tr><td>N=0, S=0, E=1, A=1</td><td>curated 内容有效，生成 skill 不足</td></tr><tr><td>N=0, S=0, E=1, A=0</td><td>gold 子集提供选择/注意力优势；映射信息和搜索成本不可再拆分</td></tr><tr><td>S=E=A=N=0</td><td>模型执行上限、oracle scope 或难度；reference 通过时不能直接判题目坏</td></tr></tbody></table></div></details>`;
skillUseRows.innerHTML=D.skill_use_adherence.filter(x=>x.n).map(x=>`<tr><td>${{x.model}} / ${{zh[x.condition]}} / T${{x.tier}}</td><td>${{x.n}}</td><td>${{x.any_skill_used}}/${{x.n}}</td><td>${{x.exact_expected_skills_fully_used==null?'—':x.exact_expected_skills_fully_used+'/'+x.n}}</td><td>${{x.used_outcome_passed}}/${{x.used_n}}</td><td>${{x.unused_outcome_passed}}/${{x.unused_n}}</td></tr>`).join('')||'<tr><td colspan="6" class="small">等待轨迹数据</td></tr>';
envCards.innerHTML=D.environment_diagnostics.map(x=>{{let m=Object.fromEntries(x.self_generated_by_model.map(y=>[y.model,y]));let ctrl=['exact_oracle','curated_all','no_skill'].map(c=>{{let y=x.controls[c];return `<span class="metric ${{y.observed===20?'pass':'missing'}}">${{zh[c]}} O ${{y.outcome_passed}}/${{y.observed}}</span>`}}).join(' ');return `<article class="case"><span class="kind">${{x.status==='matched_controls_complete'?'匹配对照完整':'暂定结论'}}</span><h3>${{x.environment_id}} · ${{esc(x.name)}}</h3><p>${{esc(x.capability)}}</p><div class="grid two"><div><b>Qwen</b><div class="small">覆盖 ${{m['qwen3.7-max'].observed}}/10 · Outcome ${{m['qwen3.7-max'].outcome_passed}} · Strict ${{m['qwen3.7-max'].strict_passed}} · Process-only ${{m['qwen3.7-max'].process_only_failures}}</div></div><div><b>Fable</b><div class="small">覆盖 ${{m['sig-fable'].observed}}/10 · Outcome ${{m['sig-fable'].outcome_passed}} · Strict ${{m['sig-fable'].strict_passed}} · Process-only ${{m['sig-fable'].process_only_failures}}</div></div></div><p class="small">双模型同题 outcome 失败 ${{x.both_models_outcome_fail}}/${{x.paired_task_count}} · reference ${{x.reference_strict_passed}}/${{x.reference_total}} · scope ${{esc(JSON.stringify(x.scope_risk_counts))}}</p><p>${{esc(x.current_read)}}</p><div>${{ctrl}}</div></article>`}}).join('');
function failureCell(x){{if(!x.observed)return '<span class="metric missing">0/5 未完成</span>';let details=x.tasks.map(t=>`<div><b>${{t.task_id}}</b> · ${{esc(t.task_slug)}} · ${{esc(t.classification)}}<br><span class="small">Skill: ${{esc((t.required_skills.length?t.required_skills:[t.primary_skill]).join(', '))}}<br>O: ${{t.failed_outcome.map(z=>esc(z.name+': '+z.message)).join('; ')||'无'}}<br>P: ${{t.failed_process.map(z=>esc(z.name+': '+z.message)).join('; ')||'无'}}</span></div>`).join('');return `<span class="metric ${{x.strict_failures?'fail':'pass'}}">失败 ${{x.strict_failures}}/${{x.observed}}</span>${{details}}`}};
failureRows.innerHTML=['E1','E2','E3','E4','E5','E6'].flatMap(e=>[5,6].map(t=>{{let q=D.failure_map.find(x=>x.model==='qwen3.7-max'&&x.environment_id===e&&x.tier===t),f=D.failure_map.find(x=>x.model==='sig-fable'&&x.environment_id===e&&x.tier===t);return `<tr><td><b>${{e}} / T${{t}}</b></td><td>${{failureCell(q)}}</td><td>${{failureCell(f)}}</td></tr>`}})).join('');
attributionRows.innerHTML=D.failure_attribution.summaries.map(x=>{{let c=x.cause_counts;return `<tr><td><b>${{x.environment_id}} / T${{x.tier}}</b></td><td>${{x.model}}</td><td>${{x.observed}}/5 · ${{x.strict_passed}}/${{x.observed}}</td><td>${{c.functional_gap||0}}</td><td>${{c.verified_verifier_false_negative||0}}</td><td>${{c.substantive_process_gap||0}}</td><td>${{c.shape_sensitive_process_only||0}}</td><td>${{c.unresolved_process_only||0}}</td></tr>`}}).join('');
learningCards.innerHTML=Object.entries(D.learning.by_model).map(([m,x])=>`<div class="case"><h3>${{m}}</h3><p><b>${{x.learning_tasks}}</b> 个 T1–T3 · <b>${{x.learning_attempts}}</b> 次尝试 · 最终通过 ${{x.terminal_strict_passes}} · 修复成功 ${{x.repaired_to_pass}}</p><p class="small">same-session 异常 ${{x.same_session_failures}} · active skills/families ${{x.active_skills}}/${{x.families}} · 多 skill families ${{x.families_with_multiple_skills}} · 含 verifier 术语 skills ${{x.skills_with_verifier_markers}}</p></div>`).join('');
options(skillModel,['qwen3.7-max','sig-fable'],null,true);options(skillEnv,['E1','E2','E3','E4','E5','E6'],null,true);
function renderSkills(){{let q=skillSearch.value.toLowerCase(),rows=D.learning.families.filter(x=>(skillModel.value==='all'||x.model===skillModel.value)&&(skillEnv.value==='all'||x.environment_id===skillEnv.value)&&JSON.stringify(x).toLowerCase().includes(q));skillRows.innerHTML=rows.map(x=>`<tr class="click" data-key="${{x.model}}|${{x.family_id}}"><td><b>${{x.family_id}}</b><br><span class="small">${{x.model}} · ${{x.expected_oracle_slug}}</span></td><td>${{x.terminal_strict_passes}}/${{x.learning_task_count}} 通过 · ${{x.learning_attempts}} attempts</td><td>${{x.generated_skill_count}} · ${{x.generated_slugs.join(', ')}}</td><td>${{x.best_word_jaccard.toFixed(3)}}</td><td>${{x.oracle_token_recall_from_learning_evidence==null?'—':(100*x.oracle_token_recall_from_learning_evidence).toFixed(1)+'%'}}</td><td>${{x.generated_verifier_marker_hits}}</td></tr>`).join('');skillRows.querySelectorAll('tr').forEach(tr=>tr.onclick=()=>showFamily(...tr.dataset.key.split('|')))}};[skillModel,skillEnv].forEach(x=>x.onchange=renderSkills);skillSearch.oninput=renderSkills;renderSkills();
function showFamily(model,id){{let x=D.learning.families.find(x=>x.model===model&&x.family_id===id);drawerBody.innerHTML=`<h2>${{x.family_id}} · ${{model}}</h2><p>学习任务 ${{x.learning_task_count}}/3 · 最终通过 ${{x.terminal_strict_passes}} · attempts ${{x.learning_attempts}} · generated skills ${{x.generated_skill_count}}</p><p>Best Jaccard ${{x.best_word_jaccard.toFixed(3)}} · Oracle evidence recall ${{x.oracle_token_recall_from_learning_evidence==null?'—':(100*x.oracle_token_recall_from_learning_evidence).toFixed(1)+'%'}} · verifier markers ${{x.generated_verifier_marker_hits}}</p><details open><summary>Generated skill 全文</summary><pre>${{esc(x.generated_text)}}</pre></details><details><summary>Curated oracle 全文</summary><pre>${{esc(x.curated_text)}}</pre></details><details><summary>T1–T3 可见证据摘录</summary><pre>${{esc(x.learning_evidence_excerpt)}}</pre></details>`;drawer.classList.add('open')}}
derivabilityCards.innerHTML=D.derivability.summaries.map(x=>{{let c=x.category_counts;return `<div class="case"><h3>${{x.model}}</h3><p><b>${{x.concept_instances}}</b> 个 task-concept 实例</p><p class="small">可见且 Generated 捕获 ${{c.captured_from_visible_evidence||0}} · 可见、Oracle 捕获 ${{c.oracle_captures_visible_generated_misses||0}} · 可见、两种 skill 都漏 ${{c.visible_missing_from_both_skills||0}} · Oracle 独有未见补入 ${{c.oracle_adds_unseen_concept||0}} · 两种 skill 均补入 ${{c.both_skills_add_unseen_concept||0}} · Generated 独有补入 ${{c.model_adds_beyond_visible_evidence||0}} · 三处都缺 ${{c.missing_from_both_learning_and_oracle||0}} · Author gap meta 命中 ${{x.author_gap_metadata_hits}}，其中 T1–T3 未见 ${{x.author_gap_unseen_in_t1_t3}}</p></div>`}}).join('');
options(derivabilityCategory,Object.keys(derivabilityZh).filter(x=>x!=='captured_from_visible_evidence'),derivabilityZh,true);
function renderDerivability(){{let q=derivabilitySearch.value.toLowerCase();let rows=D.derivability.records.filter(x=>x.category!=='captured_from_visible_evidence'&&(derivabilityModel.value==='all'||x.model===derivabilityModel.value)&&(derivabilityCategory.value==='all'||x.category===derivabilityCategory.value)&&JSON.stringify(x).toLowerCase().includes(q));derivabilityRows.innerHTML=rows.map(x=>`<tr><td><b>${{x.task_id}}</b><br><span class="small">${{x.family_id}} · T${{x.tier}}</span></td><td>${{x.model}}</td><td>${{esc(x.concept)}}</td><td>${{esc(derivabilityZh[x.category])}}</td><td>${{x.in_t1_t3_evidence?'✓':'✗'}}</td><td>${{x.in_generated_skill?'✓':'✗'}}</td><td>${{x.in_curated_oracle?'✓':'✗'}}</td><td>${{x.in_author_gap_metadata?'✓':'✗'}}</td></tr>`).join('')||'<tr><td colspan="8" class="small">当前过滤条件无记录</td></tr>'}};[derivabilityModel,derivabilityCategory].forEach(x=>x.onchange=renderDerivability);derivabilitySearch.oninput=renderDerivability;renderDerivability();
validityCards.innerHTML=D.measurement_validity.summaries.map(x=>{{let c=x.category_counts;return `<div class="case"><h3>${{x.model}}</h3><p><b>${{x.eligible_for_causal_skill_claim}}/${{x.controlled_task_count}}</b> 个受控词表覆盖任务可进入历史 skill 因果检验</p><p class="small">全部 T5/T6 ${{x.task_count}} · 仅当前题面 ${{c.on_task_only||0}} · 历史+现场混合 ${{c.mixed_history_and_on_task||0}} · 缺学习证据 ${{c.missing_learning_evidence||0}} · 词表未覆盖 ${{c.unclassified_no_controlled_concept||0}} · Oracle 全覆盖概念 ${{x.oracle_all_concepts}}/${{x.controlled_task_count}} · Generated 全覆盖概念 ${{x.generated_all_concepts}}/${{x.controlled_task_count}}</p></div>`}}).join('');validityRows.innerHTML=D.measurement_validity.by_environment.map(x=>{{let c=x.category_counts;return `<tr><td><b>${{x.model}}</b> / ${{x.environment_id}}</td><td>${{x.eligible_for_causal_skill_claim}}/${{x.controlled_task_count}}</td><td>${{c.on_task_only||0}}</td><td>${{c.mixed_history_and_on_task||0}}</td><td>${{c.missing_learning_evidence||0}}</td><td>${{c.unclassified_no_controlled_concept||0}}</td></tr>`}}).join('');
let cv=D.oracle_scope.concept_visibility;scopeVisibility.innerHTML=[['受控概念实例',cv.concept_instances],['Instruction 明示',cv.instruction_explicit_instances],['Verifier-only',cv.verifier_only_instances],['Author gap meta 命中',cv.author_gap_metadata_instances],['涉及任务',cv.tasks_with_controlled_concepts+'/60']].map(x=>`<div class="card"><span class="label">${{x[0]}}</span><b>${{x[1]}}</b></div>`).join('');
scopeCounts.innerHTML=Object.entries(D.oracle_scope.counts).map(([k,v])=>`<span class="metric ${{k==='high'?'fail':k==='medium'?'proc':'pass'}}">${{k}}: ${{v}}</span>`).join(' ');scopeRows.innerHTML=D.oracle_scope.rows.filter(x=>x.scope_risk!=='low'||x.verifier_only_concepts.length).map(x=>`<tr><td><b>${{x.task_id}}</b><br><span class="small">${{esc(x.task_slug)}}</span></td><td>${{esc(x.oracle_skill_ids.join(', '))}}</td><td><span class="metric ${{x.scope_risk==='high'?'fail':'proc'}}">${{x.scope_risk}}</span></td><td>${{esc(x.missing_concepts.join(', ')||'—')}}</td><td>${{esc(x.task_concepts_in_author_gaps.join(', ')||'—')}}</td><td>${{esc(x.verifier_only_concepts.join(', ')||'—')}}</td><td>${{esc(x.scope_lines.join('; ')||'—')}}</td></tr>`).join('');
scopeOutcomes.innerHTML=D.scope_condition_outcomes.filter(x=>x.n).map(x=>`<div>${{x.model}} · ${{x.scope_risk}} · n=${{x.n}} · strict ${{x.oracle_strict_passes}}/${{x.n}} · outcome ${{x.oracle_outcome_passes}}/${{x.n}} · process ${{x.oracle_process_passes}}/${{x.n}}</div>`).join('')||'等待 exact-oracle 结果';
function renderTasks(){{let q=taskSearch.value.toLowerCase();let rows=D.comparisons.filter(x=>(taskModel.value==='all'||x.model===taskModel.value)&&(taskEnv.value==='all'||x.environment_id===taskEnv.value)&&(taskTier.value==='all'||x.tier==taskTier.value)&&JSON.stringify(x).toLowerCase().includes(q));taskRows.innerHTML=rows.map((x,i)=>`<tr class="click" data-key="${{x.model}}|${{x.task_id}}"><td><b>${{x.task_id}}</b><br><span class="small">${{esc(x.task_slug)}} · ${{esc(x.primary_skill)}}</span></td><td>${{x.model}}</td><td>${{status(x.conditions.self_generated)}}</td><td>${{status(x.conditions.exact_oracle)}}</td><td>${{status(x.conditions.curated_all)}}</td><td>${{status(x.conditions.no_skill)}}</td><td><b>${{esc(x.causal.label)}}</b><br><span class="small">${{esc(x.causal.pattern||verdict[x.verdict])}}</span></td></tr>`).join('');taskRows.querySelectorAll('tr').forEach(tr=>tr.onclick=()=>showTask(...tr.dataset.key.split('|')))}};[taskModel,taskEnv,taskTier].forEach(x=>x.onchange=renderTasks);taskSearch.oninput=renderTasks;renderTasks();
function showTask(model,id){{let x=D.comparisons.find(x=>x.model===model&&x.task_id===id);let blocks=Object.entries(x.conditions).map(([name,c])=>`<h3>${{zh[name]}}</h3>${{c?`<p>${{status(c)}} score=${{c.score??'—'}} · job=${{esc(c.job_id)}}</p><p class="small">实际读取 skills: ${{esc(c.skills_actually_used.join(', ')||'none')}}<br>Oracle 内容证明: ${{esc(Object.entries(c.oracle_content_verification||{{}}).map(([k,v])=>k+': '+v).join(', ')||'—')}}<br>record: ${{esc(c.record_path)}}<br>trajectory: ${{esc(c.trajectory_path)}}</p><details><summary>失败测试 (${{c.failed_tests.length}})</summary><pre>${{esc(JSON.stringify(c.failed_tests,null,2))}}</pre></details>`:'<p class="small">尚无结果</p>'}}`).join('');drawerBody.innerHTML=`<h2>${{x.task_id}}</h2><p>${{esc(x.task_slug)}} · T${{x.tier}} · ${{x.environment_id}}</p><div class="conclusion ${{x.causal.complete?'good':'pending'}}"><h3>${{esc(x.causal.label)}} · ${{esc(x.causal.pattern||'')}}</h3>${{esc(x.causal.explanation)}}</div><p><b>需要的 skills</b><br>${{esc(x.required_skills.join(', ')||x.primary_skill)}}</p>${{blocks}}`;drawer.classList.add('open')}}
let a=D.verifier_audit.summary;audit.innerHTML=`<div class="card"><span class="label">过程 / 功能 checks</span><b>${{a.process_checks_total}} / ${{a.outcome_checks_total}}</b></div><p><b>${{a.tasks_with_literal_or_regex_process_checks}}/90</b> 含源码字面量或正则检查；<b>${{a.tasks_with_effective_process_weight_50_percent}}/90</b> 的过程权重为 50%。</p><p>形态敏感度：${{Object.entries(a.process_shape_sensitivity).map(([k,v])=>`${{k}}=${{v}}`).join(' · ')}}</p><h3>Process-only 分层</h3>${{D.verifier_shape_outcomes.filter(x=>x.n).map(x=>`<div class="small">${{zh[x.condition]}} · ${{x.shape_risk}} · process-only ${{x.process_only_failures}}/${{x.n}} · outcome ${{x.outcome_passes}}/${{x.n}} · process ${{x.process_passes}}/${{x.n}}</div>`).join('')}}`;
skills.innerHTML=Object.entries(D.skills.by_model).map(([m,x])=>`<div class="case"><h3>${{m}}</h3><p>skill 对数 <b>${{x.n}}</b> · 改名 ${{x.renamed}} · 完全相同 ${{x.exact_equal}}</p><div class="small">中位 word Jaccard ${{x.median_word_jaccard?.toFixed(3)??'—'}} · 长度比 ${{x.median_length_ratio?.toFixed(2)??'—'}}</div></div>`).join('')+'<p class="small">词面相似度低只说明表达和覆盖范围不同，不能单独证明 skill 质量差；最终要结合 matched oracle rescue。</p>';
cases.innerHTML=D.cases.map((x,i)=>`<article class="case"><span class="kind">${{x.kind}}</span><h3>${{x.task_id}} · ${{x.title}}</h3><p>${{x.interpretation}}</p>${{x.observations.map(o=>`<p><b>${{o.model}} / ${{zh[o.condition]||o.condition}}</b> · strict=${{o.strict}} outcome=${{o.outcome}} process=${{o.process}} · ${{o.failed_process_tests.map(t=>t.name).join(', ')}}</p>${{o.files.map(f=>`<details><summary>${{o.model}} / ${{zh[o.condition]||o.condition}} / ${{f.name}}</summary><div class="small">${{esc(f.path)}}</div><pre>${{esc(f.content)}}</pre></details>`).join('')}}`).join('')}}<details><summary>Process verifier 源码</summary><div class="small">${{esc(x.process_verifier_path)}}</div><pre>${{esc(x.process_verifier)}}</pre></details></article>`).join('');
</script></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--verifier-audit", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-audit", type=Path)
    args = parser.parse_args()
    evidence = load_json(args.evidence)
    audit = load_json(args.verifier_audit)
    reference_audit = load_json_optional(args.reference_audit)
    study_root = args.raw_root.resolve().parent
    inventory = load_json_optional(study_root / "watcher" / "inventory.json")
    matrix_state = load_json_optional(
        study_root / "matrix-watcher" / "state.json"
    )
    data = build_payload(
        evidence,
        audit,
        args.raw_root,
        reference_audit,
        inventory,
        matrix_state,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data_path = args.output_dir / "t56_report_data.json"
    md_path = args.output_dir / "t56_oracle_study_report_zh.md"
    html_path = args.output_dir / "t56_oracle_study_report_zh.html"
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")
    html_path.write_text(render_html(data), encoding="utf-8")
    print(json.dumps({
        "data": str(data_path.resolve()), "markdown": str(md_path.resolve()),
        "html": str(html_path.resolve()), "is_complete": data["is_complete"],
        "complete_cells": sum(row["complete"] for row in data["coverage"]),
        "total_cells": len(data["coverage"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
