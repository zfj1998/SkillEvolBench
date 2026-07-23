#!/usr/bin/env python3
"""Build a Chinese Markdown and standalone interactive HTML T4-T6 report."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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
    "verified_benchmark_false_negative": "已核实的 outcome/verifier 假阴性",
    "mixed_benchmark_and_model_gap": "题目缺陷与模型执行 gap 混合",
    "invalid_or_underdetermined_task": "不可满足或欠规定题目",
    "verified_verifier_false_negative": "已核实的 process verifier 假阴性",
    "substantive_process_gap": "有实际泛化意义的过程约束缺失",
    "shape_sensitive_process_only": "源码形态敏感的 process-only 失败",
    "unresolved_process_only": "尚待人工复核的 process-only 失败",
}

# These labels are deliberately model-task specific. A hidden contract can be
# the sole reason one output fails while another model genuinely computes the
# wrong values on the same task.
VERIFIED_OUTCOME_FALSE_NEGATIVE_PAIRS = frozenset({
    ("qwen3.7-max", "E1-LS4-T5"),
    ("sig-fable", "E1-LS4-T5"),
    ("sig-fable", "E3-LS2-T6"),
    ("sig-fable", "E3-LS3-T6"),
    ("qwen3.7-max", "E3-LS4-T6"),
    ("qwen3.7-max", "E4-LS1-T5"),
    ("qwen3.7-max", "E4-LS3-T5"),
    ("qwen3.7-max", "E4-LS4-T6"),
    ("qwen3.7-max", "E5-LS3-T6"),
    ("qwen3.7-max", "E5-LS4-T6"),
    ("sig-fable", "E5-LS4-T6"),
    ("qwen3.7-max", "E6-LS2-T6"),
    ("sig-fable", "E6-LS1-T6"),
    ("sig-fable", "E6-LS2-T6"),
})
MIXED_BENCHMARK_MODEL_GAP_PAIRS = frozenset({
    ("qwen3.7-max", "E2-LS1-T6"),
    ("sig-fable", "E2-LS1-T6"),
    ("qwen3.7-max", "E5-LS3-T5"),
    ("sig-fable", "E5-LS3-T5"),
    ("qwen3.7-max", "E5-LS5-T6"),
    ("qwen3.7-max", "E6-LS1-T6"),
    ("qwen3.7-max", "E6-LS3-T6"),
    ("sig-fable", "E6-LS3-T6"),
})
INVALID_OR_UNDERDETERMINED_TASKS = frozenset({"E6-LS4-T6"})
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
    "E1-LS2-T6": {
        "title": "两模型都只做了表层 SQLAlchemy 2.0 迁移，未完成会话与事务语义",
        "kind": "真实的跨文件组合执行 gap",
        "interpretation": (
            "两模型都升级了依赖并把裸 SQL 包进 text()，但没有按迁移日志建立 SessionLocal/会话边界。"
            "Qwen 继续使用 engine 连接且 total_amount_for_user 只取第一笔金额，config 仍是 sqlite；"
            "Fable 用 postgresql URL 却仍通过 engine.connect() 写入且不 commit。因而跨会话持久化、聚合和并发检查失败。"
            "这是任务正文、错误日志和公开源码足以支持的真实工程修复，不是 verifier 形态误判；"
            "它说明 dependency-conflict 与 multi-file-fix 两类历史 skill 即使都被注入，模型仍可能无法完成组合实现。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "project/src/config.py",
            "project/src/database.py",
            "project/src/services/order_service.py",
            "project/src/services/report_service.py",
        ],
    },
    "E1-LS4-T5": {
        "title": "两种 skill 都完成了端到端修复，却被隐藏 monkeypatch seam 与字面量检查判失败",
        "kind": "隐藏可注入性合同与源码扫描假阴性（强任务缺陷）",
        "interpretation": (
            "Qwen 的 self-generated 与 exact-oracle 都通过 7/8 outcome tests；两份实现都移除了 service 的"
            "吞错、让 route 返回 500/404，并在 UI 中把 error 放到 no-data 前。唯一 outcome 失败来自隐藏测试"
            "把 backend.database.db 替换成 FailingDB，但两份实现都保留了 starter 的 "
            "from backend.database import db，因此 service 持有旧对象，测试替换没有生效。题面要求的是"
            "实际间歇故障后的 500→下一次 200，并没有声明必须支持这种 monkeypatch seam；官方 solution 却"
            "特意改成 import backend.database as db_module 后逐次取 db_module.db。更强的证据是其余四个"
            "hidden tests 也用同样的无效替换，却因原始 DB 的 modulo-3 全局调用计数碰巧通过，结果依赖测试"
            "顺序而非替身。Process 侧同样有字面量假阴性：P2 只在 UserProfile.jsx 搜 status/error，忽略"
            "已有 classifyProfileResponse helper；P3 只认 routes.py 中的 500 或 services.py 中的 raise/"
            "ConnectionError，exact 实现调用 error_status() 因而被误判。两种 skill 同结果不是 oracle"
            "不足或模型不会错误传播，而是任务把未公开的测试可注入性与源码布局混入 reward。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "backend/database.py",
            "backend/services.py",
            "backend/routes.py",
            "backend/error_payloads.py",
            "backend/http_policy.py",
            "frontend/UserProfile.jsx",
            "frontend/profile_state.js",
        ],
    },
    "E2-LS1-T6": {
        "title": "公开测试与 fixture 冲突；Qwen 被隐藏接口卡住，Fable 两种条件都未落笔",
        "kind": "误导性公开测试与模型执行停滞（强任务缺陷）",
        "interpretation": (
            "requests.json 含 u1–u4 四条都具备 user_id/amount 的有效输入，currency/timezone 又明确应在 enrich/fallback"
            "阶段补齐；但项目随附 public_tests/test_transactions.py 硬要求 results 长度为 3。官方 reference 不修改"
            "fixture，实际产生 4 个正常 transaction，因而该 public test 失败；同一 reference 在官方 verifier 下却"
            "严格 100/100。Qwen self-generated 已正确完成 validate→enrich→normalize→call、404 fallback、UTC"
            "和 USD 归一化，hidden outcome 过 4/5；唯一失败是 validate_record 返回 missing 列表并在 loop 中"
            "本地 skip，而 hidden test 强制要求直接抛 ValueError。题面只说 fail locally，curated pre-call skill"
            "还明确推荐 structured errors，因此该异常类型是未公开接口。它的 process 失败也主要是源码扫描："
            "pipeline-order 用 text.index 命中了 import 中更早的 send_transaction，UTC fallback 明明在"
            "fallback_policy.py 却只扫描 transactions.py；reference 通过改 import 形态规避。另一方面，Fable"
            "self-generated 和 exact-oracle 都注意到 public-test 矛盾，分别消耗 25,029 与 23,495"
            "输出 tokens 反复讨论应删 u4、改 fixture 还是扩 REQUIRED_FIELDS，最终都只执行 read/skill/ls/pytest/"
            "只读 Python probe，没有任何 edit/write，保留 starter 后同得 0.25。Exact 条件已实际打开两个指定"
            "oracle skills，仍无法把不一致的公开信号变成行动。这一失败首先是 task 的误导性测试造成执行停滞，"
            "其次是模型无法及时收敛；不能用它证明 generated skill 比 oracle 差，也不能把 oracle failure 解释为"
            "高级 skill 本身无效。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "transactions.py",
            "requests.json",
            "public_tests/test_transactions.py",
            "fallback_policy.py",
        ],
        "task_source_files": [
            "environment/transactions.py",
            "environment/requests.json",
            "environment/public_tests/test_transactions.py",
        ],
    },
    "E2-LS2-T6": {
        "title": "Exact 只救回了 success_budget 字面量检查，没有救回任何功能",
        "kind": "Strict-only 源码形态变化，不是 Oracle 功能迁移",
        "interpretation": (
            "Qwen/Fable self-generated 与 Fable exact-oracle 的全部 outcome tests 都通过，真实 breaker 行为"
            "相同：连续失败开路、cooldown 内 fail-fast、到时 half-open probe、成功后立即关闭。两份 self 实现"
            "已让 next_probe_time"
            "只使用 recovery_timeout，却保留 recent_success_budget 的无害记账字段；process verifier 只要"
            "breaker_client.py 出现 success_budget 字符串就判失败。Exact 实现删除这些 token，strict 从"
            "0.9375 变为 1.0。关键是 generated retry skill 和 curated retry/orchestration skills 都没有"
            "circuit-breaker 或 success_budget 知识，任务正文反而直接写了“Ignore legacy success_budget”。"
            "所以这次 exact strict rescue 不能归功于 annotation prior 或更高质量 oracle skill，只是模型从"
            "当前题面采取了更彻底的源码清理并满足字面量检查；它也解释了为什么 20 个当前 self/exact 配对"
            "可以出现 strict 正负交换但 outcome rescue 仍为 0。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "breaker_client.py",
            "cooldown_policy.py",
            "breaker_state.py",
        ],
    },
    "E2-LS3-T5": {
        "title": "Generated strict 胜出来自 verifier 位置过拟合，功能上与 Oracle 相同",
        "kind": "Generated skill 的 verifier-specific 过拟合反例",
        "interpretation": (
            "Fable self-generated 与 exact-oracle 都通过全部 outcome tests：都跟随运行期 metadata，"
            "最终抓取 8 页、80 行。两者唯一差异是源码布局。Self 实现把 should_continue(response)"
            "导入 solution.py，并在生成 skill 中明确记录了 hidden process check 会 grep entry module、"
            "要把 has_more/total_pages 等字面量放到被扫描文件；因此严格 1.0。Exact 实现则把"
            "has_more 与 total_pages 的真实判断封装在 page_plan.next_page，把每页 metadata snapshot"
            "封装在 report_cache，solution.py 每轮调用这些 helper，功能正确且模块化，但 process verifier"
            "只读取 solution.py，并要求其中出现 has_more 或至少两个 total_pages 字面量，故以"
            "rechecks_metadata_or_has_more 判到 0.75。仓库 curated pagination skill 只描述通用分页，"
            "没有该固定文件扫描先验；generated skill 则大篇幅总结了 grep、literal token 和 file-location"
            "陷阱。这个 self>oracle 的 strict harm 是 T1–T3 verifier 细节迁移/测试过拟合，不是更强的"
            "分页语义能力；也直接证明只看 strict reward 会把 skill evolve 与 verifier gaming 混在一起。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "solution.py",
            "page_plan.py",
            "report_cache.py",
        ],
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
    "E3-LS3-T5": {
        "title": "Join key 已修对，但两模型额外去重 master rows 导致统计偏差",
        "kind": "模型过度修复 / 真实数据语义 gap",
        "interpretation": (
            "两模型都把 users.id 正确连到 transactions.user_id，过程检查全部通过；失败来自它们同时改写"
            "schema_cleaner 并对 users.id 做 drop_duplicates。题目只要求修 merge path，starter 与 reference"
            "保留清洗后仍重复的 master rows；额外去重把 merged_row_count、平均交易数和 totals 一起改变。"
            "这不是错误 join key，也不是题目不可解，而是模型在已有正确清洗逻辑上过度泛化了“去重”经验。"
        ),
        "files": [
            "join_selector.py",
            "merge_user_spending.py",
            "schema_cleaner.py",
            "output.json",
        ],
    },
    "E3-LS1-T6": {
        "title": "两种条件 outcome 全过，三类等价实现仍被固定 token 扫描拒绝",
        "kind": "跨模块、常量与 regex 写法的 process 假阴性",
        "interpretation": (
            "Fable self-generated 与 exact-oracle 都通过全部 outcome tests，正确清理逗号/货币/会计"
            "负数/零宽字符，得到四个 region 的精确 totals，并按 1.0% tolerance 生成正确 validation。Self"
            "唯一 process 失败是 totals_validator 使用 TOLERANCE_PCT=1.0 后比较 delta_pct <="
            "TOLERANCE_PCT；verifier 只接受源码中连续字面量 <= 1.0。Exact 另两项失败同样是形态问题："
            "它用 ACCOUNTING_NEGATIVE regex + is_negative 处理括号负数，而检查只认 negative_mask 或"
            "startswith('(')；它从 schema_inspector.ZERO_WIDTH_CHARS 导入并循环移除 ZWSP，而检查只在"
            "amount_cleaner.py 搜索 literal \\u200b。三项实现均被真实结果证明有效，差异不涉及 generated/"
            "oracle skill 的功能质量；strict 分只衡量是否复刻 reference 的局部命名与文件布局。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "process_pipeline.py",
            "amount_cleaner.py",
            "totals_validator.py",
            "schema_inspector.py",
            "output.json",
        ],
    },
    "E3-LS2-T6": {
        "title": "三次实现的 767 行语义与顺序全对，只因题面允许的 count 字段被 dict 全等拒绝",
        "kind": "隐藏 record shape 合同（强任务缺陷）",
        "interpretation": (
            "Qwen self-generated、Fable self-generated 与 Fable exact-oracle 都只失败同一个名为"
            "date_sort_correct 的 outcome check，且 natural product order、semantic dedup、aggregate totals"
            "和全部 process checks 均通过。独立复算把 Fable self 的每条 record 投影到 verifier 期待的"
            "product_id/date/total_amount 后，767/767 行逐项完全相等；唯一差异是模型按 Required Output"
            "Schema 中“and the aggregate/count fields produced by the transaction pipeline”加入了"
            "transaction_count，Fable self 还加入 total_quantity。Hidden check 却用 records == expected"
            "做完整 dict 全等，而 expected 只保留三个字段，再用误导性的 composite ordering mismatch"
            "报错。官方 reference 通过删掉 count 字段规避。这里三种 skill 路径的共同 outcome failure"
            "不是日期排序能力不足，而是题面允许/暗示扩展字段与未声明 exact-shape verifier 冲突。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "process_transaction_log.py",
            "date_normalizer.py",
            "product_ordering.py",
            "dedup_policy.py",
            "output.json",
        ],
    },
    "E3-LS3-T6": {
        "title": "Self 的 segment totals 只差未声明数组顺序；Exact 则长分析后完全未修改",
        "kind": "隐藏数组顺序合同 + 独立的模型执行停滞（强任务缺陷）",
        "interpretation": (
            "Fable self-generated 已通过 records_match_ground_truth、coverage、no_fanout 和全部 process"
            "checks，唯一失败是 category_totals_correct。独立复算显示三个 segment 的数值逐项一致；self"
            "按题面列举/业务顺序 enterprise→mid_market→growth 输出，verifier 用 sort_values('segment')"
            "生成 enterprise→growth→mid_market 后直接比较 list，题面没有声明数组顺序。这个 0.9375"
            "是纯序列形状假阴性。Fable exact-oracle 则是另一种原因：它实际读取两个指定 curated skills，"
            "消耗 54,551 input / 17,351 output tokens，执行 12 次 read 和 2 次只读 bash，却没有任何"
            "edit/write，保留 starter 后大量失败；轨迹显示它被额外 alias 与 coverage 定义的歧义拖入"
            "反复分析。Exact failure 因而主要是模型执行停滞，不能反证 oracle 内容；同时也不能用 exact"
            "停滞来掩盖 self 路径中已证实的 hidden order contract。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "company_normalizer.py",
            "dedup_policy.py",
            "process_customer_totals.py",
            "output.json",
        ],
    },
    "E3-LS4-T6": {
        "title": "四条运行路径核心 null 语义一致，outcome 成败只由 audit 字段放置决定",
        "kind": "隐藏输出形状合同（强任务缺陷）",
        "interpretation": (
            "Qwen/Fable 的 self-generated 与 exact-oracle 都正确实现 supplier/column-aware null policy："
            "A/B 的 0 保留，C 的 price=0 判缺失但 stock=0 保留，-1/-999 按字典归一化；顶层汇总和"
            "category totals 一致。四条路径 outcome 恰好交叉：Fable self 与 Qwen exact 通过，Fable exact"
            "与 Qwen self 失败。差异不是数值或 null 规则，而是后两者把 valid counts、out-of-stock 或"
            "normalized_by_marker 等题面要求的 audit 明细加入每个 source 的 source_null_summary；前两者"
            "把同类信息放在独立 null_standardization_audit。Hidden test 对 source_null_summary 做整个 dict"
            "全等，任何额外 audit key 都触发 mismatch，题面/schema 却没有禁止扩展。故 Qwen exact 的"
            "outcome rescue 与 Fable exact 的 harm 都只是输出布局偶然性，不是 oracle skill 的功能增益/伤害；"
            "process 侧还存在 null_policy.py 字符串切片误判。该题可测试 null 语义，但当前 verifier 不能"
            "把合法 audit 扩展与错误结果区分开。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "null_policy.py",
            "merge_inventory.py",
            "quality_summary.py",
            "merge_supplier_inventory.py",
        ],
        "task_source_files": [
            "environment/data_dictionary.md",
            "environment/quality_summary.py",
        ],
    },
    "E3-LS5-T5": {
        "title": "两模型用 Oracle 都修对 malformed amount 得到 700，却被错误 ground truth 强制为 706",
        "kind": "数据生成意图与 verifier ground truth 冲突（强任务缺陷）",
        "interpretation": (
            "任务生成器在 line 76–79 把字符串 1,2,3 明确列入 bad_amount()，并在 line 222–223 明确"
            "抽取 700 个 active、300 个 inactive logical customers。Qwen 与 Fable exact-oracle 都读到该证据后，"
            "把 parse_amount 改为只接受合法千分位分组；运行得到 logical=1000、active=700、inactive=300，"
            "并独立重算 active set 完全一致。Self-generated 沿用 starter 的 replace(',', '')，会把 malformed"
            "1,2,3 解析成 123，因而把 6 个本应 inactive 的客户误判 active。Hidden verifier 复制了同一宽松"
            "parser，并硬断言 expected active == 706；官方 reference 也只修 activity_guard、不修 parser，"
            "所以错误实现反而通过。对固定 store.db 的独立复算结果是：宽松 parser=706，严格 parser=700；"
            "共有 38 条 malformed rows，最终额外激活 6 个 inactive customers。这里 exact-oracle 的 outcome"
            "harm 是 benchmark ground truth 与 generator 语义冲突，不是模型能力下降，也不是 curated skill"
            "质量不足；这是“oracle 仍失败”必须逐题查资产、不能直接归因为题难的最强案例之一。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "customer_identity.py",
            "order_validity.py",
            "activity_guard.py",
            "count_active_customers.py",
        ],
        "task_source_files": [
            "environment/generate_data.py",
            "environment/order_validity.py",
            "environment/README.md",
        ],
    },
    "E3-LS5-T6": {
        "title": "完整 quality report 功能全过，process 仍要求固定变量名、tuple 方向与内联常量",
        "kind": "高密度固定字符串 process 假阴性",
        "interpretation": (
            "Fable self-generated 与 exact-oracle 都通过全部 outcome tests：row counts、五类 issues、"
            "cent-level cross-query reconciliation、invalid office status、low confidence 与 corrected"
            "revenue 均正确。Self 仍失败两项：它用 groups[(month, region)] 而非 verifier 硬编码的"
            "grouped[(str(row['month']), str(row['region']))]，并把 0.01 放进 CENT_TOLERANCE 常量；两者"
            "语义等价。Exact 用 by_region_month[(region, month)] 分组，tuple 方向不影响 grouping，却不"
            "匹配固定字符串；它确实生成 duplicate_region_month_batches issue，只因局部变量没有命名为"
            "duplicate_batches 又失败一项。两份输出的 outcome 完整通过已经反证这些 token 对功能的必要"
            "性。该题可以测 layered sanity 的功能，但 strict/process 分主要测 reference-style 源码复刻，"
            "不应进入 skill evolve 功能结论。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "revenue_anomaly.py",
            "consistency_guard.py",
            "office_registry.py",
            "confidence_policy.py",
            "build_operations_quality_report.py",
            "output.json",
        ],
    },
    "E4-LS1-T5": {
        "title": "模型完全做对冲突抽取，却因输出路径隐藏契约被判全部 outcome 失败",
        "kind": "题面与 verifier 路径契约冲突（强任务缺陷）",
        "interpretation": (
            "Qwen 产出的 JSON 含两笔正确 revenue、source、conflict_detected 和禁止单一 corrected value 的 summary，"
            "三项 process checks 也全部通过。失败原因是模型按题面把 output.json 写到 /root/task；Harbor 验证时"
            "artifact 被放进 workspace/task/project，而 verifier 实际要求 workspace/task/output.json，即 project 的父目录。"
            "starter 的 run_analysis.sh 恰好用 ../output.json 满足这个隐藏布局，generated structured-extraction skill"
            "反而明确建议改为脚本同目录。这里 reward=0.5 是路径合同错位造成的假阴性，也是清晰的 skill 负迁移案例。"
        ),
        "files": [
            "run_analysis.sh",
            "analyzer.py",
            "conflict_policy.py",
            "revenue_sources.py",
            "output.json",
        ],
    },
    "E4-LS3-T5": {
        "title": "模型使用题面明确允许的 MISSING，却被 verifier 的另一套 marker 白名单拒绝",
        "kind": "题面与 verifier 的缺失值集合冲突（强任务缺陷）",
        "interpretation": (
            "题面明确写出缺失字段可用 UNKNOWN、MISSING、空字符串或 null。Qwen 保留通用 label"
            "解析器，把 emergency_contact、blood_type、allergies 统一写成 MISSING；五个 present fields"
            "全部正确，process 三项全过，new patient 泛化也只因同一 marker 被拒绝。隐藏 outcome"
            "verifier 的 MISSING_MARKERS 却只有 N/A、字符串 null 和 TODO，并用 str(value) 比较："
            "这不仅拒绝题面示例 UNKNOWN、MISSING、空字符串，连真正 JSON null 读成 Python None 后"
            "也不等于字符串 null。官方 reference 只是把常量换成 N/A 来迎合隐藏白名单。该题仍能测试"
            "不幻觉与字段抽取，但当前 outcome 失败主要是合同自相矛盾，不能算 generated skill 未学会"
            "missing-value policy。"
        ),
        "files": [
            "fill_patient_form.py",
            "missing_policy.py",
            "intake_extractor.py",
        ],
    },
    "E4-LS4-T6": {
        "title": "两模型都完整报告五项首轮变化，却因 verifier 自造的两种表面写法被判失败",
        "kind": "隐藏字面量与任务原始文档表面冲突（强任务缺陷）",
        "interpretation": (
            "Qwen self-generated 与 Fable exact-oracle 都修复了按位置比较的问题，生成的报告包含"
            "v1→v2、v2→v3、Rollbacks、Net v1→v3 四段，首轮明确列出 Eligibility、Work Hours、"
            "Equipment、Security、Co-Working 五项变化，并正确排除 rolled-back Eligibility 与"
            "quarterly security briefing。唯一 outcome failure 的 hidden test 不解析结构或变化数，"
            "而是从五个固定 token 中要求命中四个；其中 `10 am - 4 pm` 与原始 policy_v2 的"
            "`10 AM – 4 PM` 标点不同，`$150/month` 又与原文 `$150 per month` 不同。两份报告忠实"
            "复用原文，因而只得 3/5 literal hits；把这两个 source-faithful variant 归一后是 5/5。"
            "这是确定的 verifier 假阴性，不是模型不会三版本 diff，也不是 oracle skill 不足。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "analyze_policy_history.py",
            "version_diff.py",
            "rollback_detector.py",
            "output/policy_history_report.md",
        ],
        "task_source_files": [
            "environment/policy_v1.md",
            "environment/policy_v2.md",
            "environment/policy_v3.md",
        ],
    },
    "E5-LS2-T6": {
        "title": "两模型完整使用 10/2 evidence split，却被 startswith 与循环变量名的固定 token 拒绝",
        "kind": "强假阴性证据",
        "interpretation": (
            "Qwen 与 Fable 的 outcome tests 全部通过：12 个 manifest source 各出现一次，10 个 vendor、"
            "2 个 independent 标签全对，decision basis 明确写入两类数量、ID、独立 review 的 usability/"
            "tradeoff 权重，并由加载后的 evidence 动态生成。Qwen 唯一两项 process failure 中，第一项是"
            "label_audit 用 source_type.startswith('vendor') 正确覆盖 vendor_doc/vendor_community，却因源码"
            "没有这两个字面量被判 blind；第二项是它先用 list comprehension 生成 labels，再遍历 vendor_ids/"
            "independent_ids 汇总 dimensions，verifier 却只接受 counter/defaultdict 或连续字面"
            "`for source in sources`。Fable 的 board_pipeline 明确 `for s in sources`、按 label split、计算"
            "independent usability score 并得出 winner，也只因变量不叫 source 而失败同一检查。真实 output"
            "已经直接证明数据依赖和 provenance split；这些 process failures 只测 reference 源码表面。"
        ),
        "files": [
            "label_audit.py",
            "board_pipeline.py",
            "output/board_report.json",
        ],
    },
    "E5-LS3-T5": {
        "title": "同一缺失 source id 被隐藏答案同时标成 fake 与 invalid，公开资产无法决定标签",
        "kind": "欠规定的标签边界与真实模型分类 gap 混合（强任务缺陷）",
        "interpretation": (
            "R09 与 R13 使用完全相同的 MED_NATURE_TABLE3_DEPLOYMENT，且该 id 同样不存在于"
            "source_manifest、evidence_index、source_cards 和 references.bib；hidden ground truth 却把"
            "R09 标 fake、R13 标 invalid。R08/R10 也只呈现为 registry miss，却要求 fake。题面要求"
            "区分 invalid 与 fabricated，但没有定义两者边界或提供外部真实性结果；唯一可区分信号是"
            "citation_packet 的 article_claim 自己写了 Fake/Invalid/Selective/Misrepresented 等标签词，"
            "这会把任务退化成复制泄漏标签。Qwen 与 Fable 把 registry miss 一致标 invalid 是可辩护的"
            "证据驱动策略，不能把 fake/invalid 错位全算成 skill 不足；但两模型也确有真实 gap，例如都"
            "没有稳定区分 selective 与 misrepresented，Fable 基本保留 starter。因此这是题目欠规定"
            "和模型执行不足的混合失败，oracle 是否 rescue 也必须在这个测量缺陷下解释。"
        ),
        "files": [
            "citation_policy.py",
            "audit_pipeline.py",
            "output/citation_audit.json",
        ],
        "task_source_files": [
            "environment/citation_packet.json",
            "environment/source_manifest.json",
            "environment/evidence_index.json",
            "environment/references.bib",
            "tests/ground_truth.json",
        ],
    },
    "E5-LS3-T6": {
        "title": "Qwen 完成 14/15 标签和全部审计维度，却被合理 scope 判断与固定理由词表误判",
        "kind": "Qwen 的语义正确实现被隐藏标签/措辞与源码 token 放大（强任务缺陷）",
        "interpretation": (
            "Qwen 对 15 条 citation 的 14 条标签与 hidden answer 完全一致，唯一分歧 S02 是"
            "`AI can detect diabetic retinopathy from retinal images`：该 claim 已保留 source card 所说"
            "的 image-based scope，没有声称普适诊断，判 valid 至少与题面定义同样合理；hidden answer"
            "仍强制 selective。M02 已正确判 misrepresented，reason 明确写 water intake 与 AI ethics"
            "`unrelated`，但 verifier 的 reason 白名单不接受 unrelated/topic mismatch，只接受"
            "misrepresented/not/self-reported/significant/attribution。Process 又要求 citation_policy.py"
            "同时出现 authenticity 与 doi/journal 字面量；Qwen 实际用 manifest 的 authentic=false 和"
            "source_type=fake_citation 做更直接的真实性判断，却因没有 doi/journal token 失败。故 Qwen"
            "的 raw outcome/process failure 是 verifier 假阴性；Fable 同题几乎未改 starter、把大多数"
            "问题都判 valid，仍是明确的真实执行失败，必须按模型分开归因。"
        ),
        "files": [
            "citation_policy.py",
            "audit_pipeline.py",
            "output/citation_audit.json",
        ],
        "task_source_files": [
            "environment/citation_packet.json",
            "environment/source_manifest.json",
            "environment/evidence_index.json",
            "tests/ground_truth.json",
        ],
    },
    "E5-LS4-T6": {
        "title": "两模型都完成层级摘要；一个被数组顺序卡住，一个被 validation/skin 词形卡住",
        "kind": "隐藏位置合同与无词形归一的概念检查（强任务缺陷）",
        "interpretation": (
            "Qwen 与 Fable 都生成了 5 个 article summaries、2 个 group summaries 和 1 个 overall，"
            "所有 must_select、word limits、forbidden terms 与主题内容均满足。Qwen 将 application group"
            "排在 method 前并显式写 group_id；verifier 不读取 group_id，却硬要求数组第 0 项含 method、"
            "第 1 项含 application。题面和 schema 都没有规定 group 数组顺序，所以这是位置敏感假阴性。"
            "Fable 顺序正确，raw test 在第一个缺词 `validation` 就停止；独立复算还发现裸词 `skin`"
            "也未出现。但全文分别保留了 `validated diagnostic tasks`、`visual dermatology`，对应的"
            "selected_sections 又含 `a1_method_validation` 与 `a5_application_skin`。verifier 只在 summary"
            "text 做裸 substring，不做词形/领域同义归一，也不看 section id。两者在任务语义上均已完成；当前 0.9091 不能解释为 skill evolve"
            "失败，也不能说明 oracle skill 仍不足。"
        ),
        "files": [
            "summarizer.py",
            "priority_policy.py",
            "audience_policy.py",
            "output/summary.json",
        ],
        "task_source_files": [
            "environment/dossier.json",
            "environment/schemas/output_schema.json",
            "tests/ground_truth.json",
        ],
    },
    "E5-LS5-T6": {
        "title": "矛盾集合完全正确，但类型、provenance 形态与 grounding 调用仍不完整",
        "kind": "高语义完成度 + 实质与形态混合 gap",
        "interpretation": (
            "Qwen 找到了 ground truth 的 9/9 真矛盾和 3/3 非矛盾，证据 quote 也完整；失败并非不会做审计。"
            "实质缺口是三个 internal pair 仍标 numeric/date，而题面明确要求 internal 类型；pipeline 也没有读取"
            "evidence_index.json。另一方面，它已经保存 source cards 与 URLs，hidden outcome 却额外要求未写进"
            "output schema 的 source_cards_chars 数字字段，部分 reasoning 失败也来自固定关键词白名单。"
            "因此 strict failure 同时包含真实 contract 漏项和 verifier 形态放大，不能等同于整题功能失败。"
        ),
        "files": [
            "audit_pipeline.py",
            "contradiction_policy.py",
            "scope_normalizer.py",
        ],
    },
    "E6-LS1-T6": {
        "title": "Fable 已正确分级和起草，却被未公开时间、关键词与 response-list 范围判失败",
        "kind": "隐藏回复合同；Qwen 另有真实优先级 gap（强任务缺陷）",
        "interpretation": (
            "Fable 的 20 封邮件优先级、P0 集合和三份 P0 draft 全部正确；checkout draft 引用"
            "inc-7421/queue，指定 action owner，并给出 `initial status update within 30 minutes` 和后续"
            "两小时 mitigation ETA。Hidden ground truth 却要求字面 `10:30`，而该时间没有出现在"
            "instruction、09:00 邮件、thread_context 或 calendar；reason 还必须含任意词 `Immediate`，"
            "尽管 Fable 已写 active production incident/genuine current crisis。最后，Fable 把两封正文"
            "明确说 `Please review today`、`Need your view today` 的 P1 邮件列为 need response，但没有"
            "为它们起草 P0 immediate reply；这符合题面 `only messages that truly need responses` 与"
            "`For P0 items only, draft immediate replies` 的自然组合，verifier 却把 response_list 偷换成"
            "exact P0 set。故 Fable 的 raw failure 是完整合同假阴性。Qwen 还把 checkout 降为 P1 并漏掉"
            "对应 draft，属于题目缺陷与真实模型 gap 混合，不能共享 Fable 的归因。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "priority_rules.py",
            "reply_drafter.py",
            "triage_pipeline.py",
            "output/triage.json",
        ],
        "task_source_files": [
            "tests/ground_truth.json",
            "environment/mail/messages.json",
            "environment/mail/thread_context.md",
            "environment/calendar/today.json",
        ],
    },
    "E6-LS2-T6": {
        "title": "两模型的路由、CC 与回复语义都正确，却因两个未公开固定短语被判 outcome 失败",
        "kind": "隐藏措辞白名单与源码 marker 造成的语义假阴性（强任务缺陷）",
        "interpretation": (
            "Qwen 与 Fable 都精确选出 4 个 reply、3 个 acknowledge、8 个 ignore，并保持要求的 CC；"
            "combo_03 都明确写 `cannot commit` full engine、给出 MVP 和 six-week 方案，符合题面"
            "`avoid making unsupported commitments`，但 hidden ground truth 只接受 `not promise` 或"
            "`would not promise`。combo_02 的 rationale 分别写明 `context/thread_notes.md in "
            "thread_history` 和 `thread history (thread_notes / thread_history)`，却因没有连续字面短语"
            "`thread context` 被判失败。独立复算把语义等价表面纳入后，两模型 required groups 从"
            "官方 2/3 变 3/3，context rationale 也通过；其余 outcome 合同本来就全部通过。Process"
            "另因 policy 源码没出现 `triage` 固定 token 失败，但正确的 4/3/8 路由已经直接证明执行了"
            "triage。这是功能性假阴性，不应作为 E6 组合能力或 skill evolve 失败。"
        ),
        "conditions": ["self_generated", "exact_oracle"],
        "files": [
            "reply_policy.py",
            "context_loader.py",
            "output/replies.json",
        ],
        "task_source_files": [
            "tests/ground_truth.json",
            "environment/context/project_state.json",
            "environment/context/thread_notes.md",
        ],
    },
    "E6-LS3-T6": {
        "title": "两模型都抽出 8/8 actions，却被未公开的 action ID 名称判成大量缺失",
        "kind": "隐藏 semantic-ID 合同与部分真实 status/follow-up gap（强任务缺陷）",
        "interpretation": (
            "Qwen 与 Fable 都从 ft01–ft08 正确抽出全部 8 个真实 action，source_message_id、"
            "assignee、deadline 和大多数 status 也与 ground truth 对齐。Qwen 的核心字段命中"
            "23/24，Fable 命中 22/24；两者都把 ft01 命名为 act_webhook_runbook，而 verifier"
            "只接受未在题面公开的 act_runbook，于是 test_expected_actions_detected 和"
            "test_assignees_deadlines_and_descriptions 报 missing。ft06 同样被合理命名为"
            "act_docs_update/act_update_docs，而隐藏答案只认 act_docs，连 implicit=true 也因按"
            "隐藏 ID lookup 被忽略。题面只要求 stable action id，没有规定命名词表；verifier"
            "应以 source_message_id 或语义字段对齐。模型仍有真实缺口：docs/migration 的"
            "open/no_update 区分不全对，并生成了非 overdue follow-up。故本题不是完全假阴性，"
            "但当前 2/7 outcome pass 严重低估实际 extraction 能力，不能直接用于判断 skill"
            "evolution 失败。"
        ),
        "files": [
            "action_tracker.py",
            "extractor_policy.py",
            "followup_drafter.py",
            "output/actions.json",
        ],
        "task_source_files": [
            "tests/ground_truth.json",
            "environment/slack/channel_export.json",
        ],
    },
    "E6-LS4-T6": {
        "title": "题目没有唯一最优日程，verifier 却要求任意固定时间与数组顺序",
        "kind": "欠规定的唯一解与不可满足硬约束（强任务缺陷）",
        "interpretation": (
            "两模型都生成了 DST-aware、多日分散、带偏好解释的三会议方案；Fable 的三项 score 和 soft count"
            "甚至全部匹配 ground truth。verifier 仍要求 meetings 必须保持 team_sync/client_demo/one_on_one 的数组顺序，"
            "并必须包含 2026-04-28 15:00、04-29 14:00、04-30 19:00 三个固定 start。题面没有给这些"
            "tie-break，官方 solution 只是按 meeting id 硬编码时间。更严重的是纽约、洛杉矶、柏林和伦敦的"
            "09:00–17:00 工作时段没有四人共同正长度交集，官方时间也违反“每位 attendee 的 hard constraints”。"
            "因此该题当前不能可靠区分 skill quality；即使 oracle skill 合理，模型也可能因选择另一个等价/更合理解而失败。"
        ),
        "files": ["scheduling_policy.py", "output/schedule.json"],
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
    "business-impact prioritization": (
        r"business impact|emotional tone|all-caps|operational risk|"
        r"priority counts?|p0 items?"
    ),
    "semantic schema resolution": (
        r"column naming convention|found by meaning|casefold|case-sensitive|"
        r"header normalization|schema handling"
    ),
    "cent-level precision": r"precision|cent[- ]level|decimal",
    "integration regression coverage": (
        r"integration[- ]style|regression coverage|coverage threshold|"
        r"line coverage|coverage-driven"
    ),
    "dependency API migration": (
        r"alembic|sqlalchemy|deprecated alias|dependency (?:update|upgrade)|"
        r"api migration|compatibility issues?"
    ),
    "multi-sheet formula preservation": (
        r"multi-sheet|formula-driven|all sheets|formula values?|"
        r"computed values not formulas"
    ),
    "ordered normalization pipeline": (
        r"extract.*normalize.*fill.*validat|pipeline order|four-step pipeline|"
        r"normalize.*enrich|enrich.*normalize"
    ),
    "citation authenticity and support": (
        r"fabricated citations?|citation audit|authenticity|claim support|"
        r"misrepresented|selective citation"
    ),
    "semantic null distinctions": (
        r"fillna.*zero|zero.*offline|none.*empty|empty.*none|"
        r"boundary semantics|missing.*zero|missing temperature.*offline|"
        r"actual zero-degree|exclude null/offline|fillna\(0\)"
    ),
    "error propagation and HTTP semantics": (
        r"error state|successful api responses?|db error returns 500|"
        r"silent empty|blank profile|distinguishes 404 and 500|"
        r"operational error"
    ),
    "hierarchical summarization": (
        r"per-article summaries?|group summaries?|overall synthesis|"
        r"hierarchical(?:ly)?"
    ),
    "priority-based summarization": (
        r"highest-value findings?|high-value evidence|"
        r"prioriti[sz](?:e|ing).*findings?|priority selection|"
        r"document order|word limits?"
    ),
    "multi-dimensional recency ranking": (
        r"evidence quality.*recency|recency.*evidence quality|"
        r"outdated.*source|stale authority|three dimensions"
    ),
    "natural numeric ordering": (
        r"sorted naturally|zero-padded|numeric position|lexicographic|"
        r"numeric string"
    ),
    "response schema migration": (
        r"deprecated.*current fields?|current.*deprecated fields?|"
        r"canonical fields?|field migration"
    ),
    "per-record fallback validation": (
        r"primary record is invalid|primary records? before|"
        r"backup data only|fallback only for|per-record backup"
    ),
    "document reference validation": (
        r"page reference|referenced section|current-year|wrong page pointer|"
        r"source page"
    ),
    "local pre-call validation": (
        r"rejected locally|before they hit the backend|zero remote 400|"
        r"local validation|before any api call"
    ),
    "dynamic pagination termination": (
        r"metadata changes mid-run|has_more|rechecks metadata|"
        r"grow while pagination|growing while pagination|"
        r"precomputes a page plan"
    ),
    "configured endpoint resolution": (
        r"configuration endpoint|current data url|legacy url|"
        r"migration-era legacy|uses current endpoint"
    ),
    "systemic root-cause repair": (
        r"actual root cause|real fix|one-off special case|"
        r"hardcoded regions?|all states correct"
    ),
    "join-key correctness": (
        r"join key|user_id join|merge path|transactions attach|"
        r"correct user records"
    ),
}

ENVIRONMENT_PROFILES = {
    "E1": {
        "name": "软件调试、依赖与多文件修复",
        "capability": "从症状定位根因，并在依赖升级、重构和跨层修改中保持行为与测试一致。",
        "provisional_read": (
            "两模型在 10 个 T5/T6 上得到完全相同的 outcome 8/10、strict 5/10，连失败题也一致。"
            "其中 3 题功能已通过、只是指定文件/API/覆盖率形态未满足；两项共同 outcome 失败中，数据库"
            "会话迁移是真实组合执行 gap，而跨文件错误传播题的两种实现其实都完成了 500/404/UI 修复，"
            "只因隐藏 monkeypatch seam 与源码字面量扫描失败。因此 E1 当前主要是 verifier/测试形态敏感，"
            "外加一个真实数据库会话缺口，不支持 T5/T6 普遍不可解，也不像某一个模型的偶然退化。"
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
            "T5 只有同一个 wrong-join-key trap 被两模型共同做错，但逐代码看二者其实都选对了 join key；"
            "真正问题是额外改写 schema cleaner、按 user id 去重，破坏了 starter/reference 保留的重复 master rows。"
            "两模型的 self/exact 已形成 20 个匹配对：raw oracle outcome rescue=1、harm=3，但全部 discordant"
            "都来自已核实的 benchmark 缺陷。Qwen 在 null unification 上的 rescue 只是把 audit 明细移出"
            "hidden dict 全等字段；Qwen/Fable 在 active-customer trap 上的 harm 则是正确拒绝 malformed `1,2,3`"
            "后得到 generator 声明的 700，而 hidden parser 错认 706。对复合排序、wrong-join 与模糊合并这些"
            "真实功能失败，exact oracle 没有救回。E3 因而既暴露过度修复与组合不变量 gap，也证明 raw"
            "self↔oracle 翻转可能完全由 verifier/ground truth 造成，不能仅按分数解释为 skill 效应。"
        ),
    },
    "E4": {
        "name": "文档抽取、格式迁移与版本比较",
        "capability": "结构化抽取、跨格式保真、上下文填表、多版本 diff 与冲突保留。",
        "provisional_read": (
            "Qwen self 的 T5/T6 raw outcome 都是 3/5；新完成的 Fable exact-oracle 则是 T5 3/5、T6 4/5。"
            "两项 T5 raw 失败和两模型共同的 E4-LS4-T6 raw 失败都是明确 benchmark 合同问题。"
            "E4-LS1-T5 不是文档语义失败："
            "模型已正确输出两笔 revenue、source 与 conflict，三项 process 也全过，只因题面要求的输出路径"
            "与 verifier 实际父目录合同冲突而被判 0/5 outcome；E4-LS3-T5 则使用题面明确允许的 MISSING，"
            "隐藏 verifier 却只接受 N/A、字符串 null 或 TODO，甚至拒绝真正 JSON null；E4-LS4-T6 两模型"
            "都列全五项首轮变化，却因 hidden token 的标点/单位写法与原始文档不一致而失败。剔除这三项"
            "假阴性后，Fable exact 的 T5/T6 核心语义为 10/10；Qwen self 为 9/10，剩余 PDF→DOCX"
            "数值表面保真是真实 gap。Fable self repair 与另外两 control 到齐前，尚不能把跨模型差异当 oracle 因果效应。"
        ),
    },
    "E5": {
        "name": "研究检索、证据归因与综合",
        "capability": "多源筛选、证据化比较、引用核验、受约束总结与矛盾审计。",
        "provisional_read": (
            "Qwen 的 T5/T6 outcome 为 3/5、1/5，Fable 为 3/5、3/5；两模型仍共同做错 4/10 个对齐任务。"
            "失败集中在没有读取 grounding files、provenance 合同、引用问题标签和 pipeline 执行，但逐题审计"
            "发现 raw 分数又混入明显测量缺陷：citation T5 让同一缺失 source id 同时对应 fake/invalid；"
            "citation T6 中 Qwen 已做对 14/15 标签，唯一 S02 已保留 retinal-image scope，却被强制 selective，"
            "正确的 `unrelated` 理由和 manifest authenticity 判断又因固定 token 被拒；hierarchical summary"
            "两模型都完成 5/2/1 结构、must-select 与主题语义，分别只撞上 group 数组顺序和"
            "validation/validated、skin/dermatology 的裸 substring。"
            "但 E5-LS5-T6 中 Qwen 已找全 9/9 真矛盾与 3/3 非矛盾，strict 失败主要是 internal 类型、"
            "evidence_index 调用和未公开的 source_cards_chars 形态；不能把它算成完全不会审计。"
            "Fable 在复合检索总结上较强，但差距是否来自 skill 仍需同模型四条件对照。"
        ),
    },
    "E6": {
        "name": "邮件、会议与行动项工作流",
        "capability": "优先级判断、上下文回复、行动项抽取、时区排期以及 thread 级综合。",
        "provisional_read": (
            "两模型 T6 outcome 都是 0/5，且失败横跨优先级、必含内容、隐式行动、DST 排期和状态汇总。"
            "generated skills 往往已经写到这些概念，但执行产物仍不符合契约。逐代码后，至少四题的 raw"
            "0/5 被 benchmark 明显放大：E6-LS1-T6 中 Fable 的 P0 与 draft 全对，却撞上未公开 10:30、"
            "Immediate 和 response-list=P0 合同；Qwen 同题仍有真实 priority gap。E6-LS2-T6 中两模型的 4 reply/3 acknowledge/8 ignore、CC 与"
            "回复语义都正确，只因 `cannot commit`/thread history 没匹配 `not promise`/`thread context`"
            "固定短语而失败；E6-LS3-T6 中两模型都抽出 8/8 actions，核心字段分别命中"
            "23/24 与 22/24，却因题面未公开的 action ID 名称被报大量 missing；E6-LS4-T6 则是"
            "欠规定题，四人工作时段无共同正长度交集，verifier 仍要求未声明的固定日期、时间和数组顺序。"
            "其余优先级、回复内容与 thread parsing 仍有真实执行 gap。因此 E6 的 0/5 既不是纯模型失败，"
            "也不是纯坏题；需在 exact/no-skill 到齐后按题剔除合同缺陷再估计 skill 效应。"
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


def trajectory_tool_activity(path: Path) -> dict[str, Any]:
    """Extract compact tool and mutation evidence from one trajectory.

    Some AP exports preserve the trajectory and verifier reports but not the
    final task tree. Tool calls still show whether the model inspected, tested,
    or actually mutated the workspace.
    """

    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {
            "tool_counts": {},
            "bash_commands": [],
            "mutation_call_count": 0,
            "final_edits": [],
        }

    tool_counts: Counter[str] = Counter()
    bash_commands: list[str] = []
    mutation_call_count = 0
    edits: list[dict[str, str]] = []

    def visit(node: Any) -> None:
        nonlocal mutation_call_count
        if isinstance(node, dict):
            function_name = node.get("function_name")
            arguments = node.get("arguments")
            if isinstance(function_name, str):
                tool_counts[function_name] += 1
                if function_name in {"edit", "write", "apply_patch"}:
                    mutation_call_count += 1
                if function_name == "bash" and isinstance(arguments, dict):
                    command = arguments.get("command")
                    if isinstance(command, str):
                        bash_commands.append(command)
            if function_name == "edit" and isinstance(arguments, dict):
                file_path = arguments.get("filePath")
                old = arguments.get("oldString")
                new = arguments.get("newString")
                if all(isinstance(item, str) for item in (file_path, old, new)):
                    edits.append(
                        {
                            "file_path": file_path,
                            "old": old,
                            "new": new,
                        }
                    )
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return {
        "tool_counts": dict(sorted(tool_counts.items())),
        "bash_commands": bash_commands,
        "mutation_call_count": mutation_call_count,
        "final_edits": edits,
    }


def trajectory_final_edits(path: Path) -> list[dict[str, str]]:
    """Backward-compatible helper used by focused tests."""

    return trajectory_tool_activity(path)["final_edits"]


def reproduce_e3_ls5_active_counts(task_root: Path) -> dict[str, Any]:
    """Recompute the malformed-amount ground-truth conflict independently."""

    database = task_root / "environment" / "store.db"
    generator = task_root / "environment" / "generate_data.py"
    generator_text = generator.read_text(encoding="utf-8", errors="replace")

    zero_width = ("\u200b", "\u200c", "\u200d", "\ufeff")

    def normalize_email(value: object) -> str | None:
        if value is None:
            return None
        text = str(value)
        for character in zero_width:
            text = text.replace(character, "")
        text = text.strip().lower()
        return None if text in {"", "null", "none", "na"} else text

    def valid_status(value: object) -> bool:
        return str(value).strip().lower() in {"paid", "shipped"}

    def valid_date(value: object) -> bool:
        if value is None:
            return False
        for format_string in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                datetime.strptime(str(value).strip(), format_string)
                return True
            except ValueError:
                pass
        return False

    strict_pattern = re.compile(
        r"^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$"
    )

    def amount(value: object, *, strict: bool) -> Decimal | None:
        if value is None:
            return None
        text = str(value).strip().replace("$", "").strip()
        if not text or (strict and strict_pattern.fullmatch(text) is None):
            return None
        try:
            parsed = Decimal(text.replace(",", ""))
        except InvalidOperation:
            return None
        return parsed if parsed > 0 else None

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        customers = connection.execute(
            "SELECT id, email FROM customers ORDER BY id"
        ).fetchall()
        orders = connection.execute(
            "SELECT customer_id, amount, order_date, status FROM orders ORDER BY id"
        ).fetchall()
    finally:
        connection.close()

    by_email: dict[str, int] = {}
    canonical: dict[int, int] = {}
    for row in customers:
        customer_id = int(row["id"])
        email = normalize_email(row["email"])
        if email is None:
            canonical[customer_id] = customer_id
        else:
            canonical[customer_id] = by_email.setdefault(email, customer_id)

    def active_ids(*, strict: bool) -> tuple[set[int], list[int]]:
        active: set[int] = set()
        malformed_qualified: list[int] = []
        for row in orders:
            canonical_id = canonical.get(int(row["customer_id"]))
            if canonical_id is None:
                continue
            if not valid_status(row["status"]) or not valid_date(row["order_date"]):
                continue
            if amount(row["amount"], strict=strict) is None:
                continue
            active.add(canonical_id)
            if row["amount"] == "1,2,3":
                malformed_qualified.append(canonical_id)
        return active, malformed_qualified

    loose, malformed_qualified = active_ids(strict=False)
    strict, strict_malformed = active_ids(strict=True)
    sample_match = re.search(
        r"active_indices\s*=\s*set\(random\.sample\([^\n]+,\s*(\d+)\)\)",
        generator_text,
    )
    bad_amount_body = generator_text.split("def bad_amount", 1)[-1].split(
        "def status_variant", 1
    )[0]
    return {
        "method": (
            "Read store.db directly; normalize identities; compare the starter/"
            "verifier comma-stripping parser with a valid-thousands-group parser."
        ),
        "generator_declared_active": (
            int(sample_match.group(1)) if sample_match else None
        ),
        "generator_labels_1_2_3_bad": '"1,2,3"' in bad_amount_body,
        "loose_parser_active": len(loose),
        "strict_parser_active": len(strict),
        "extra_active_from_loose_parser": len(loose - strict),
        "malformed_qualified_rows_under_loose_parser": len(malformed_qualified),
        "malformed_qualified_unique_customers": len(set(malformed_qualified)),
        "malformed_qualified_rows_under_strict_parser": len(strict_malformed),
        "database_path": str(database.resolve()),
        "generator_path": str(generator.resolve()),
    }


def reproduce_e3_ls2_record_shape(
    task_root: Path, artifact_task_root: Path
) -> dict[str, Any]:
    """Show that the alleged sort mismatch is only extra record fields."""

    import pandas as pd

    csv_path = task_root / "environment" / "transaction_log.csv"
    output_path = artifact_task_root / "output.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    observed = payload.get("records") or []

    frame = pd.read_csv(csv_path, dtype={"product_id": str})
    frame["parsed_date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["amount_clean"] = (
        frame["amount"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .astype(float)
    )
    deduplicated = frame.drop_duplicates(
        subset=[
            "date",
            "product_id",
            "customer_id",
            "amount",
            "quantity",
            "channel",
        ]
    ).copy()
    expected = (
        deduplicated.groupby(["parsed_date", "product_id"], as_index=False)[
            "amount_clean"
        ]
        .sum()
        .rename(columns={"amount_clean": "total_amount"})
    )
    expected["_product_order"] = expected["product_id"].map(
        lambda value: int(str(value).strip().removeprefix("P"))
    )
    expected = expected.sort_values(
        ["parsed_date", "_product_order"],
        ascending=[True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    expected["date"] = expected["parsed_date"].dt.strftime("%Y-%m-%d")
    expected_records = expected.drop(
        columns=["_product_order", "parsed_date"]
    ).to_dict(orient="records")
    expected_keys = ("product_id", "date", "total_amount")
    projected = [
        {key: record.get(key) for key in expected_keys} for record in observed
    ]
    observed_keys = sorted(observed[0]) if observed else []
    return {
        "method": (
            "Recompute the verifier's semantic dedup, aggregation, and composite "
            "sort; then compare both the full dictionaries and a projection onto "
            "the three verifier/reference fields."
        ),
        "observed_rows": len(observed),
        "expected_rows": len(expected_records),
        "full_record_dicts_equal": observed == expected_records,
        "projected_semantic_records_equal": projected == expected_records,
        "observed_record_keys": observed_keys,
        "verifier_expected_keys": list(expected_keys),
        "extra_record_keys": sorted(set(observed_keys) - set(expected_keys)),
        "artifact_output_path": str(output_path.resolve()),
        "fixture_path": str(csv_path.resolve()),
    }


def reproduce_e3_ls3_category_order(
    task_root: Path, artifact_task_root: Path
) -> dict[str, Any]:
    """Recompute category totals and isolate the list-order-only mismatch."""

    import pandas as pd

    environment = task_root / "environment"
    output_path = artifact_task_root / "output.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    observed = payload.get("category_totals") or []

    def canonical(value: object) -> str:
        normalized = re.sub(
            r"[^a-z0-9]+", " ", str(value).strip().lower()
        )
        normalized = re.sub(r"\s+", " ", normalized).strip()
        aliases = {
            "acme": "acme corp",
            "acme corporation": "acme corp",
            "globaltech": "global tech",
            "premier sol": "premier solutions",
        }
        return aliases.get(normalized, normalized)

    def segment(value: float) -> str:
        if value >= 3_500_000:
            return "enterprise"
        if value >= 1_500_000:
            return "mid_market"
        return "growth"

    crm = pd.read_csv(environment / "crm_contacts.csv")
    crm["canonical_company"] = crm["company_name"].map(canonical)
    crm["segment"] = crm["annual_revenue"].astype(float).map(segment)
    crm = crm.drop_duplicates(subset=["canonical_company"], keep="first")
    ratings = pd.read_csv(environment / "external_ratings.csv")
    ratings["canonical_company"] = ratings["company"].map(canonical)
    ratings = ratings.drop_duplicates(
        subset=["canonical_company"], keep="first"
    )
    erp = pd.read_csv(environment / "erp_orders.csv")
    erp["canonical_company"] = erp["company_name"].map(canonical)
    erp["order_amount"] = erp["order_amount"].astype(float)
    erp = erp.groupby("canonical_company", as_index=False)["order_amount"].sum()
    merged = crm.merge(
        ratings, on="canonical_company", how="left", validate="1:1"
    ).merge(erp, on="canonical_company", how="left", validate="1:1")
    merged["order_amount"] = merged["order_amount"].fillna(0.0)
    expected = (
        merged.groupby("segment", as_index=False)["order_amount"]
        .sum()
        .rename(columns={"order_amount": "total_order_amount"})
        .sort_values("segment", kind="mergesort")
        .reset_index(drop=True)
        .to_dict(orient="records")
    )
    observed_by_segment = {
        row["segment"]: row["total_order_amount"] for row in observed
    }
    expected_by_segment = {
        row["segment"]: row["total_order_amount"] for row in expected
    }
    return {
        "method": (
            "Recompute the official category totals; compare the ordered JSON "
            "array and the same values indexed by segment."
        ),
        "ordered_lists_equal": observed == expected,
        "values_equal_when_keyed_by_segment": (
            observed_by_segment == expected_by_segment
        ),
        "observed_segment_order": [row["segment"] for row in observed],
        "verifier_expected_segment_order": [
            row["segment"] for row in expected
        ],
        "observed_totals": observed,
        "verifier_expected_totals": expected,
        "artifact_output_path": str(output_path.resolve()),
    }


def reproduce_e6_ls3_action_identity(
    task_root: Path, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Align actions by source message instead of the verifier's hidden IDs."""

    ground_truth_path = task_root / "tests" / "ground_truth.json"
    messages_path = task_root / "environment" / "slack" / "channel_export.json"
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    messages = json.loads(messages_path.read_text(encoding="utf-8"))["messages"]

    expected_source_by_id: dict[str, str] = {}
    for action_id, spec in ground_truth.get("expected_fields", {}).items():
        terms = [str(term).lower() for term in spec.get("description_terms", [])]
        candidates = [
            str(message["id"])
            for message in messages
            if all(term in str(message.get("text") or "").lower() for term in terms)
        ]
        if candidates:
            expected_source_by_id[str(action_id)] = candidates[0]

    rows = []
    for observation in observations:
        artifact_raw = observation.get("artifact_task_path")
        if not artifact_raw:
            continue
        output_path = Path(str(artifact_raw)) / "output" / "actions.json"
        if not output_path.is_file():
            continue
        output = json.loads(output_path.read_text(encoding="utf-8"))
        actions = [
            action for action in output.get("actions", [])
            if isinstance(action, dict)
        ]
        by_source = {
            str(action.get("source_message_id")): action
            for action in actions
            if action.get("source_message_id")
        }
        field_checks = []
        id_mismatches = []
        for expected_id, source_id in expected_source_by_id.items():
            actual = by_source.get(source_id)
            if actual is None:
                continue
            if str(actual.get("id") or "") != expected_id:
                id_mismatches.append({
                    "source_message_id": source_id,
                    "verifier_expected_id": expected_id,
                    "model_id": actual.get("id"),
                })
            spec = ground_truth["expected_fields"][expected_id]
            for field in ("assignee", "deadline", "status"):
                if field in spec:
                    field_checks.append({
                        "source_message_id": source_id,
                        "field": field,
                        "expected": spec[field],
                        "actual": actual.get(field),
                        "matched": actual.get(field) == spec[field],
                    })
        rows.append({
            "model": observation.get("model"),
            "condition": observation.get("condition"),
            "expected_actions": len(expected_source_by_id),
            "source_aligned_actions_found": sum(
                source_id in by_source
                for source_id in expected_source_by_id.values()
            ),
            "exact_hidden_id_matches": sum(
                by_source.get(source_id, {}).get("id") == expected_id
                for expected_id, source_id in expected_source_by_id.items()
            ),
            "core_fields_matched": sum(
                check["matched"] for check in field_checks
            ),
            "core_fields_checked": len(field_checks),
            "id_mismatches": id_mismatches,
            "core_field_mismatches": [
                check for check in field_checks if not check["matched"]
            ],
            "artifact_output_path": str(output_path.resolve()),
        })
    return {
        "method": (
            "Derive each expected action's source message from its description "
            "terms, then align model outputs by the public source_message_id "
            "instead of the verifier-only action ID vocabulary."
        ),
        "instruction_only_requires_stable_action_id": True,
        "verifier_indexes_actions_by_exact_hidden_id": True,
        "expected_source_by_hidden_id": expected_source_by_id,
        "models": rows,
        "ground_truth_path": str(ground_truth_path.resolve()),
        "messages_path": str(messages_path.resolve()),
    }


def reproduce_e6_ls2_semantic_phrasing(
    task_root: Path, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Re-evaluate the two hidden phrase checks with semantic equivalents."""

    ground_truth_path = task_root / "tests" / "ground_truth.json"
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    semantic_refusal_terms = (
        "cannot commit",
        "can't commit",
        "unable to commit",
        "decline the commitment",
        "declined the unsupported",
    )
    semantic_thread_terms = (
        "thread context",
        "thread history",
        "thread_history",
        "thread notes",
        "thread_notes",
        "earlier round of the thread",
    )
    official_refusal_terms = tuple(
        str(term).lower()
        for term in ground_truth["required_terms"]["combo_03"][2]
    )

    rows = []
    for observation in observations:
        artifact_raw = observation.get("artifact_task_path")
        if not artifact_raw:
            continue
        task_artifact = Path(str(artifact_raw))
        output_path = task_artifact / "output" / "replies.json"
        if not output_path.is_file():
            continue
        output = json.loads(output_path.read_text(encoding="utf-8"))
        replies = {
            str(reply.get("email_id")): reply
            for reply in output.get("replies", [])
            if isinstance(reply, dict)
        }
        acknowledgements = {
            str(item.get("email_id"))
            for item in output.get("acknowledgements", [])
            if isinstance(item, dict)
        }
        ignored = {
            str(item.get("email_id"))
            for item in output.get("ignored", [])
            if isinstance(item, dict)
        }
        combo_02_rationale = str(
            replies.get("combo_02", {}).get("rationale") or ""
        ).lower()
        combo_03_body = str(
            replies.get("combo_03", {}).get("body") or ""
        ).lower()
        official_refusal_match = any(
            term in combo_03_body for term in official_refusal_terms
        )
        semantic_refusal_match = any(
            term in combo_03_body for term in semantic_refusal_terms
        )
        official_context_match = "thread context" in combo_02_rationale
        semantic_context_match = any(
            term in combo_02_rationale for term in semantic_thread_terms
        )
        expected_cc_ok = all(
            set(addresses).issubset(
                set(replies.get(message_id, {}).get("cc", []))
            )
            for message_id, addresses in ground_truth["expected_cc"].items()
        )
        forbidden_absent = all(
            str(phrase).lower()
            not in json.dumps(output, ensure_ascii=False).lower()
            for phrase in ground_truth["forbidden_phrases"]
        )
        policy_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (
                task_artifact / "reply_policy.py",
                task_artifact / "context_loader.py",
            )
            if path.is_file()
        ).lower()
        rows.append({
            "model": observation.get("model"),
            "condition": observation.get("condition"),
            "reply_ids_exact": set(replies) == set(
                ground_truth["expected_reply_ids"]
            ),
            "ack_ids_exact": acknowledgements == set(
                ground_truth["expected_ack_ids"]
            ),
            "ignore_ids_exact": ignored == set(
                ground_truth["expected_ignore_ids"]
            ),
            "expected_cc_preserved": expected_cc_ok,
            "forbidden_phrases_absent": forbidden_absent,
            "combo_03_official_refusal_phrase_match": official_refusal_match,
            "combo_03_semantic_refusal_match": semantic_refusal_match,
            "combo_03_official_required_groups": 2 + int(
                official_refusal_match
            ),
            "combo_03_semantic_required_groups": 2 + int(
                semantic_refusal_match
            ),
            "combo_02_official_thread_context_match": official_context_match,
            "combo_02_semantic_thread_evidence_match": semantic_context_match,
            "literal_triage_marker_in_policy_source": "triage" in policy_text,
            "artifact_output_path": str(output_path.resolve()),
        })

    return {
        "method": (
            "Recompute routing, CC, forbidden-content and the two failed hidden "
            "phrase checks; then accept only explicit semantic equivalents "
            "already demanded by the public instruction."
        ),
        "instruction_requires_avoiding_unsupported_commitments": True,
        "instruction_requires_context_used_rationale": True,
        "instruction_requires_exact_not_promise_wording": False,
        "instruction_requires_exact_thread_context_phrase": False,
        "official_refusal_terms": list(official_refusal_terms),
        "semantic_refusal_terms": list(semantic_refusal_terms),
        "semantic_thread_terms": list(semantic_thread_terms),
        "models": rows,
        "ground_truth_path": str(ground_truth_path.resolve()),
    }


def reproduce_e6_ls1_hidden_reply_contract(
    task_root: Path, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Separate public triage semantics from hidden exact reply strings."""

    ground_truth_path = task_root / "tests" / "ground_truth.json"
    messages_path = task_root / "environment" / "mail" / "messages.json"
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    message_payload = json.loads(messages_path.read_text(encoding="utf-8"))
    messages = {
        str(message["id"]): message
        for message in message_payload.get("messages", [])
    }
    public_text_parts = [
        (task_root / "instruction.md").read_text(
            encoding="utf-8", errors="replace"
        )
    ]
    for path in sorted((task_root / "environment").rglob("*")):
        if path.is_file():
            try:
                public_text_parts.append(
                    path.read_text(encoding="utf-8", errors="replace")
                )
            except OSError:
                pass
    public_surface = "\n".join(public_text_parts).lower()

    rows = []
    for observation in observations:
        artifact_raw = observation.get("artifact_task_path")
        if not artifact_raw:
            continue
        task_artifact = Path(str(artifact_raw))
        output_path = task_artifact / "output" / "triage.json"
        if not output_path.is_file():
            continue
        output = json.loads(output_path.read_text(encoding="utf-8"))
        items = {
            str(item.get("id")): item
            for item in output.get("items", [])
            if isinstance(item, dict)
        }
        priorities = {
            task_id: str(item.get("priority"))
            for task_id, item in items.items()
        }
        expected_priorities = {
            str(task_id): str(priority)
            for task_id, priority in ground_truth["expected_priorities"].items()
        }
        p0_ids = {
            task_id
            for task_id, priority in priorities.items()
            if priority == "P0"
        }
        response_ids = {
            str(task_id) for task_id in output.get("response_list", [])
        }
        expected_response_ids = set(ground_truth["expected_response_ids"])
        extra_response_ids = sorted(response_ids - expected_response_ids)
        explicit_request_extras = [
            task_id
            for task_id in extra_response_ids
            if re.search(
                r"\b(?:please|need your|need a|can you|could you)\b",
                str(messages.get(task_id, {}).get("body") or ""),
                re.IGNORECASE,
            )
        ]
        drafts = {
            str(draft.get("email_id")): draft
            for draft in output.get("drafts", [])
            if isinstance(draft, dict)
        }
        checkout_body = str(
            drafts.get("checkout_incident", {}).get("body") or ""
        ).lower()
        checkout_reason = str(
            items.get("checkout_incident", {}).get("reason") or ""
        ).lower()
        checkout_semantic_eta = bool(
            re.search(
                r"\b(?:eta|within\s+\d+\s+(?:minutes?|hours?)|by\s+\d{1,2}:\d{2})\b",
                checkout_body,
                re.IGNORECASE,
            )
        )
        checkout_semantic_incident_reason = any(
            phrase in checkout_reason
            for phrase in (
                "active production incident",
                "incident still active",
                "current crisis",
                "bridge",
            )
        )
        rows.append({
            "model": observation.get("model"),
            "condition": observation.get("condition"),
            "all_priorities_exact": priorities == expected_priorities,
            "p0_set_exact": p0_ids == set(ground_truth["expected_p0"]),
            "draft_ids_exact": set(drafts) == set(
                ground_truth["expected_drafts"]
            ),
            "response_list_exact_hidden_set": (
                response_ids == expected_response_ids
            ),
            "extra_response_ids": extra_response_ids,
            "extra_response_ids_with_explicit_requests": explicit_request_extras,
            "checkout_has_incident_and_queue_context": (
                "inc-7421" in checkout_body and "queue" in checkout_body
            ),
            "checkout_has_semantic_eta": checkout_semantic_eta,
            "checkout_has_hidden_10_30_literal": "10:30" in checkout_body,
            "checkout_reason_has_hidden_immediate_literal": (
                "immediate" in checkout_reason
            ),
            "checkout_reason_has_semantic_incident_evidence": (
                checkout_semantic_incident_reason
            ),
            "artifact_output_path": str(output_path.resolve()),
        })

    return {
        "method": (
            "Recompute priority/P0/draft sets, inspect whether response-list "
            "extras explicitly request an answer, and compare the hidden "
            "10:30/Immediate literals with public ETA/incident semantics."
        ),
        "hidden_10_30_appears_in_public_instruction_or_environment": (
            "10:30" in public_surface
        ),
        "public_instruction_limits_immediate_drafts_to_p0": True,
        "public_instruction_limits_response_list_to_p0": False,
        "models": rows,
        "ground_truth_path": str(ground_truth_path.resolve()),
        "messages_path": str(messages_path.resolve()),
    }


def reproduce_e4_ls3_missing_markers(
    task_root: Path, artifact_task_root: Path
) -> dict[str, Any]:
    """Compare prompt-authorized missing values with the hidden whitelist."""

    import ast

    outcome_path = task_root / "tests" / "test_outcome.py"
    outcome_tree = ast.parse(outcome_path.read_text(encoding="utf-8"))
    verifier_markers: set[Any] = set()
    for node in outcome_tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "MISSING_MARKERS"
                for target in node.targets
            )
        ):
            verifier_markers = set(ast.literal_eval(node.value))
            break

    policy_path = artifact_task_root / "missing_policy.py"
    policy_tree = ast.parse(policy_path.read_text(encoding="utf-8"))
    actual_marker: Any = None
    for node in policy_tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "DEFAULT_MISSING_MARKER"
                for target in node.targets
            )
        ):
            actual_marker = ast.literal_eval(node.value)
            break

    instruction_examples: list[Any] = ["UNKNOWN", "MISSING", "", None]
    return {
        "method": (
            "Evaluate every missing-marker example explicitly allowed by the "
            "instruction using the verifier's exact str(value) membership test."
        ),
        "instruction_examples": [
            "UNKNOWN", "MISSING", "empty string", "JSON null"
        ],
        "verifier_accepted_strings": sorted(str(value) for value in verifier_markers),
        "instruction_example_acceptance": {
            (
                "empty string" if value == ""
                else "JSON null" if value is None
                else str(value)
            ): str(value) in verifier_markers
            for value in instruction_examples
        },
        "model_marker": actual_marker,
        "model_marker_accepted": str(actual_marker) in verifier_markers,
        "verifier_uses_str_value_membership": True,
        "outcome_verifier_path": str(outcome_path.resolve()),
        "artifact_policy_path": str(policy_path.resolve()),
    }


def reproduce_e4_ls4_literal_surface(
    task_root: Path, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare hidden literal hits with source-faithful surface variants."""

    verifier_tokens = [
        "60 days",
        "10 am - 4 pm",
        "$800",
        "quarterly security briefings",
        "$150/month",
    ]
    semantic_variants = {
        "60 days": ["60 days"],
        "10 am - 4 pm": ["10 am - 4 pm", "10 am – 4 pm", "10 am — 4 pm"],
        "$800": ["$800"],
        "quarterly security briefings": ["quarterly security briefings"],
        "$150/month": ["$150/month", "$150 per month"],
    }

    rows = []
    for observation in observations:
        path_raw = observation.get("trajectory_path")
        if not path_raw:
            continue
        path = Path(str(path_raw))
        try:
            trajectory = json.loads(
                path.read_text(encoding="utf-8", errors="replace")
            )
        except (OSError, json.JSONDecodeError):
            continue

        text_candidates: list[str] = []

        def collect(node: Any) -> None:
            if isinstance(node, dict):
                content = node.get("content")
                if isinstance(content, str):
                    lowered = content.lower()
                    if (
                        "policy history analysis" in lowered
                        and "net v1 -> v3 changes" in lowered
                    ):
                        text_candidates.append(content)
                for child in node.values():
                    collect(child)
            elif isinstance(node, list):
                for child in node:
                    collect(child)

        collect(trajectory)
        if not text_candidates:
            continue

        def candidate_score(value: str) -> tuple[int, int]:
            lowered = value.lower()
            signals = {
                variant
                for variants in semantic_variants.values()
                for variant in variants
                if variant in lowered
            }
            return len(signals), len(value)

        report = max(text_candidates, key=candidate_score)
        lowered = report.lower()
        exact_hits = [token for token in verifier_tokens if token in lowered]
        semantic_hits = [
            label
            for label, variants in semantic_variants.items()
            if any(variant in lowered for variant in variants)
        ]
        rows.append({
            "model": observation.get("model"),
            "condition": observation.get("condition"),
            "verifier_literal_hits": exact_hits,
            "verifier_literal_hit_count": len(exact_hits),
            "source_normalized_semantic_hits": semantic_hits,
            "source_normalized_semantic_hit_count": len(semantic_hits),
            "hidden_threshold": 4,
            "hidden_literal_check_passes": len(exact_hits) >= 4,
            "source_normalized_check_passes": len(semantic_hits) >= 4,
            "required_sections_present": all(
                heading in lowered
                for heading in (
                    "v1 -> v2",
                    "v2 -> v3",
                    "rollbacks",
                    "net v1 -> v3 changes",
                )
            ),
            "trajectory_path": str(path.resolve()),
        })

    policy_v2 = task_root / "environment" / "policy_v2.md"
    source_text = policy_v2.read_text(encoding="utf-8", errors="replace")
    return {
        "method": (
            "Recover the generated report from trajectory tool output; compare "
            "the verifier's five literal tokens with semantically identical "
            "spellings copied from policy_v2.md."
        ),
        "verifier_tokens": verifier_tokens,
        "source_policy_uses_en_dash_core_hours": "10 AM – 4 PM" in source_text,
        "source_policy_uses_per_month_stipend": "$150 per month" in source_text,
        "models": rows,
        "policy_v2_path": str(policy_v2.resolve()),
    }


def reproduce_e5_ls3_t5_label_identifiability(
    task_root: Path, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Show when fake versus invalid cannot be recovered from public metadata."""

    packet_path = task_root / "environment" / "citation_packet.json"
    manifest_path = task_root / "environment" / "source_manifest.json"
    evidence_path = task_root / "environment" / "evidence_index.json"
    ground_truth_path = task_root / "tests" / "ground_truth.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    public_source_ids = {
        str(row.get("id")) for row in manifest if isinstance(row, dict)
    } | {str(row.get("source_id")) for row in evidence if isinstance(row, dict)}
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    absent_rows = []
    for citation in packet:
        citation_id = str(citation["citation_id"])
        source_id = str(citation.get("source_id") or "")
        row = {
            "citation_id": citation_id,
            "source_id": source_id,
            "expected_label": ground_truth["labels"].get(citation_id),
            "article_claim": str(citation.get("article_claim") or ""),
        }
        by_source[source_id].append(row)
        if source_id not in public_source_ids:
            absent_rows.append(row)
    contradictory_source_labels = [
        {
            "source_id": source_id,
            "citation_ids": [row["citation_id"] for row in group],
            "expected_labels": sorted({str(row["expected_label"]) for row in group}),
        }
        for source_id, group in sorted(by_source.items())
        if source_id not in public_source_ids
        and len({row["expected_label"] for row in group}) > 1
    ]
    leaked_label_words = ("fake", "invalid", "selective", "misrepresented")
    claim_label_leak = {
        row["citation_id"]: [
            label
            for label in leaked_label_words
            if re.search(rf"\b{re.escape(label)}\b", row["article_claim"], re.I)
        ]
        for group in by_source.values()
        for row in group
    }

    models = []
    for observation in observations:
        artifact_raw = observation.get("artifact_task_path")
        if not artifact_raw:
            continue
        output_path = Path(str(artifact_raw)) / "output" / "citation_audit.json"
        if not output_path.is_file():
            continue
        output = json.loads(output_path.read_text(encoding="utf-8"))
        actual = {
            str(row.get("citation_id")): str(row.get("label"))
            for row in output.get("results", [])
            if isinstance(row, dict)
        }
        models.append(
            {
                "model": observation.get("model"),
                "condition": observation.get("condition"),
                "missing_registry_labels": {
                    row["citation_id"]: actual.get(row["citation_id"])
                    for row in absent_rows
                },
                "missing_registry_labels_are_consistent": len(
                    {actual.get(row["citation_id"]) for row in absent_rows}
                )
                <= 1,
                "artifact_output_path": str(output_path.resolve()),
            }
        )

    return {
        "method": (
            "Join citation_packet, source_manifest, evidence_index and hidden "
            "labels by source_id; test whether identical public source evidence "
            "maps to contradictory fake/invalid labels."
        ),
        "absent_from_public_registry": absent_rows,
        "absent_source_expected_label_counts": dict(
            sorted(Counter(str(row["expected_label"]) for row in absent_rows).items())
        ),
        "same_source_id_with_conflicting_hidden_labels": contradictory_source_labels,
        "article_claim_label_word_leak": claim_label_leak,
        "models": models,
        "packet_path": str(packet_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "evidence_path": str(evidence_path.resolve()),
        "ground_truth_path": str(ground_truth_path.resolve()),
    }


def reproduce_e5_ls3_t6_semantic_audit(
    task_root: Path, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Separate semantic citation auditing from hidden lexical contracts."""

    packet_path = task_root / "environment" / "citation_packet.json"
    manifest_path = task_root / "environment" / "source_manifest.json"
    ground_truth_path = task_root / "tests" / "ground_truth.json"
    packet = {
        str(row["citation_id"]): row
        for row in json.loads(packet_path.read_text(encoding="utf-8"))
    }
    manifest = {
        str(row["id"]): row
        for row in json.loads(manifest_path.read_text(encoding="utf-8"))
    }
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    s02 = packet["S02"]
    s02_source = manifest[str(s02["source_id"])]

    models = []
    for observation in observations:
        artifact_raw = observation.get("artifact_task_path")
        if not artifact_raw:
            continue
        artifact_root = Path(str(artifact_raw))
        output_path = artifact_root / "output" / "citation_audit.json"
        policy_path = artifact_root / "citation_policy.py"
        if not output_path.is_file():
            continue
        output = json.loads(output_path.read_text(encoding="utf-8"))
        results = {
            str(row.get("citation_id")): row
            for row in output.get("results", [])
            if isinstance(row, dict)
        }
        mismatches = [
            {
                "citation_id": citation_id,
                "expected": expected,
                "actual": (results.get(citation_id) or {}).get("label"),
            }
            for citation_id, expected in ground_truth["labels"].items()
            if (results.get(citation_id) or {}).get("label") != expected
        ]
        m02_reason = str((results.get("M02") or {}).get("reason") or "").lower()
        official_m02_terms = [
            str(term).lower() for term in ground_truth["reason_terms"]["M02"]
        ]
        policy_text = (
            policy_path.read_text(encoding="utf-8", errors="replace").lower()
            if policy_path.is_file()
            else ""
        )
        models.append(
            {
                "model": observation.get("model"),
                "condition": observation.get("condition"),
                "exact_label_count": len(ground_truth["labels"]) - len(mismatches),
                "total_label_count": len(ground_truth["labels"]),
                "label_mismatches": mismatches,
                "m02_reason": m02_reason,
                "m02_official_reason_word_match": any(
                    term in m02_reason for term in official_m02_terms
                ),
                "m02_semantic_topic_mismatch_match": any(
                    term in m02_reason
                    for term in (
                        "unrelated",
                        "off-topic",
                        "topic mismatch",
                        "water intake",
                    )
                ),
                "policy_checks_manifest_authenticity_semantics": (
                    "authentic" in policy_text
                    and ("fake_citation" in policy_text or "source_type" in policy_text)
                ),
                "policy_satisfies_hidden_authenticity_token_shape": (
                    "authenticity" in policy_text
                    and ("doi" in policy_text or "journal" in policy_text)
                ),
                "artifact_output_path": str(output_path.resolve()),
                "artifact_policy_path": str(policy_path.resolve()),
            }
        )

    s02_claim = str(s02.get("article_claim") or "").lower()
    s02_notes = str(s02_source.get("notes") or "").lower()
    return {
        "method": (
            "Recompute exact label agreement; then independently test whether "
            "S02 already carries the source scope, whether M02 states a semantic "
            "topic mismatch, and whether authenticity is checked via manifest fields."
        ),
        "s02_claim": s02.get("article_claim"),
        "s02_source_note": s02_source.get("notes"),
        "s02_claim_preserves_image_scope": (
            "retinal image" in s02_claim
            and ("image-based" in s02_notes or "retinal" in s02_notes)
        ),
        "s02_claim_makes_universal_or_all_settings_claim": bool(
            re.search(r"\b(?:universal|all settings|all patients|every)\b", s02_claim)
        ),
        "models": models,
        "packet_path": str(packet_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "ground_truth_path": str(ground_truth_path.resolve()),
    }


def reproduce_e5_ls4_hierarchy_semantics(
    task_root: Path, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare positional/lexical checks with the actual hierarchy semantics."""

    ground_truth_path = task_root / "tests" / "ground_truth.json"
    schema_path = task_root / "environment" / "schemas" / "output_schema.json"
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    rows = []
    for observation in observations:
        artifact_raw = observation.get("artifact_task_path")
        if not artifact_raw:
            continue
        output_path = Path(str(artifact_raw)) / "output" / "summary.json"
        if not output_path.is_file():
            continue
        output = json.loads(output_path.read_text(encoding="utf-8"))
        article_summaries = output.get("article_summaries") or []
        group_summaries = output.get("group_summaries") or []
        overall = output.get("overall_summary") or {}
        summaries = [*article_summaries, *group_summaries, overall]
        joined = " ".join(
            str(summary.get("text") or "")
            for summary in summaries
            if isinstance(summary, dict)
        ).lower()
        selected = {
            str(section_id)
            for summary in summaries
            if isinstance(summary, dict)
            for section_id in summary.get("selected_sections", [])
        }
        group_semantics = []
        for index, summary in enumerate(group_summaries):
            text = str(summary.get("text") or "").lower()
            declared = str(
                summary.get("group_id") or summary.get("theme") or ""
            ).lower()
            inferred = declared
            if not inferred:
                if "method" in text:
                    inferred = "method"
                elif "application" in text:
                    inferred = "application"
            group_semantics.append(
                {
                    "index": index,
                    "declared_or_inferred_theme": inferred,
                    "text_contains_theme": bool(inferred and inferred in text),
                }
            )
        exact_required = {
            term: term.lower() in joined for term in ground_truth["required_terms"]
        }
        semantic_required = dict(exact_required)
        semantic_required["validation"] = (
            semantic_required.get("validation", False)
            or "validated" in joined
            or any("validation" in section_id.lower() for section_id in selected)
        )
        semantic_required["skin"] = (
            semantic_required.get("skin", False)
            or "dermatolog" in joined
            or any("skin" in section_id.lower() for section_id in selected)
        )
        word_limits_ok = (
            all(
                int(summary.get("word_count", 10**9))
                <= int(ground_truth["limits"]["article"])
                for summary in article_summaries
            )
            and all(
                int(summary.get("word_count", 10**9))
                <= int(ground_truth["limits"]["group"])
                for summary in group_summaries
            )
            and int(overall.get("word_count", 10**9))
            <= int(ground_truth["limits"]["overall"])
        )
        rows.append(
            {
                "model": observation.get("model"),
                "condition": observation.get("condition"),
                "article_summary_count": len(article_summaries),
                "group_summary_count": len(group_summaries),
                "has_overall_summary": isinstance(overall, dict) and bool(overall),
                "word_limits_ok": word_limits_ok,
                "must_select_complete": set(ground_truth["must_select"]) <= selected,
                "forbidden_terms_absent": all(
                    str(term).lower() not in joined
                    for term in ground_truth.get("forbidden_terms", [])
                ),
                "exact_required_terms": exact_required,
                "exact_required_terms_complete": all(exact_required.values()),
                "source_normalized_required_terms": semantic_required,
                "source_normalized_required_terms_complete": all(
                    semantic_required.values()
                ),
                "group_semantics": group_semantics,
                "semantic_group_set_complete": {
                    row["declared_or_inferred_theme"] for row in group_semantics
                }
                == {"method", "application"},
                "hidden_positional_group_check_passes": (
                    len(group_summaries) >= 2
                    and "method" in str(group_summaries[0].get("text") or "").lower()
                    and "application"
                    in str(group_summaries[1].get("text") or "").lower()
                ),
                "artifact_output_path": str(output_path.resolve()),
            }
        )

    instruction = (
        (task_root / "instruction.md")
        .read_text(encoding="utf-8", errors="replace")
        .lower()
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    group_item_properties = (
        schema.get("properties", {})
        .get("group_summaries", {})
        .get("items", {})
        .get("properties", {})
    )
    return {
        "method": (
            "Recompute hierarchy cardinalities, selections, word limits and "
            "theme coverage; compare semantic group identity and validation "
            "word-family evidence with the verifier's array-position and exact "
            "substring checks."
        ),
        "instruction_explicitly_prescribes_method_first_group_order": bool(
            re.search(r"method.{0,40}(?:first|index\s*0|group\s*0)", instruction)
        ),
        "schema_requires_group_theme_or_id": (
            "theme" in group_item_properties or "group_id" in group_item_properties
        ),
        "models": rows,
        "ground_truth_path": str(ground_truth_path.resolve()),
        "schema_path": str(schema_path.resolve()),
    }


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
            trajectory_rel = row.get("local_trajectory_path")
            trajectory_path = raw_root / trajectory_rel if trajectory_rel else None
            trajectory_activity = (
                trajectory_tool_activity(trajectory_path)
                if trajectory_path and trajectory_path.is_file()
                else trajectory_tool_activity(Path("/nonexistent"))
            )
            trial_rel = row.get("local_trial_path")
            trial_result_path = (
                raw_root / trial_rel / "result.json" if trial_rel else None
            )
            trial_result = (
                load_json_optional(trial_result_path)
                if trial_result_path and trial_result_path.is_file()
                else {}
            )
            observations.append({
                "model": row["model"],
                "condition": row.get("condition"),
                "strict": row.get("strict_pass"),
                "outcome": row.get("outcome_pass"),
                "process": row.get("process_pass"),
                "score": row.get("normalized_score"),
                "failed_outcome_tests": row.get("failed_outcome_tests") or [],
                "failed_process_tests": row.get("failed_process_tests") or [],
                "files": files,
                "artifact_task_path": (
                    str(task_root.resolve()) if rel and task_root.is_dir() else None
                ),
                "trajectory_path": (
                    str(trajectory_path.resolve())
                    if trajectory_path and trajectory_path.is_file()
                    else None
                ),
                "tool_counts": trajectory_activity["tool_counts"],
                "bash_commands": trajectory_activity["bash_commands"],
                "mutation_call_count": trajectory_activity[
                    "mutation_call_count"
                ],
                "final_edits": trajectory_activity["final_edits"],
                "agent_result": trial_result.get("agent_result") or {},
            })
        if not observations:
            continue
        process_raw = str(verifier.get("process", {}).get("path") or "")
        outcome_raw = str(verifier.get("outcome", {}).get("path") or "")
        process_path = Path(process_raw) if process_raw else None
        outcome_path = Path(outcome_raw) if outcome_raw else None
        task_slug = str(verifier.get("task_slug") or "")
        tasks_root_raw = str(audit.get("tasks_root") or "")
        task_root = (
            Path(tasks_root_raw) / task_slug
            if tasks_root_raw and task_slug
            else None
        )
        instruction_path = task_root / "instruction.md" if task_root else None
        solution_path = task_root / "solution" / "solve.sh" if task_root else None
        task_source_files = []
        if task_root:
            for name in definition.get("task_source_files", []):
                path = task_root / name
                if path.is_file():
                    task_source_files.append(
                        {
                            "name": name,
                            "path": str(path.resolve()),
                            "content": path.read_text(
                                encoding="utf-8", errors="replace"
                            ),
                        }
                    )
        reproduction: dict[str, Any] = {}
        if task_id == "E3-LS5-T5" and task_root:
            reproduction = reproduce_e3_ls5_active_counts(task_root)
        self_artifact_path = next(
            (
                Path(str(observation["artifact_task_path"]))
                for observation in observations
                if observation.get("condition") == "self_generated"
                and observation.get("model") == "sig-fable"
                and observation.get("artifact_task_path")
            ),
            None,
        )
        if (
            task_id == "E3-LS2-T6"
            and task_root
            and self_artifact_path
        ):
            reproduction = reproduce_e3_ls2_record_shape(
                task_root, self_artifact_path
            )
        if (
            task_id == "E3-LS3-T6"
            and task_root
            and self_artifact_path
        ):
            reproduction = reproduce_e3_ls3_category_order(
                task_root, self_artifact_path
            )
        qwen_self_artifact_path = next(
            (
                Path(str(observation["artifact_task_path"]))
                for observation in observations
                if observation.get("condition") == "self_generated"
                and observation.get("model") == "qwen3.7-max"
                and observation.get("artifact_task_path")
            ),
            None,
        )
        if (
            task_id == "E4-LS3-T5"
            and task_root
            and qwen_self_artifact_path
        ):
            reproduction = reproduce_e4_ls3_missing_markers(
                task_root, qwen_self_artifact_path
            )
        if task_id == "E4-LS4-T6" and task_root:
            reproduction = reproduce_e4_ls4_literal_surface(
                task_root, observations
            )
        if task_id == "E5-LS3-T5" and task_root:
            reproduction = reproduce_e5_ls3_t5_label_identifiability(
                task_root, observations
            )
        if task_id == "E5-LS3-T6" and task_root:
            reproduction = reproduce_e5_ls3_t6_semantic_audit(task_root, observations)
        if task_id == "E5-LS4-T6" and task_root:
            reproduction = reproduce_e5_ls4_hierarchy_semantics(task_root, observations)
        if task_id == "E6-LS3-T6" and task_root:
            reproduction = reproduce_e6_ls3_action_identity(
                task_root, observations
            )
        if task_id == "E6-LS2-T6" and task_root:
            reproduction = reproduce_e6_ls2_semantic_phrasing(
                task_root, observations
            )
        if task_id == "E6-LS1-T6" and task_root:
            reproduction = reproduce_e6_ls1_hidden_reply_contract(
                task_root, observations
            )
        result.append({
            "task_id": task_id,
            **definition,
            "task_slug": task_slug or None,
            "instruction_path": str(instruction_path) if instruction_path else None,
            "instruction": (
                instruction_path.read_text(encoding="utf-8", errors="replace")
                if instruction_path and instruction_path.is_file()
                else ""
            ),
            "reference_solution_path": str(solution_path) if solution_path else None,
            "reference_solution": (
                solution_path.read_text(encoding="utf-8", errors="replace")
                if solution_path and solution_path.is_file()
                else ""
            ),
            "task_source_files": task_source_files,
            "reproduction": reproduction,
            "process_verifier_path": str(process_path) if process_path else None,
            "process_verifier": (
                process_path.read_text(encoding="utf-8", errors="replace")
                if process_path and process_path.is_file() else ""
            ),
            "outcome_verifier_path": str(outcome_path) if outcome_path else None,
            "outcome_verifier": (
                outcome_path.read_text(encoding="utf-8", errors="replace")
                if outcome_path and outcome_path.is_file() else ""
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


def matched_skill_content_diagnostics(
    learning: dict[str, Any], comparisons: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Contrast skill text with matched self/exact T5-T6 behavior by slice.

    This deliberately keeps content distance separate from causal effect.  A
    low Jaccard score or more verifier language is descriptive evidence only;
    the paired outcome/strict vectors say whether that content change altered
    observed behavior on the same tasks.
    """
    family_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for family in learning.get("families", []):
        if not isinstance(family, dict):
            continue
        key = (str(family.get("model") or ""), str(family.get("environment_id") or ""))
        family_groups[key].append(family)

    result: list[dict[str, Any]] = []
    for model in MODELS:
        for environment_id in ENVS:
            matched = sorted(
                (
                    row
                    for row in comparisons
                    if row.get("model") == model
                    and row.get("environment_id") == environment_id
                    and int(row.get("tier") or 0) in (5, 6)
                    and row.get("conditions", {}).get("self_generated") is not None
                    and row.get("conditions", {}).get("exact_oracle") is not None
                ),
                key=lambda row: str(row.get("task_id") or ""),
            )
            if not matched:
                continue

            families = family_groups.get((model, environment_id), [])
            jaccards = sorted(
                float(row["best_word_jaccard"])
                for row in families
                if row.get("best_word_jaccard") is not None
            )
            generated_chars = sum(len(str(row.get("generated_text") or "")) for row in families)
            curated_chars = sum(len(str(row.get("curated_text") or "")) for row in families)
            generated_concepts = sorted({
                str(concept)
                for row in families
                for concept in row.get("generated_concepts", [])
            })
            curated_concepts = sorted({
                str(concept)
                for row in families
                for concept in row.get("curated_concepts", [])
            })

            def passed(condition: str, metric: str) -> int:
                return sum(
                    row["conditions"][condition].get(metric) is True
                    for row in matched
                )

            def identical(metric: str) -> bool:
                return all(
                    row["conditions"]["self_generated"].get(metric)
                    is row["conditions"]["exact_oracle"].get(metric)
                    for row in matched
                )

            compliance_rows = []
            for row in matched:
                exact = row["conditions"]["exact_oracle"]
                expected = set(exact.get("oracle_skill_ids") or [])
                used = set(exact.get("skills_actually_used") or [])
                if expected:
                    compliance_rows.append(expected.issubset(used))

            controls = {}
            for condition in ("no_skill", "curated_all"):
                observed = [
                    row for row in matched
                    if row["conditions"].get(condition) is not None
                ]
                controls[condition] = {
                    "observed": len(observed),
                    "outcome_passed": sum(
                        row["conditions"][condition].get("outcome") is True
                        for row in observed
                    ),
                    "strict_passed": sum(
                        row["conditions"][condition].get("strict") is True
                        for row in observed
                    ),
                }

            result.append({
                "model": model,
                "environment_id": environment_id,
                "matched_tasks": len(matched),
                "complete_t5_t6_slice": len(matched) == 10,
                "outcome_vectors_identical": identical("outcome"),
                "strict_vectors_identical": identical("strict"),
                "self_outcome_passed": passed("self_generated", "outcome"),
                "exact_outcome_passed": passed("exact_oracle", "outcome"),
                "self_strict_passed": passed("self_generated", "strict"),
                "exact_strict_passed": passed("exact_oracle", "strict"),
                "outcome_discordant_task_ids": [
                    str(row.get("task_id") or "")
                    for row in matched
                    if row["conditions"]["self_generated"].get("outcome")
                    is not row["conditions"]["exact_oracle"].get("outcome")
                ],
                "strict_discordant_task_ids": [
                    str(row.get("task_id") or "")
                    for row in matched
                    if row["conditions"]["self_generated"].get("strict")
                    is not row["conditions"]["exact_oracle"].get("strict")
                ],
                "family_count": len(families),
                "generated_skill_count": sum(
                    int(row.get("generated_skill_count") or 0) for row in families
                ),
                "learning_attempts": sum(
                    int(row.get("learning_attempts") or 0) for row in families
                ),
                "learning_terminal_strict_passes": sum(
                    int(row.get("terminal_strict_passes") or 0) for row in families
                ),
                "learning_repairs": sum(
                    int(row.get("repaired_to_pass") or 0) for row in families
                ),
                "median_best_word_jaccard": median(jaccards) if jaccards else None,
                "generated_chars": generated_chars,
                "curated_chars": curated_chars,
                "generated_to_curated_char_ratio": (
                    generated_chars / curated_chars if curated_chars else None
                ),
                "generated_verifier_marker_hits": sum(
                    int(row.get("generated_verifier_marker_hits") or 0)
                    for row in families
                ),
                "oracle_verifier_marker_hits": sum(
                    int(row.get("oracle_verifier_marker_hits") or 0)
                    for row in families
                ),
                "generated_concepts": generated_concepts,
                "curated_concepts": curated_concepts,
                "generated_only_concepts": sorted(
                    set(generated_concepts) - set(curated_concepts)
                ),
                "curated_only_concepts": sorted(
                    set(curated_concepts) - set(generated_concepts)
                ),
                "exact_skill_use_audited": len(compliance_rows),
                "exact_full_skill_use": sum(compliance_rows),
                "controls": controls,
            })
    return result


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
            "v2 full-task controlled concept-pattern screen over T5/T6 instructions and "
            "verifier check names versus T1-T3 visible instructions/feedback and both "
            "skill texts; every T5/T6 task was manually inspected when expanding the "
            "dictionary, but matching remains lexical rather than a semantic proof"
        ),
        "concept_dictionary": [
            {"concept": concept, "pattern": pattern}
            for concept, pattern in CONCEPT_PATTERNS.items()
        ],
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


def validity_stratified_effects(
    comparisons: list[dict[str, Any]],
    measurement_validity: dict[str, Any],
) -> list[dict[str, Any]]:
    validity = {
        (str(row.get("model")), str(row.get("task_id"))): str(
            row.get("category")
        )
        for row in measurement_validity.get("records", [])
        if isinstance(row, dict)
    }
    contrasts = (
        ("self_generated", "no_skill"),
        ("exact_oracle", "self_generated"),
        ("exact_oracle", "no_skill"),
        ("exact_oracle", "curated_all"),
    )
    result = []
    for model in MODELS:
        model_rows = [
            row
            for row in comparisons
            if row["model"] == model and int(row["tier"]) in {5, 6}
        ]
        categories = sorted(
            {
                validity.get((model, str(row["task_id"])), "missing")
                for row in model_rows
            }
        )
        for category in categories:
            group = [
                row
                for row in model_rows
                if validity.get((model, str(row["task_id"])), "missing")
                == category
            ]
            complete = [row for row in group if row["causal"]["complete"]]
            for treatment, reference in contrasts:
                matched = [
                    row
                    for row in group
                    if row["conditions"][treatment] is not None
                    and row["conditions"][reference] is not None
                ]
                treatment_pass = sum(
                    row["conditions"][treatment]["outcome"] is True
                    for row in matched
                )
                reference_pass = sum(
                    row["conditions"][reference]["outcome"] is True
                    for row in matched
                )
                result.append(
                    {
                        "model": model,
                        "validity_category": category,
                        "task_count": len(group),
                        "complete_four_conditions": len(complete),
                        "complete_causal_category_counts": dict(
                            sorted(
                                Counter(
                                    row["causal"]["category"] for row in complete
                                ).items()
                            )
                        ),
                        "treatment": treatment,
                        "reference": reference,
                        "n": len(matched),
                        "treatment_pass": treatment_pass,
                        "reference_pass": reference_pass,
                        "delta": rate(
                            treatment_pass - reference_pass, len(matched)
                        ),
                        "rescued": sum(
                            row["conditions"][reference]["outcome"] is not True
                            and row["conditions"][treatment]["outcome"] is True
                            for row in matched
                        ),
                        "harmed": sum(
                            row["conditions"][reference]["outcome"] is True
                            and row["conditions"][treatment]["outcome"] is not True
                            for row in matched
                        ),
                    }
                )
    return result


def pearson_correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)
    if left_variance == 0 or right_variance == 0:
        return None
    covariance = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right)
    )
    return covariance / math.sqrt(left_variance * right_variance)


def learning_transfer_diagnostics(
    learning: dict[str, Any],
    comparisons: list[dict[str, Any]],
    measurement_validity: dict[str, Any],
) -> dict[str, Any]:
    """Relate acquisition evidence to later self-generated outcomes.

    This is descriptive, not a causal estimate: family difficulty can affect
    both T1-T3 acquisition and T5/T6 performance, and no-skill controls are
    required before any difference can be attributed to the generated skill.
    """

    families = {
        (str(row.get("model")), str(row.get("family_id"))): row
        for row in learning.get("families", [])
        if isinstance(row, dict) and row.get("model") and row.get("family_id")
    }
    self_outcomes: dict[tuple[str, str], dict[int, bool]] = defaultdict(dict)
    for row in comparisons:
        if int(row.get("tier", -1)) not in (5, 6):
            continue
        condition = row.get("conditions", {}).get("self_generated")
        if not isinstance(condition, dict):
            continue
        family_id = str(row.get("task_id") or "").rsplit("-T", 1)[0]
        self_outcomes[(str(row.get("model")), family_id)][int(row["tier"])] = (
            condition.get("outcome") is True
        )

    rows: list[dict[str, Any]] = []
    for key, outcomes in sorted(self_outcomes.items()):
        family = families.get(key)
        if family is None or set(outcomes) != {5, 6}:
            continue
        rows.append(
            {
                "model": key[0],
                "family_id": key[1],
                "terminal_strict_passes": int(
                    family.get("terminal_strict_passes") or 0
                ),
                "learning_attempts": int(family.get("learning_attempts") or 0),
                "repaired_to_pass": int(family.get("repaired_to_pass") or 0),
                "best_word_jaccard": float(family.get("best_word_jaccard") or 0),
                "t5_outcome": outcomes[5],
                "t6_outcome": outcomes[6],
            }
        )

    validity_by_key = {
        (str(row.get("model")), str(row.get("task_id"))): row
        for row in measurement_validity.get("records", [])
        if isinstance(row, dict)
    }
    comparison_by_key = {
        (str(row.get("model")), str(row.get("task_id"))): row
        for row in comparisons
        if int(row.get("tier", -1)) in (5, 6)
    }
    summaries: list[dict[str, Any]] = []
    for model in MODELS:
        model_rows = [row for row in rows if row["model"] == model]
        pass_groups = []
        for terminal_passes in range(4):
            group = [
                row
                for row in model_rows
                if row["terminal_strict_passes"] == terminal_passes
            ]
            pass_groups.append(
                {
                    "terminal_strict_passes": terminal_passes,
                    "families": len(group),
                    "t5_passed": sum(row["t5_outcome"] for row in group),
                    "t6_passed": sum(row["t6_outcome"] for row in group),
                    "combined_passed": sum(
                        row["t5_outcome"] + row["t6_outcome"] for row in group
                    ),
                    "combined_total": 2 * len(group),
                }
            )

        coverage_groups = []
        for coverage in ("all", "partial", "none"):
            group = []
            for key, validity in validity_by_key.items():
                if key[0] != model or validity.get("generated_coverage") != coverage:
                    continue
                comparison = comparison_by_key.get(key)
                if comparison is None:
                    continue
                condition = comparison.get("conditions", {}).get("self_generated")
                if isinstance(condition, dict):
                    group.append(condition.get("outcome") is True)
            coverage_groups.append(
                {
                    "generated_coverage": coverage,
                    "tasks": len(group),
                    "outcome_passed": sum(group),
                    "outcome_rate": rate(sum(group), len(group)),
                }
            )

        def values(name: str) -> list[float]:
            return [float(row[name]) for row in model_rows]

        t5 = [float(row["t5_outcome"]) for row in model_rows]
        t6 = [float(row["t6_outcome"]) for row in model_rows]
        combined = [
            (float(row["t5_outcome"]) + float(row["t6_outcome"])) / 2
            for row in model_rows
        ]
        summaries.append(
            {
                "model": model,
                "families": len(model_rows),
                "by_terminal_strict_passes": pass_groups,
                "by_generated_concept_coverage": coverage_groups,
                "correlations": {
                    "terminal_passes_vs_t5": pearson_correlation(
                        values("terminal_strict_passes"), t5
                    ),
                    "terminal_passes_vs_t6": pearson_correlation(
                        values("terminal_strict_passes"), t6
                    ),
                    "terminal_passes_vs_combined": pearson_correlation(
                        values("terminal_strict_passes"), combined
                    ),
                    "learning_attempts_vs_t6": pearson_correlation(
                        values("learning_attempts"), t6
                    ),
                    "repairs_vs_t6": pearson_correlation(
                        values("repaired_to_pass"), t6
                    ),
                    "generated_oracle_jaccard_vs_t6": pearson_correlation(
                        values("best_word_jaccard"), t6
                    ),
                },
            }
        )
    return {
        "method": (
            "descriptive family-level association between T1-T3 acquisition and "
            "self-generated T5/T6 outcome; not causal and confounded by family difficulty"
        ),
        "rows": rows,
        "summaries": summaries,
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
        "method": (
            "v2 full-task lexical screening after manual inspection of all 60 T5/T6; "
            "scope-risk cases still require task/skill review"
        ),
        "counts": dict(Counter(row["scope_risk"] for row in rows)),
        "concept_visibility": {
            "concept_dictionary_size": len(CONCEPT_PATTERNS),
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
        model_task = (str(row.get("model") or ""), task_id)
        shape = shape_by_task.get(task_id, "unknown")
        if row.get("outcome_pass") is not True:
            if model_task in VERIFIED_OUTCOME_FALSE_NEGATIVE_PAIRS:
                cause = "verified_benchmark_false_negative"
            elif task_id in INVALID_OR_UNDERDETERMINED_TASKS:
                cause = "invalid_or_underdetermined_task"
            elif model_task in MIXED_BENCHMARK_MODEL_GAP_PAIRS:
                cause = "mixed_benchmark_and_model_gap"
            else:
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
    cases: list[dict[str, Any]],
    matched_skill_content: list[dict[str, Any]],
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
    matched_exact = [
        row
        for row in comparisons
        if int(row["tier"]) in (5, 6)
        and row["conditions"]["self_generated"] is not None
        and row["conditions"]["exact_oracle"] is not None
    ]
    if matched_exact:
        self_outcome = sum(
            row["conditions"]["self_generated"]["outcome"] is True
            for row in matched_exact
        )
        exact_outcome = sum(
            row["conditions"]["exact_oracle"]["outcome"] is True
            for row in matched_exact
        )
        self_strict = sum(
            row["conditions"]["self_generated"]["strict"] is True
            for row in matched_exact
        )
        exact_strict = sum(
            row["conditions"]["exact_oracle"]["strict"] is True
            for row in matched_exact
        )
        rescued = sum(
            row["conditions"]["self_generated"]["outcome"] is not True
            and row["conditions"]["exact_oracle"]["outcome"] is True
            for row in matched_exact
        )
        harmed = sum(
            row["conditions"]["self_generated"]["outcome"] is True
            and row["conditions"]["exact_oracle"]["outcome"] is not True
            for row in matched_exact
        )
        harmed_task_ids = [
            str(row["task_id"])
            for row in matched_exact
            if row["conditions"]["self_generated"]["outcome"] is True
            and row["conditions"]["exact_oracle"]["outcome"] is not True
        ]
        strict_rescued = sum(
            row["conditions"]["self_generated"]["strict"] is not True
            and row["conditions"]["exact_oracle"]["strict"] is True
            for row in matched_exact
        )
        strict_harmed = sum(
            row["conditions"]["self_generated"]["strict"] is True
            and row["conditions"]["exact_oracle"]["strict"] is not True
            for row in matched_exact
        )
        exact_assigned = [
            row
            for row in comparisons
            if row["conditions"]["exact_oracle"] is not None
        ]
        exact_compliant = sum(
            bool(row["conditions"]["exact_oracle"]["oracle_skill_ids"])
            and set(row["conditions"]["exact_oracle"]["oracle_skill_ids"]).issubset(
                row["conditions"]["exact_oracle"]["skills_actually_used"]
            )
            for row in exact_assigned
        )
        slices = ", ".join(
            sorted(
                {
                    f"{row['model']}/{row['environment_id']}"
                    for row in matched_exact
                }
            )
        )
        known_e3_defect_harms = {"E3-LS4-T6", "E3-LS5-T5"}
        if (
            harmed
            and not rescued
            and set(harmed_task_ids).issubset(known_e3_defect_harms)
        ):
            outcome_note = (
                f"Outcome 已出现 {harmed} 个 exact harm，均来自 E3 已核实的 benchmark 合同缺陷"
                "（E3-LS4-T6 的隐藏 audit shape、E3-LS5-T5 的错误 706 ground truth），"
                "不能解释为 oracle skill 造成真实能力下降。"
            )
        elif rescued or harmed:
            outcome_note = (
                f"Outcome 已出现 {rescued + harmed} 个 discordant pairs，必须逐题查代码后"
                "再判断是 skill 效应、执行随机性还是 benchmark 合同缺陷。"
            )
        else:
            outcome_note = (
                "当前 matched outcome 完全不变，尚没有 oracle 功能 rescue/harm 证据。"
            )
        if strict_rescued or strict_harmed:
            strict_note = (
                f"Strict 出现 {strict_rescued} 个 rescue 与 {strict_harmed} 个 harm；"
                "已审案例主要是固定文件、字面量和输出形状路径变化，不能直接当成功能迁移。"
            )
        else:
            strict_note = "Strict 也没有 discordant pair。"
        result.append(
            {
                "level": "warn",
                "title": "当前 Exact Oracle matched slices 尚无 outcome 救回",
                "body": (
                    f"目前只有 {slices} 形成 {len(matched_exact)} 个 T5/T6 self/exact 配对："
                    f"self-generated outcome {self_outcome}/{len(matched_exact)}，"
                    f"exact-oracle {exact_outcome}/{len(matched_exact)}，救回 {rescued}、"
                    f"损害 {harmed}；strict 则 self={self_strict}/{len(matched_exact)}、"
                    f"exact={exact_strict}/{len(matched_exact)}，救回 {strict_rescued}、"
                    f"损害 {strict_harmed}。{outcome_note}{strict_note}Exact 条件在已导出的 T4–T6 中有 "
                    f"{exact_compliant}/{len(exact_assigned)} 题实际打开了全部指定 skill，"
                    "所以当前零增益不能归因于 treatment 普遍没挂载；目前仅覆盖上述 "
                    f"{len(set((row['model'], row['environment_id']) for row in matched_exact))} 个"
                    "模型×环境 slice，且有个别 T6 只读取了指定 skill 子集。No-skill 与 curated-all"
                    "仍未齐，不能外推为最终结论。"
                ),
            }
        )
    qwen_e2 = next(
        (
            row
            for row in matched_skill_content
            if row["model"] == "qwen3.7-max"
            and row["environment_id"] == "E2"
            and row["complete_t5_t6_slice"]
        ),
        None,
    )
    if (
        qwen_e2
        and qwen_e2["outcome_vectors_identical"]
        and qwen_e2["strict_vectors_identical"]
    ):
        ratio = qwen_e2["generated_to_curated_char_ratio"]
        ratio_text = f"{ratio:.2f}×" if ratio is not None else "未知"
        jaccard = qwen_e2["median_best_word_jaccard"]
        jaccard_text = f"{jaccard:.3f}" if jaccard is not None else "未知"
        no_skill = qwen_e2["controls"]["no_skill"]
        control_note = (
            f"No-skill 已有 {no_skill['observed']}/10，outcome "
            f"{no_skill['outcome_passed']}/{no_skill['observed']}。"
            if no_skill["observed"]
            else "No-skill 尚未到齐，所以这不能证明 E2 不需要 skill。"
        )
        result.append({
            "level": "warn",
            "title": "Qwen/E2：Skill 内容差异很大，但 10 题行为向量完全相同",
            "body": (
                f"Qwen/E2 的 10 个 T5/T6 self/exact 配对中，outcome 都是 "
                f"{qwen_e2['self_outcome_passed']}/10，strict 都是 "
                f"{qwen_e2['self_strict_passed']}/10，逐题向量而非仅总分完全一致。"
                f"与此同时，T1–T3 产生 {qwen_e2['generated_skill_count']} 个 skills，"
                f"相对 5 个 curated family 的中位 best Jaccard 仅 {jaccard_text}，"
                f"总字符数为 curated 的 {ratio_text}，并含 "
                f"{qwen_e2['generated_verifier_marker_hits']} 个 verifier/process/source-scan markers，"
                f"curated 为 {qwen_e2['oracle_verifier_marker_hits']}。Exact 运行中 "
                f"{qwen_e2['exact_full_skill_use']}/{qwen_e2['exact_skill_use_audited']} 题读取了"
                "全部指定 skill。因此，这个 slice 证明“更丰富且更贴测试的 generated 内容”"
                "和“更短的 curated scaffold”在当前题集上没有产生可测行为差异；它不证明"
                f"两类 skill 等质，也不证明 skill 无用。{control_note}"
            ),
        })
    e1_matched = {
        str(row["model"]): row
        for row in matched_skill_content
        if row["environment_id"] == "E1"
        and row["complete_t5_t6_slice"]
    }
    qwen_e1 = e1_matched.get("qwen3.7-max")
    fable_e1 = e1_matched.get("sig-fable")
    if (
        qwen_e1
        and fable_e1
        and qwen_e1["outcome_vectors_identical"]
        and qwen_e1["strict_vectors_identical"]
        and fable_e1["outcome_vectors_identical"]
        and fable_e1["strict_vectors_identical"]
    ):
        def decimal_text(value: Any, digits: int) -> str:
            return (
                f"{float(value):.{digits}f}"
                if isinstance(value, (int, float))
                else "未知"
            )

        result.append({
            "level": "warn",
            "title": "E1 跨模型复现：self 与 exact 的 20 组同题结果逐项相同",
            "body": (
                "Qwen 与 Fable 在 E1 各有 10 个 T5/T6 self/exact 配对；两个模型的两种条件都"
                "逐题得到 outcome 8/10、strict 5/10，而非仅平均分相同。Exact 执行中共 "
                f"{qwen_e1['exact_full_skill_use'] + fable_e1['exact_full_skill_use']}/"
                f"{qwen_e1['exact_skill_use_audited'] + fable_e1['exact_skill_use_audited']} 题读取了"
                "全部指定 skill。与此同时，Qwen/Fable generated skill 相对 curated 的总长度为 "
                f"{decimal_text(qwen_e1['generated_to_curated_char_ratio'], 2)}×/"
                f"{decimal_text(fable_e1['generated_to_curated_char_ratio'], 2)}×，中位 best Jaccard 仅 "
                f"{decimal_text(qwen_e1['median_best_word_jaccard'], 3)}/"
                f"{decimal_text(fable_e1['median_best_word_jaccard'], 3)}。共同的两个 outcome failure 仍是 "
                "E1-LS2-T6 的真实数据库 session 迁移执行 gap，以及 E1-LS4-T5 已核实的隐藏"
                "monkeypatch/import-binding 缺陷。故当前最可靠的说法是：在 E1 上把 generated"
                "换成 exact curated 并未改变行为，失败不支持归因为 generated skill 文本质量不足；"
                "但 no-skill 未到齐，尚不能区分“两类 skill 都有效”与“任务主要靠题面即可完成”。"
            ),
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
    strong_task_defects = [
        case for case in cases if "强任务缺陷" in str(case.get("kind") or "")
    ]
    if strong_task_defects:
        ids = ", ".join(str(case["task_id"]) for case in strong_task_defects)
        result.append({
            "level": "warn",
            "title": f"已逐代码核实 {len(strong_task_defects)} 个强 benchmark task 缺陷",
            "body": (
                f"当前明确的是 {ids}。E1-LS4-T5 的隐藏故障注入依赖未声明的 Python import binding，"
                "其余同类替身测试又因全局 modulo-3 调用计数碰巧通过，并叠加固定文件字面量检查；"
                "E2-LS1-T6 的项目自带 public test 要求 3 个结果，但四条 fixture 都是有效输入，官方"
                "reference 产生 4 个结果并因此无法通过该 public test，正式 Fable self/exact 都被矛盾信号"
                "拖入无修改的分析停滞；"
                "E3-LS4-T6 对 source_null_summary 做隐藏 dict 全等，把题面要求的额外 marker audit 当错误；"
                "E3-LS5-T5 的 generator 明确生成 700 active 并把 1,2,3 标为 bad_amount，verifier 却复用"
                "宽松 parser 将其当 123 并硬认 706，导致语义正确的 exact 实现失败；"
                "E3-LS2-T6 的 767 行内容和排序完全正确，仅因题面允许的 count 字段被 record dict 全等"
                "拒绝；E3-LS3-T6 的 segment totals 数值一致，仅数组顺序未匹配未声明的字母序；"
                "E4-LS1-T5 的题面输出路径与 verifier 的父目录合同冲突，"
                "语义正确输出被全部判为 outcome 失败；E4-LS3-T5 的题面明确允许 UNKNOWN、MISSING、"
                "空字符串或 null，隐藏 verifier 却只接受 N/A、字符串 null 和 TODO，且实际 JSON null"
                "经 str(None) 后也会被拒绝；"
                "E4-LS4-T6 中两模型都报告了五项首轮变化，但 hidden test 的 `10 am - 4 pm` 与"
                "`$150/month` 两个 token 和原始 policy_v2 的 en-dash、`$150 per month` 写法冲突；"
                "E6-LS3-T6 中两模型都抽取了 8/8 个真实 action，核心"
                "assignee/deadline/status 字段分别命中 23/24 与 22/24，却因未公开的 action-id 词表"
                "被判大量 missing，该题同时仍有少量 status/follow-up 真缺口；E6-LS1-T6 中 Fable"
                "优先级/P0/draft 全对，但被从未公开的 10:30/Immediate/response-list exact set 拒绝，"
                "Qwen 同题另有真实优先级错误；E6-LS2-T6 的两模型"
                "路由、CC 和拒绝过度承诺语义都正确，hidden verifier 却只接受 `not promise`/"
                "`thread context` 两个固定短语；E6-LS4-T6 的四人工作时段没有共同正长度交集，"
                "verifier 却要求题面未声明的固定时间和数组顺序。90/90 reference pass 只能证明官方脚本能满足"
                "官方 verifier，不能排除 reference 利用隐藏合同或任意 tie-break。最终任务质量结论必须把这类题"
                "从纯模型/skill failure 中单独报告。"
            ),
        })
    qwen_e4_t5 = [
        row
        for row in comparisons
        if row["model"] == "qwen3.7-max"
        and row["environment_id"] == "E4"
        and int(row["tier"]) == 5
        and row["conditions"]["self_generated"] is not None
    ]
    if len(qwen_e4_t5) == 5:
        raw_passed = sum(
            row["conditions"]["self_generated"]["outcome"] is True
            for row in qwen_e4_t5
        )
        raw_failed_ids = {
            str(row["task_id"])
            for row in qwen_e4_t5
            if row["conditions"]["self_generated"]["outcome"] is not True
        }
        confirmed_contract_artifacts = {"E4-LS1-T5", "E4-LS3-T5"}
        if raw_failed_ids == confirmed_contract_artifacts:
            result.append({
                "level": "warn",
                "title": "Qwen/E4 T5：原始 3/5，但两个失败均为已复现的契约假阴性",
                "body": (
                    f"官方 outcome 原始值仍应报告为 {raw_passed}/5，不能擅自改分；但失败集合恰好只有 "
                    "E4-LS1-T5 与 E4-LS3-T5。前者已正确抽取两笔 revenue、source 与 conflict，"
                    "三项 process 全过，只错在题面与隐藏 verifier 的输出目录不一致；后者五个现有字段"
                    "和三项 process 全过，只因使用题面明确允许的 MISSING 被隐藏白名单拒绝。故在"
                    "contract-aware 的能力解释中，这 5 个 T5 都显示了任务核心功能完成证据；这是一项"
                    "诊断性语义结论，不是把官方 3/5 改写成新的 benchmark 分数。若不单列这两题，会把"
                    "E4 的 T5 skill-evolve/模型能力低估 40 个百分点。"
                ),
            })
    fable_e4_exact = [
        row
        for row in comparisons
        if row["model"] == "sig-fable"
        and row["environment_id"] == "E4"
        and int(row["tier"]) in (5, 6)
        and row["conditions"]["exact_oracle"] is not None
    ]
    if len(fable_e4_exact) == 10:
        raw_passed = sum(
            row["conditions"]["exact_oracle"]["outcome"] is True
            for row in fable_e4_exact
        )
        raw_failed_ids = {
            str(row["task_id"])
            for row in fable_e4_exact
            if row["conditions"]["exact_oracle"]["outcome"] is not True
        }
        known_contract_artifacts = {
            "E4-LS1-T5",
            "E4-LS3-T5",
            "E4-LS4-T6",
        }
        if raw_failed_ids == known_contract_artifacts:
            result.append({
                "level": "good",
                "title": "Fable/E4 exact oracle：raw 7/10，三个失败全是可复现 verifier 假阴性",
                "body": (
                    f"Fable exact-oracle 的 10 个 T5/T6 官方 outcome 为 {raw_passed}/10；失败集合精确为 "
                    "E4-LS1-T5、E4-LS3-T5、E4-LS4-T6。前两题分别是输出目录错位和 missing-marker"
                    "白名单矛盾；后一题实际输出五项 v1→v2 变化、六项 v2→v3 变化、正确 rollback 与"
                    "net sections，独立复算表明 hidden literal 只命中 3/5，但按任务原始文档表面归一后"
                    "命中 5/5。因此 exact 条件下 10/10 题都有核心语义完成证据。这个结果直接反驳"
                    "“E4 T5/T6 因太难而连 oracle 条件也普遍做不出”；同时，Fable self、no-skill 和"
                    "curated-all 尚未形成同模型配对，所以它还不能证明成功是 oracle skill 造成的。"
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
            f"经逐题检查扩展的 {visibility.get('concept_dictionary_size', 0)} 项受控概念词表在 60 个 T5/T6 中识别到 "
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
            f"missing-learning={counts.get('missing_learning_evidence', 0)}, "
            f"unclassified={counts.get('unclassified_no_controlled_concept', 0)}"
        )
    result.append({
        "level": "warn",
        "title": "并非所有 T5/T6 成功都能作为 Skill Evolution 证据",
        "body": (
            "受控概念筛查显示："
            + "; ".join(validity_parts)
            + "。只在当前题面出现的高级要求，即使模型做对，也只能证明现场执行能力；"
            "有 T1–T3 历史支持的任务也必须再由同题 no-skill 对照证明 skill 增量。"
            "当前词表已逐题扩展到覆盖 60/60，但它仍是 lexical screen，不能用词面命中替代完整语义审查。"
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
    learning_transfer = learning_transfer_diagnostics(
        learning, comparisons, measurement_validity
    )
    matched_skill_content = matched_skill_content_diagnostics(
        learning, comparisons
    )
    validity_effects = validity_stratified_effects(
        comparisons, measurement_validity
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
    cases = build_cases(rows, audit, raw_root)
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
        "cases": cases,
        "skills": skill_summary(evidence),
        "learning": learning,
        "learning_transfer": learning_transfer,
        "matched_skill_content": matched_skill_content,
        "derivability": derivability,
        "measurement_validity": measurement_validity,
        "validity_stratified_effects": validity_effects,
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
            cases,
            matched_skill_content,
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
        "该表先区分 outcome 与 process-only 失败。`Outcome 假阴性`只用于当前模型产物已经独立复算出任务核心语义正确的 model×task；`混合`表示 verifier/task 确有缺陷，但模型还留有真实字段或执行错误；`无效题`表示硬约束不可满足或题面没有唯一 tie-break。Process 假阴性则要求功能测试已过且逐代码确认仅固定文件/字面量扫描失败。其余源码形态敏感项仍标为待复核，不把启发式判断冒充结论。",
        "",
        "| Env | Tier | 模型 | 覆盖 | Strict | 功能 gap | Outcome 假阴性 | 混合 | 无效题 | Process 假阴性 | 实质过程 gap | 形态敏感 | 未决过程 |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in data["failure_attribution"]["summaries"]:
        counts = item["cause_counts"]
        lines.append(
            f"| {item['environment_id']} | T{item['tier']} | {item['model']} | {item['observed']}/5 | "
            f"{item['strict_passed']}/{item['observed']} | {counts.get('functional_gap', 0)} | "
            f"{counts.get('verified_benchmark_false_negative', 0)} | "
            f"{counts.get('mixed_benchmark_and_model_gap', 0)} | "
            f"{counts.get('invalid_or_underdetermined_task', 0)} | "
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
        "### Skill 内容不同，是否真的改变了同题行为？",
        "",
        "这一表只展示已有 self-generated/exact-oracle 同题配对的 model×Env slice。`向量相同`要求每一题的布尔结果都相同，不是只比较总分。内容差异和行为差异分开报告，避免把低 Jaccard 或更长文本直接解释成能力差异。",
        "",
        "| 模型 / Env | 配对 | Outcome S/E | Strict S/E | 逐题向量 O/S | Generated skills | 中位 Jaccard | 字符比 G/O | Verifier markers G/O | Exact 全读 | No-skill outcome |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in data["matched_skill_content"]:
        ratio = item["generated_to_curated_char_ratio"]
        ratio_text = "—" if ratio is None else f"{ratio:.2f}×"
        jaccard = item["median_best_word_jaccard"]
        jaccard_text = "—" if jaccard is None else f"{jaccard:.3f}"
        no_skill = item["controls"]["no_skill"]
        lines.append(
            f"| {item['model']} / {item['environment_id']} | {item['matched_tasks']}/10 | "
            f"{item['self_outcome_passed']}/{item['exact_outcome_passed']} | "
            f"{item['self_strict_passed']}/{item['exact_strict_passed']} | "
            f"{'同' if item['outcome_vectors_identical'] else '异'} / "
            f"{'同' if item['strict_vectors_identical'] else '异'} | "
            f"{item['generated_skill_count']} | {jaccard_text} | {ratio_text} | "
            f"{item['generated_verifier_marker_hits']}/{item['oracle_verifier_marker_hits']} | "
            f"{item['exact_full_skill_use']}/{item['exact_skill_use_audited']} | "
            f"{no_skill['outcome_passed']}/{no_skill['observed']} |"
        )
    lines += [
        "",
        "Qwen/E2 是当前最清晰的 content–behavior 解耦案例：generated skills 明显更长、更具体且吸收大量 verifier 反馈，curated 则是更短的通用 scaffold，但 10 个 T5/T6 的 outcome 和 strict 逐题向量均完全一致。这说明当前 self-vs-exact treatment 没有识别出内容增益；只有 no-skill 到齐后，才能判断是两类 skill 都有效，还是题面本身已经足够。",
        "",
        "### T1–T3 做得好，是否真的预测 T5/T6？",
        "",
        "下面只做 family-level 描述性关联：把每个 family 的 T1–T3 最终 strict 通过数，与同一模型 self-generated 条件下的 T5/T6 outcome 对齐。它不能证明 generated skill 造成了后续成功，因为 family 难度会同时影响 acquisition 与 transfer；最终仍以同题 no-skill 对照为准。",
        "",
        "| 模型 | T1–T3 最终 strict | Families | T5 outcome | T6 outcome | T5+T6 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in data["learning_transfer"]["summaries"]:
        for group in item["by_terminal_strict_passes"]:
            if not group["families"]:
                continue
            lines.append(
                f"| {item['model']} | {group['terminal_strict_passes']}/3 | "
                f"{group['families']} | {group['t5_passed']}/{group['families']} | "
                f"{group['t6_passed']}/{group['families']} | "
                f"{group['combined_passed']}/{group['combined_total']} |"
            )
    lines += [
        "",
        "| 模型 | r(T1–T3 pass, T5) | r(T1–T3 pass, T6) | r(T1–T3 pass, combined) | r(尝试数, T6) | r(修复成功数, T6) | r(Generated/Oracle Jaccard, T6) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in data["learning_transfer"]["summaries"]:
        correlations = item["correlations"]
        rendered = {
            key: "—" if value is None else f"{value:+.3f}"
            for key, value in correlations.items()
        }
        lines.append(
            f"| {item['model']} | {rendered['terminal_passes_vs_t5']} | "
            f"{rendered['terminal_passes_vs_t6']} | "
            f"{rendered['terminal_passes_vs_combined']} | "
            f"{rendered['learning_attempts_vs_t6']} | "
            f"{rendered['repairs_vs_t6']} | "
            f"{rendered['generated_oracle_jaccard_vs_t6']} |"
        )
    lines += [
        "",
        "Generated skill 的受控概念词面覆盖与 self-generated outcome 也不是单调关系：",
        "",
        "| 模型 | Generated 概念覆盖 | Tasks | Outcome |",
        "|---|---|---:|---:|",
    ]
    for item in data["learning_transfer"]["summaries"]:
        for group in item["by_generated_concept_coverage"]:
            if not group["tasks"]:
                continue
            lines.append(
                f"| {item['model']} | {group['generated_coverage']} | "
                f"{group['tasks']} | {group['outcome_passed']}/{group['tasks']} "
                f"({pct(group['outcome_rate'])}) |"
            )
    lines += [
        "",
        "当前相关性整体偏弱，Generated/Oracle 文本 Jaccard 对 T6 近乎没有预测力；而 generated 概念全覆盖组的原始通过率反而更低。最合理的解释不是 skill 有害，而是困难题会诱发更长、更具体、概念更全的总结，同时仍更难执行。这说明不能用 skill 长度、词面覆盖或与 oracle 相似度替代同题四条件实验。",
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
        "这是一项 measurement-validity 筛查，而不是效果估计。只有高级要求在 T1–T3 有历史证据的任务，后续成功才有可能归因于 skill transfer；仍必须再由同任务 no-skill 对照证明增量。若高级要求只在当前 T5/T6 instruction 出现，模型做对最多说明现场执行能力，不能证明此前形成的 skill 有帮助。当前 60/60 题均有受控概念命中，但 lexical screen 仍不能代替语义审查。",
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
        "按 measurement-validity 分层的 matched outcome 效应（只显示当前已有配对）：",
        "",
        "| 模型 | 有效性分层 | Treatment − Reference | n | Treatment | Reference | Δ | Rescue / Harm | 四条件完整 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in data["validity_stratified_effects"]:
        if not item["n"]:
            continue
        lines.append(
            f"| {item['model']} | "
            f"{MEASUREMENT_VALIDITY_ZH.get(item['validity_category'], item['validity_category'])} | "
            f"{CONDITION_ZH[item['treatment']]} − {CONDITION_ZH[item['reference']]} | "
            f"{item['n']} | {item['treatment_pass']}/{item['n']} | "
            f"{item['reference_pass']}/{item['n']} | {pct(item['delta'])} | "
            f"{item['rescued']} / {item['harmed']} | "
            f"{item['complete_four_conditions']}/{item['task_count']} |"
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
            f"{data['oracle_scope']['concept_visibility']['concept_dictionary_size']} 项受控词表覆盖 {data['oracle_scope']['concept_visibility']['tasks_with_controlled_concepts']}/60 题，"
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
            outcome_failures = ", ".join(
                item.get("name", "") for item in obs["failed_outcome_tests"]
            ) or "无"
            process_failures = ", ".join(
                item.get("name", "") for item in obs["failed_process_tests"]
            ) or "无"
            condition = CONDITION_ZH.get(str(obs.get("condition")), str(obs.get("condition")))
            lines.append(
                f"- {obs['model']} / {condition}：strict={obs['strict']}，"
                f"outcome={obs['outcome']}，process={obs['process']}；"
                f"outcome failures `{outcome_failures}`；process failures `{process_failures}`。"
            )
        if case.get("reproduction"):
            lines += [
                "",
                "独立复算证据：",
                "",
                "```json",
                json.dumps(case["reproduction"], ensure_ascii=False, indent=2),
                "```",
            ]
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
<section class="panel"><h2>失败归因总览</h2><p class="small">Outcome 假阴性要求该模型产物经独立复算后核心语义正确；“混合”保留模型真实缺口；“无效题”表示不可满足或欠规定。形态敏感仍只是筛查标签。</p><div class="tablebox"><table><thead><tr><th>Env/Tier</th><th>模型</th><th>覆盖/Strict</th><th>功能 gap</th><th>Outcome 假阴性</th><th>混合</th><th>无效题</th><th>Process 假阴性</th><th>实质过程 gap</th><th>形态敏感</th><th>未决过程</th></tr></thead><tbody id="attributionRows"></tbody></table></div></section>
<section class="panel"><h2>T1–T3 学习与 Skill 来源审计</h2><div class="grid two" id="learningCards"></div><div class="filters" style="margin-top:16px"><select id="skillModel"></select><select id="skillEnv"></select><input id="skillSearch" placeholder="搜索 family / skill"></div><div class="tablebox"><table><thead><tr><th>Family</th><th>学习结果</th><th>生成 skill</th><th>Best Jaccard</th><th>Oracle evidence recall</th><th>Verifier markers</th></tr></thead><tbody id="skillRows"></tbody></table></div><p class="small">Evidence recall 仅是词面覆盖率，不代表逻辑可推导性。点击 family 查看 T1–T3 证据摘录、generated skill 与 curated oracle 全文。</p></section>
<section class="panel"><h2>Skill 内容差异，是否真的改变同题行为？</h2><p>逐 model×Env 对齐 Self-generated 与 Exact oracle 的 T5/T6。向量相同要求逐题结果完全一致，不只是总分相同。</p><div class="tablebox"><table><thead><tr><th>模型 / Env</th><th>配对</th><th>Outcome S/E</th><th>Strict S/E</th><th>向量 O/S</th><th>Generated skills</th><th>Jaccard</th><th>长度 G/O</th><th>Verifier markers G/O</th><th>Exact 全读</th><th>No-skill O</th></tr></thead><tbody id="matchedSkillRows"></tbody></table></div><p class="small">内容距离只是描述性证据；同题行为是否变化看 matched vectors。No-skill 未齐时，不能把 self/exact 相同解释为“不需要 skill”。</p></section>
<section class="panel"><h2>T1–T3 表现能预测 T5/T6 吗？</h2><p>这是 family-level 描述性关联，不是 skill 的因果效果：family 难度会同时影响 acquisition 与 transfer，最终仍要看同题 no-skill。</p><div class="grid two" id="learningTransferCards"></div><h3 style="margin-top:16px">按 T1–T3 最终 strict 通过数分层</h3><div class="tablebox"><table><thead><tr><th>模型</th><th>T1–T3 strict</th><th>Families</th><th>T5</th><th>T6</th><th>T5+T6</th></tr></thead><tbody id="learningTransferRows"></tbody></table></div><h3 style="margin-top:16px">Generated 概念覆盖与 Outcome</h3><div class="tablebox"><table><thead><tr><th>模型</th><th>概念覆盖</th><th>Tasks</th><th>Outcome</th></tr></thead><tbody id="learningCoverageRows"></tbody></table></div><p class="small">当前文本相似度、概念覆盖和学习通过数都只能作诊断，不能替代四条件 matched control。困难题往往既诱发更详细的 skill，也更难执行，原始相关性会被反向混杂。</p></section>
<section class="panel"><h2>T5/T6 概念可推导性与 Annotation Prior</h2><p>把每个高级概念分别放回 T1–T3 可见证据、generated skill、curated oracle 和仅题目作者可见的 gap metadata 中检查。重点看“可见但没总结”“oracle 补入未见概念”“两边都缺”三类。</p><div class="grid two" id="derivabilityCards"></div><div class="filters" style="margin-top:16px"><select id="derivabilityModel"><option value="all">全部模型</option><option value="qwen3.7-max">qwen3.7-max</option><option value="sig-fable">sig-fable</option></select><select id="derivabilityCategory"><option value="all">全部非平凡分类</option></select><input id="derivabilitySearch" placeholder="搜索 task / concept"></div><div class="tablebox"><table><thead><tr><th>Task / Family</th><th>模型</th><th>高级概念</th><th>分类</th><th>T1–T3</th><th>Generated</th><th>Oracle</th><th>Author gap meta</th></tr></thead><tbody id="derivabilityRows"></tbody></table></div><p class="small">Author gap meta 是 benchmark 作者的设计注释，不会注入模型。此处仍是受控词表筛查，不把词面缺失自动等同于逻辑不可推导。</p></section>
<section class="panel"><h2>哪些 T5/T6 真能测 Skill Evolution？</h2><p>先判断高级要求是否在 T1–T3 留下历史证据，再看匹配 no-skill 对照。若要求只在当前 T5/T6 题面出现，模型现场做对不能证明此前形成的 skill 有帮助。当前 60/60 题均有受控概念命中，但 lexical screen 仍不能代替语义审查。</p><div class="grid two" id="validityCards"></div><div class="tablebox"><table><thead><tr><th>模型/Env</th><th>可进入历史 skill 因果检验</th><th>仅当前题面</th><th>历史+现场混合</th><th>缺学习证据</th><th>词表未覆盖</th></tr></thead><tbody id="validityRows"></tbody></table></div><h3 style="margin-top:16px">按测量有效性分层的 Matched Outcome 效应</h3><div class="tablebox"><table><thead><tr><th>模型/分层</th><th>Treatment − Reference</th><th>n</th><th>Treatment</th><th>Reference</th><th>Δ</th><th>救回/损害</th><th>四条件完整</th></tr></thead><tbody id="validityEffectRows"></tbody></table></div><p class="small">“可进入因果检验”不等于已经证明 skill 有用；仍需同模型同任务的 Self / Exact / Curated-all / No-skill 四条件结果。</p></section>
<section class="panel"><h2>Curated Oracle 是否真的足以覆盖任务？</h2><p>仓库中的 curated skill 多数是基础工作流，不是 T5/T6 的 solution manual。Oracle 仍失败必须同时考虑 skill scope gap，不能直接判题目坏。</p><div id="scopeVisibility" class="grid cards"></div><div id="scopeCounts"></div><div class="tablebox"><table><thead><tr><th>Task</th><th>Oracle skills</th><th>风险</th><th>缺失概念</th><th>Author gap 命中</th><th>Verifier-only</th><th>Scope</th></tr></thead><tbody id="scopeRows"></tbody></table></div><h3 style="margin-top:16px">Oracle 结果按 scope risk 分层</h3><div id="scopeOutcomes" class="small"></div><p class="small">这是受控概念的启发式筛查。高风险项用于人工复核，不把词面缺失自动等同于语义缺失。</p></section>
<section class="panel"><h2>逐题匹配对照</h2><div class="filters"><select id="taskModel"></select><select id="taskEnv"></select><select id="taskTier"><option value="all">T4–T6</option><option value="4">T4</option><option value="5">T5</option><option value="6">T6</option></select><input id="taskSearch" placeholder="搜索 task / skill"></div><div class="tablebox"><table><thead><tr><th>Task</th><th>模型</th><th>Self-generated</th><th>Exact oracle</th><th>Curated all</th><th>No skill</th><th>历史 Skill 测量有效性</th><th>四条件判定</th></tr></thead><tbody id="taskRows"></tbody></table></div></section>
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
attributionRows.innerHTML=D.failure_attribution.summaries.map(x=>{{let c=x.cause_counts;return `<tr><td><b>${{x.environment_id}} / T${{x.tier}}</b></td><td>${{x.model}}</td><td>${{x.observed}}/5 · ${{x.strict_passed}}/${{x.observed}}</td><td>${{c.functional_gap||0}}</td><td>${{c.verified_benchmark_false_negative||0}}</td><td>${{c.mixed_benchmark_and_model_gap||0}}</td><td>${{c.invalid_or_underdetermined_task||0}}</td><td>${{c.verified_verifier_false_negative||0}}</td><td>${{c.substantive_process_gap||0}}</td><td>${{c.shape_sensitive_process_only||0}}</td><td>${{c.unresolved_process_only||0}}</td></tr>`}}).join('');
learningCards.innerHTML=Object.entries(D.learning.by_model).map(([m,x])=>`<div class="case"><h3>${{m}}</h3><p><b>${{x.learning_tasks}}</b> 个 T1–T3 · <b>${{x.learning_attempts}}</b> 次尝试 · 最终通过 ${{x.terminal_strict_passes}} · 修复成功 ${{x.repaired_to_pass}}</p><p class="small">same-session 异常 ${{x.same_session_failures}} · active skills/families ${{x.active_skills}}/${{x.families}} · 多 skill families ${{x.families_with_multiple_skills}} · 含 verifier 术语 skills ${{x.skills_with_verifier_markers}}</p></div>`).join('');
matchedSkillRows.innerHTML=D.matched_skill_content.map(x=>{{let n=x.controls.no_skill;let ratio=x.generated_to_curated_char_ratio==null?'—':x.generated_to_curated_char_ratio.toFixed(2)+'×';let jac=x.median_best_word_jaccard==null?'—':x.median_best_word_jaccard.toFixed(3);return `<tr><td><b>${{x.model}}</b><br><span class="small">${{x.environment_id}}</span></td><td>${{x.matched_tasks}}/10</td><td>${{x.self_outcome_passed}}/${{x.exact_outcome_passed}}</td><td>${{x.self_strict_passed}}/${{x.exact_strict_passed}}</td><td><span class="metric ${{x.outcome_vectors_identical?'pass':'fail'}}">${{x.outcome_vectors_identical?'同':'异'}}</span> <span class="metric ${{x.strict_vectors_identical?'pass':'fail'}}">${{x.strict_vectors_identical?'同':'异'}}</span></td><td>${{x.generated_skill_count}}</td><td>${{jac}}</td><td>${{ratio}}</td><td>${{x.generated_verifier_marker_hits}}/${{x.oracle_verifier_marker_hits}}</td><td>${{x.exact_full_skill_use}}/${{x.exact_skill_use_audited}}</td><td>${{n.outcome_passed}}/${{n.observed}}</td></tr>`}}).join('')||'<tr><td colspan="11" class="small">等待 self/exact matched slices</td></tr>';
const fmtCorr=v=>v==null?'—':(v>=0?'+':'')+v.toFixed(3);
learningTransferCards.innerHTML=D.learning_transfer.summaries.map(x=>{{let c=x.correlations;return `<div class="case"><h3>${{x.model}}</h3><p><b>${{x.families}}</b> 个完整 family</p><p class="small">r(T1–T3 pass → T5) ${{fmtCorr(c.terminal_passes_vs_t5)}} · r(pass → T6) ${{fmtCorr(c.terminal_passes_vs_t6)}} · r(pass → combined) ${{fmtCorr(c.terminal_passes_vs_combined)}}<br>r(attempts → T6) ${{fmtCorr(c.learning_attempts_vs_t6)}} · r(repairs → T6) ${{fmtCorr(c.repairs_vs_t6)}} · r(Jaccard → T6) ${{fmtCorr(c.generated_oracle_jaccard_vs_t6)}}</p></div>`}}).join('');
learningTransferRows.innerHTML=D.learning_transfer.summaries.flatMap(x=>x.by_terminal_strict_passes.filter(g=>g.families).map(g=>`<tr><td><b>${{x.model}}</b></td><td>${{g.terminal_strict_passes}}/3</td><td>${{g.families}}</td><td>${{g.t5_passed}}/${{g.families}}</td><td>${{g.t6_passed}}/${{g.families}}</td><td>${{g.combined_passed}}/${{g.combined_total}}</td></tr>`)).join('');
learningCoverageRows.innerHTML=D.learning_transfer.summaries.flatMap(x=>x.by_generated_concept_coverage.filter(g=>g.tasks).map(g=>`<tr><td><b>${{x.model}}</b></td><td>${{g.generated_coverage}}</td><td>${{g.tasks}}</td><td>${{g.outcome_passed}}/${{g.tasks}} (${{(100*g.outcome_rate).toFixed(1)}}%)</td></tr>`)).join('');
options(skillModel,['qwen3.7-max','sig-fable'],null,true);options(skillEnv,['E1','E2','E3','E4','E5','E6'],null,true);
function renderSkills(){{let q=skillSearch.value.toLowerCase(),rows=D.learning.families.filter(x=>(skillModel.value==='all'||x.model===skillModel.value)&&(skillEnv.value==='all'||x.environment_id===skillEnv.value)&&JSON.stringify(x).toLowerCase().includes(q));skillRows.innerHTML=rows.map(x=>`<tr class="click" data-key="${{x.model}}|${{x.family_id}}"><td><b>${{x.family_id}}</b><br><span class="small">${{x.model}} · ${{x.expected_oracle_slug}}</span></td><td>${{x.terminal_strict_passes}}/${{x.learning_task_count}} 通过 · ${{x.learning_attempts}} attempts</td><td>${{x.generated_skill_count}} · ${{x.generated_slugs.join(', ')}}</td><td>${{x.best_word_jaccard.toFixed(3)}}</td><td>${{x.oracle_token_recall_from_learning_evidence==null?'—':(100*x.oracle_token_recall_from_learning_evidence).toFixed(1)+'%'}}</td><td>${{x.generated_verifier_marker_hits}}</td></tr>`).join('');skillRows.querySelectorAll('tr').forEach(tr=>tr.onclick=()=>showFamily(...tr.dataset.key.split('|')))}};[skillModel,skillEnv].forEach(x=>x.onchange=renderSkills);skillSearch.oninput=renderSkills;renderSkills();
function showFamily(model,id){{let x=D.learning.families.find(x=>x.model===model&&x.family_id===id);drawerBody.innerHTML=`<h2>${{x.family_id}} · ${{model}}</h2><p>学习任务 ${{x.learning_task_count}}/3 · 最终通过 ${{x.terminal_strict_passes}} · attempts ${{x.learning_attempts}} · generated skills ${{x.generated_skill_count}}</p><p>Best Jaccard ${{x.best_word_jaccard.toFixed(3)}} · Oracle evidence recall ${{x.oracle_token_recall_from_learning_evidence==null?'—':(100*x.oracle_token_recall_from_learning_evidence).toFixed(1)+'%'}} · verifier markers ${{x.generated_verifier_marker_hits}}</p><details open><summary>Generated skill 全文</summary><pre>${{esc(x.generated_text)}}</pre></details><details><summary>Curated oracle 全文</summary><pre>${{esc(x.curated_text)}}</pre></details><details><summary>T1–T3 可见证据摘录</summary><pre>${{esc(x.learning_evidence_excerpt)}}</pre></details>`;drawer.classList.add('open')}}
derivabilityCards.innerHTML=D.derivability.summaries.map(x=>{{let c=x.category_counts;return `<div class="case"><h3>${{x.model}}</h3><p><b>${{x.concept_instances}}</b> 个 task-concept 实例</p><p class="small">可见且 Generated 捕获 ${{c.captured_from_visible_evidence||0}} · 可见、Oracle 捕获 ${{c.oracle_captures_visible_generated_misses||0}} · 可见、两种 skill 都漏 ${{c.visible_missing_from_both_skills||0}} · Oracle 独有未见补入 ${{c.oracle_adds_unseen_concept||0}} · 两种 skill 均补入 ${{c.both_skills_add_unseen_concept||0}} · Generated 独有补入 ${{c.model_adds_beyond_visible_evidence||0}} · 三处都缺 ${{c.missing_from_both_learning_and_oracle||0}} · Author gap meta 命中 ${{x.author_gap_metadata_hits}}，其中 T1–T3 未见 ${{x.author_gap_unseen_in_t1_t3}}</p></div>`}}).join('');
options(derivabilityCategory,Object.keys(derivabilityZh).filter(x=>x!=='captured_from_visible_evidence'),derivabilityZh,true);
function renderDerivability(){{let q=derivabilitySearch.value.toLowerCase();let rows=D.derivability.records.filter(x=>x.category!=='captured_from_visible_evidence'&&(derivabilityModel.value==='all'||x.model===derivabilityModel.value)&&(derivabilityCategory.value==='all'||x.category===derivabilityCategory.value)&&JSON.stringify(x).toLowerCase().includes(q));derivabilityRows.innerHTML=rows.map(x=>`<tr><td><b>${{x.task_id}}</b><br><span class="small">${{x.family_id}} · T${{x.tier}}</span></td><td>${{x.model}}</td><td>${{esc(x.concept)}}</td><td>${{esc(derivabilityZh[x.category])}}</td><td>${{x.in_t1_t3_evidence?'✓':'✗'}}</td><td>${{x.in_generated_skill?'✓':'✗'}}</td><td>${{x.in_curated_oracle?'✓':'✗'}}</td><td>${{x.in_author_gap_metadata?'✓':'✗'}}</td></tr>`).join('')||'<tr><td colspan="8" class="small">当前过滤条件无记录</td></tr>'}};[derivabilityModel,derivabilityCategory].forEach(x=>x.onchange=renderDerivability);derivabilitySearch.oninput=renderDerivability;renderDerivability();
validityCards.innerHTML=D.measurement_validity.summaries.map(x=>{{let c=x.category_counts;return `<div class="case"><h3>${{x.model}}</h3><p><b>${{x.eligible_for_causal_skill_claim}}/${{x.controlled_task_count}}</b> 个受控词表覆盖任务可进入历史 skill 因果检验</p><p class="small">全部 T5/T6 ${{x.task_count}} · 仅当前题面 ${{c.on_task_only||0}} · 历史+现场混合 ${{c.mixed_history_and_on_task||0}} · 缺学习证据 ${{c.missing_learning_evidence||0}} · 词表未覆盖 ${{c.unclassified_no_controlled_concept||0}} · Oracle 全覆盖概念 ${{x.oracle_all_concepts}}/${{x.controlled_task_count}} · Generated 全覆盖概念 ${{x.generated_all_concepts}}/${{x.controlled_task_count}}</p></div>`}}).join('');validityRows.innerHTML=D.measurement_validity.by_environment.map(x=>{{let c=x.category_counts;return `<tr><td><b>${{x.model}}</b> / ${{x.environment_id}}</td><td>${{x.eligible_for_causal_skill_claim}}/${{x.controlled_task_count}}</td><td>${{c.on_task_only||0}}</td><td>${{c.mixed_history_and_on_task||0}}</td><td>${{c.missing_learning_evidence||0}}</td><td>${{c.unclassified_no_controlled_concept||0}}</td></tr>`}}).join('');
validityEffectRows.innerHTML=D.validity_stratified_effects.filter(x=>x.n).map(x=>`<tr><td><b>${{x.model}}</b><br><span class="small">${{esc(validityZh[x.validity_category]||x.validity_category)}}</span></td><td>${{zh[x.treatment]}} − ${{zh[x.reference]}}</td><td>${{x.n}}</td><td>${{x.treatment_pass}}/${{x.n}}</td><td>${{x.reference_pass}}/${{x.n}}</td><td>${{x.delta==null?'—':(100*x.delta).toFixed(1)+'pp'}}</td><td>${{x.rescued}} / ${{x.harmed}}</td><td>${{x.complete_four_conditions}}/${{x.task_count}}</td></tr>`).join('')||'<tr><td colspan="8" class="small">等待 matched controls</td></tr>';
let cv=D.oracle_scope.concept_visibility;scopeVisibility.innerHTML=[['概念词典',cv.concept_dictionary_size],['受控概念实例',cv.concept_instances],['Instruction 明示',cv.instruction_explicit_instances],['Verifier-only',cv.verifier_only_instances],['Author gap meta 命中',cv.author_gap_metadata_instances],['涉及任务',cv.tasks_with_controlled_concepts+'/60']].map(x=>`<div class="card"><span class="label">${{x[0]}}</span><b>${{x[1]}}</b></div>`).join('');
scopeCounts.innerHTML=Object.entries(D.oracle_scope.counts).map(([k,v])=>`<span class="metric ${{k==='high'?'fail':k==='medium'?'proc':'pass'}}">${{k}}: ${{v}}</span>`).join(' ');scopeRows.innerHTML=D.oracle_scope.rows.filter(x=>x.scope_risk!=='low'||x.verifier_only_concepts.length).map(x=>`<tr><td><b>${{x.task_id}}</b><br><span class="small">${{esc(x.task_slug)}}</span></td><td>${{esc(x.oracle_skill_ids.join(', '))}}</td><td><span class="metric ${{x.scope_risk==='high'?'fail':'proc'}}">${{x.scope_risk}}</span></td><td>${{esc(x.missing_concepts.join(', ')||'—')}}</td><td>${{esc(x.task_concepts_in_author_gaps.join(', ')||'—')}}</td><td>${{esc(x.verifier_only_concepts.join(', ')||'—')}}</td><td>${{esc(x.scope_lines.join('; ')||'—')}}</td></tr>`).join('');
scopeOutcomes.innerHTML=D.scope_condition_outcomes.filter(x=>x.n).map(x=>`<div>${{x.model}} · ${{x.scope_risk}} · n=${{x.n}} · strict ${{x.oracle_strict_passes}}/${{x.n}} · outcome ${{x.oracle_outcome_passes}}/${{x.n}} · process ${{x.oracle_process_passes}}/${{x.n}}</div>`).join('')||'等待 exact-oracle 结果';
function renderTasks(){{let q=taskSearch.value.toLowerCase();let rows=D.comparisons.filter(x=>(taskModel.value==='all'||x.model===taskModel.value)&&(taskEnv.value==='all'||x.environment_id===taskEnv.value)&&(taskTier.value==='all'||x.tier==taskTier.value)&&JSON.stringify(x).toLowerCase().includes(q));taskRows.innerHTML=rows.map(x=>{{let v=D.measurement_validity.records.find(v=>v.model===x.model&&v.task_id===x.task_id);return `<tr class="click" data-key="${{x.model}}|${{x.task_id}}"><td><b>${{x.task_id}}</b><br><span class="small">${{esc(x.task_slug)}} · ${{esc(x.primary_skill)}}</span></td><td>${{x.model}}</td><td>${{status(x.conditions.self_generated)}}</td><td>${{status(x.conditions.exact_oracle)}}</td><td>${{status(x.conditions.curated_all)}}</td><td>${{status(x.conditions.no_skill)}}</td><td>${{v?`<b>${{esc(validityZh[v.category]||v.category)}}</b><br><span class="small">${{v.eligible_for_causal_skill_claim?'可进入因果检验':'不能归因于历史 skill'}} · G=${{v.generated_coverage}} · O=${{v.oracle_coverage}}</span>`:'<span class="small">T4 不在本筛查范围</span>'}}</td><td><b>${{esc(x.causal.label)}}</b><br><span class="small">${{esc(x.causal.pattern||verdict[x.verdict])}}</span></td></tr>`}}).join('');taskRows.querySelectorAll('tr').forEach(tr=>tr.onclick=()=>showTask(...tr.dataset.key.split('|')))}};[taskModel,taskEnv,taskTier].forEach(x=>x.onchange=renderTasks);taskSearch.oninput=renderTasks;renderTasks();
function showTask(model,id){{let x=D.comparisons.find(x=>x.model===model&&x.task_id===id);let v=D.measurement_validity.records.find(v=>v.model===model&&v.task_id===id);let blocks=Object.entries(x.conditions).map(([name,c])=>`<h3>${{zh[name]}}</h3>${{c?`<p>${{status(c)}} score=${{c.score??'—'}} · job=${{esc(c.job_id)}}</p><p class="small">实际读取 skills: ${{esc(c.skills_actually_used.join(', ')||'none')}}<br>Oracle 内容证明: ${{esc(Object.entries(c.oracle_content_verification||{{}}).map(([k,v])=>k+': '+v).join(', ')||'—')}}<br>record: ${{esc(c.record_path)}}<br>trajectory: ${{esc(c.trajectory_path)}}</p><details><summary>失败测试 (${{c.failed_tests.length}})</summary><pre>${{esc(JSON.stringify(c.failed_tests,null,2))}}</pre></details>`:'<p class="small">尚无结果</p>'}}`).join('');let validityBlock=v?`<div class="case"><h3>历史 Skill 测量有效性：${{esc(validityZh[v.category]||v.category)}}</h3><p>${{v.eligible_for_causal_skill_claim?'该题可进入历史 skill 的四条件因果检验。':'该题当前不能把成功归因于 T1–T3 形成的历史 skill。'}}</p><p class="small">受控概念：${{esc(v.controlled_concepts.join(', ')||'—')}}<br>T1–T3 历史命中：${{v.history_visible_count}} · 当前题面明示：${{v.instruction_explicit_count}} · generated 覆盖：${{v.generated_coverage}} · oracle 覆盖：${{v.oracle_coverage}}</p></div>`:'';drawerBody.innerHTML=`<h2>${{x.task_id}}</h2><p>${{esc(x.task_slug)}} · T${{x.tier}} · ${{x.environment_id}}</p><div class="conclusion ${{x.causal.complete?'good':'pending'}}"><h3>${{esc(x.causal.label)}} · ${{esc(x.causal.pattern||'')}}</h3>${{esc(x.causal.explanation)}}</div>${{validityBlock}}<p><b>需要的 skills</b><br>${{esc(x.required_skills.join(', ')||x.primary_skill)}}</p>${{blocks}}`;drawer.classList.add('open')}}
let a=D.verifier_audit.summary;audit.innerHTML=`<div class="card"><span class="label">过程 / 功能 checks</span><b>${{a.process_checks_total}} / ${{a.outcome_checks_total}}</b></div><p><b>${{a.tasks_with_literal_or_regex_process_checks}}/90</b> 含源码字面量或正则检查；<b>${{a.tasks_with_effective_process_weight_50_percent}}/90</b> 的过程权重为 50%。</p><p>形态敏感度：${{Object.entries(a.process_shape_sensitivity).map(([k,v])=>`${{k}}=${{v}}`).join(' · ')}}</p><h3>Process-only 分层</h3>${{D.verifier_shape_outcomes.filter(x=>x.n).map(x=>`<div class="small">${{zh[x.condition]}} · ${{x.shape_risk}} · process-only ${{x.process_only_failures}}/${{x.n}} · outcome ${{x.outcome_passes}}/${{x.n}} · process ${{x.process_passes}}/${{x.n}}</div>`).join('')}}`;
skills.innerHTML=Object.entries(D.skills.by_model).map(([m,x])=>`<div class="case"><h3>${{m}}</h3><p>skill 对数 <b>${{x.n}}</b> · 改名 ${{x.renamed}} · 完全相同 ${{x.exact_equal}}</p><div class="small">中位 word Jaccard ${{x.median_word_jaccard?.toFixed(3)??'—'}} · 长度比 ${{x.median_length_ratio?.toFixed(2)??'—'}}</div></div>`).join('')+'<p class="small">词面相似度低只说明表达和覆盖范围不同，不能单独证明 skill 质量差；最终要结合 matched oracle rescue。</p>';
cases.innerHTML=D.cases.map((x,i)=>`<article class="case"><span class="kind">${{x.kind}}</span><h3>${{x.task_id}} · ${{x.title}}</h3><p>${{x.interpretation}}</p>${{x.observations.map(o=>`<p><b>${{o.model}} / ${{zh[o.condition]||o.condition}}</b> · strict=${{o.strict}} outcome=${{o.outcome}} process=${{o.process}}<br><span class="small">Outcome failures: ${{o.failed_outcome_tests.map(t=>t.name).join(', ')||'无'}}<br>Process failures: ${{o.failed_process_tests.map(t=>t.name).join(', ')||'无'}}<br>Agent tokens: input=${{o.agent_result.n_input_tokens??'—'}} output=${{o.agent_result.n_output_tokens??'—'}} · tools: ${{Object.entries(o.tool_counts).map(([k,v])=>k+'='+v).join(', ')||'none'}} · explicit mutation calls=${{o.mutation_call_count}}</span></p>${{o.files.map(f=>`<details><summary>${{o.model}} / ${{zh[o.condition]||o.condition}} / ${{f.name}}</summary><div class="small">${{esc(f.path)}}</div><pre>${{esc(f.content)}}</pre></details>`).join('')}}${{o.bash_commands.length?`<details><summary>${{o.model}} / ${{zh[o.condition]||o.condition}} / bash commands (${{o.bash_commands.length}})</summary><div class="small">${{esc(o.trajectory_path)}}</div><pre>${{esc(o.bash_commands.join(String.fromCharCode(10,10)))}}</pre></details>`:''}}${{o.final_edits.length?`<details><summary>${{o.model}} / ${{zh[o.condition]||o.condition}} / trajectory 中的最终 edits (${{o.final_edits.length}})</summary><div class="small">${{esc(o.trajectory_path)}}</div><pre>${{esc(o.final_edits.map(e=>`### ${{e.file_path}}\n${{e.new}}`).join(String.fromCharCode(10,10)))}}</pre></details>`:''}}`).join('')}}${{Object.keys(x.reproduction||{{}}).length?`<details open><summary>独立复算证据</summary><pre>${{esc(JSON.stringify(x.reproduction,null,2))}}</pre></details>`:''}}${{x.task_source_files.map(f=>`<details><summary>任务资产 / ${{f.name}}</summary><div class="small">${{esc(f.path)}}</div><pre>${{esc(f.content)}}</pre></details>`).join('')}}<details><summary>任务正文</summary><div class="small">${{esc(x.instruction_path)}}</div><pre>${{esc(x.instruction)}}</pre></details><details><summary>Outcome verifier 源码</summary><div class="small">${{esc(x.outcome_verifier_path)}}</div><pre>${{esc(x.outcome_verifier)}}</pre></details><details><summary>Process verifier 源码</summary><div class="small">${{esc(x.process_verifier_path)}}</div><pre>${{esc(x.process_verifier)}}</pre></details><details><summary>官方 reference solution</summary><div class="small">${{esc(x.reference_solution_path)}}</div><pre>${{esc(x.reference_solution)}}</pre></details></article>`).join('');
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
