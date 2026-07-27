#!/usr/bin/env python3
"""Build the leadership-friendly SkillEvolBench v1.1 quality report.

The report deliberately keeps three evidence layers separate:

1. v1 model behavior: what Qwen, Fable, and Opus actually did.
2. benchmark audit: which task or verifier defects were found and repaired.
3. v1.1 regression: whether the repaired benchmark remains solvable and how
   Opus behaves with and without its generated skill library.

An AP ``Succeeded`` state is never treated as a task pass.  The optional
regression payload must already contain verifier-backed task records.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODEL_ORDER = ["qwen3.7-max", "sig-fable", "opus-4.8"]
MODEL_ZH = {
    "qwen3.7-max": "Qwen 3.7 Max",
    "sig-fable": "S1 Fable",
    "opus-4.8": "Opus 4.8",
}
METRICS = ("strict", "outcome", "process")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_optional_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return load_json(path)


def heatmap_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {
        (model, f"E{environment}", tier)
        for model in MODEL_ORDER
        for environment in range(1, 7)
        for tier in range(1, 7)
    }
    keyed = {
        (str(row["model"]), str(row["environment_id"]), int(row["tier"])): row
        for row in records
    }
    missing = sorted(expected - set(keyed))
    if missing:
        raise ValueError(f"heatmap is missing {len(missing)} cells: {missing[:3]}")

    totals: dict[str, Any] = {}
    for model in MODEL_ORDER:
        selected = [
            keyed[(model, f"E{environment}", tier)]
            for environment in range(1, 7)
            for tier in range(1, 7)
        ]
        totals[model] = {
            metric: sum(int(row.get(metric) or 0) for row in selected)
            for metric in METRICS
        }
        totals[model]["observed"] = sum(
            int(row.get("observed") or 0) for row in selected
        )
    return {"records": list(keyed.values()), "totals": totals}


def behavior_takeaways(behavior: dict[str, Any]) -> list[dict[str, str]]:
    summaries = behavior["model_summaries"]
    fable = summaries["sig-fable"]
    opus = summaries["opus-4.8"]
    return [
        {
            "title": "学习阶段几乎打平，但路径不同",
            "body": (
                f"Fable 在 T1–T3 终态通过 {fable['terminal_passes']}/90，"
                f"Opus 为 {opus['terminal_passes']}/90。Opus 首次通过更少"
                f"（{opus['initial_passes']} vs {fable['initial_passes']}），但通过"
                f" same-session retry 修复更多失败（{opus['repaired_to_pass']} vs "
                f"{fable['repaired_to_pass']}）。"
            ),
        },
        {
            "title": "Fable 更偏长篇、持续增补；Opus 更偏短篇、分化专门技能",
            "body": (
                f"Fable 生成 {fable['total_skill_versions']} 个 skill 版本，"
                f"中位长度 {fable['median_skill_chars']:.0f} 字符；Opus 为 "
                f"{opus['total_skill_versions']} 个版本、{opus['median_skill_chars']:.0f} "
                "字符。Opus 的 active skill 数略多，说明它更常拆成多个专门条目；"
                "Fable 更常在同一条目上反复扩写。"
            ),
        },
        {
            "title": "旧版 reflection gate 对 Opus 存在非能力性惩罚",
            "body": (
                f"Opus 有 {opus['reflection_status_counts'].get('rejected', 0)} 次、"
                f"Fable 有 {fable['reflection_status_counts'].get('rejected', 0)} 次"
                " reflection 被拒；逐条复核均属于 frontmatter parser 不兼容。"
                "v1.1 已统一到运行时 YAML parser，因此旧版差异不能解释成"
                "“Opus 不会写 skill”。"
            ),
        },
        {
            "title": "Fable 在 T4/T5 更稳，Opus 在 T6 略占优势",
            "body": (
                "旧版 strict：Fable T4/T5/T6 为 16/15/8，Opus 为 12/12/10。"
                "这支持“Fable 更擅长按程序稳定执行，Opus 更擅长高复杂度整合”"
                "这一描述性判断，但任务与 verifier 缺陷会混淆差异，需以 v1.1 "
                "matched no-skill 回归复核。"
            ),
        },
        {
            "title": "生成的 skill 同时包含可迁移知识与 verifier 定向措辞",
            "body": (
                f"按保守关键词扫描，Fable 有 {fable['skills_with_verifier_markers']} "
                f"条、Opus 有 {opus['skills_with_verifier_markers']} 条 active skill "
                "提到 verifier、hidden test、regex 等裁判相关概念。逐条阅读显示，其中"
                "既有可迁移规则，也有“使用测试期望的精确词形”一类过拟合策略。"
                "因此报告展示完整 SKILL.md，并把“任务迁移能力”和“利用反馈适配裁判”"
                "分开解释。"
            ),
        },
    ]


def build_payload(
    old_report: dict[str, Any],
    behavior: dict[str, Any],
    task_audit: dict[str, Any],
    reference_audit: dict[str, Any],
    regression: dict[str, Any],
) -> dict[str, Any]:
    heatmap = heatmap_summary(old_report["self_generated_t1_t6"]["records"])
    return {
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "model_order": MODEL_ORDER,
        "model_zh": MODEL_ZH,
        "heatmap": heatmap,
        "behavior": behavior,
        "behavior_takeaways": behavior_takeaways(behavior),
        "task_audit": task_audit,
        "reference_audit": reference_audit,
        "regression": regression,
        "measurement_validity": old_report.get("measurement_validity", {}),
        "protocol_design": old_report.get("protocol_design", {}),
        "claim_boundary": behavior.get("claim_boundary"),
    }


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def render_html(data: dict[str, Any]) -> str:
    blob = _json_for_script(data)
    generated = html.escape(str(data["generated_at_utc"]))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SkillEvolBench v1.1 · 模型行为与题库质量报告</title>
<style>
:root{{--ink:#172033;--muted:#637087;--line:#dce3ef;--bg:#f5f7fb;--card:#fff;
--blue:#3867d6;--cyan:#1493a5;--green:#16805b;--amber:#b56b08;--red:#b43a45;
--purple:#7353ba;--shadow:0 12px 36px rgba(34,49,78,.09)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.65 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI","PingFang SC",sans-serif}}
.wrap{{max-width:1480px;margin:auto;padding:28px}}.hero{{padding:42px;border-radius:24px;
background:linear-gradient(125deg,#16244a,#2b5db0 58%,#168b91);color:white;box-shadow:var(--shadow)}}
h1{{font-size:38px;line-height:1.18;margin:8px 0 12px}}h2{{font-size:25px;margin:0 0 16px}}
h3{{font-size:18px;margin:0 0 8px}}p{{margin:8px 0}}.eyebrow{{letter-spacing:.11em;
text-transform:uppercase;font-weight:750;opacity:.82}}.hero p{{max-width:980px;font-size:17px;opacity:.92}}
.badge{{display:inline-block;padding:5px 10px;border:1px solid rgba(255,255,255,.35);
border-radius:999px;margin:4px 8px 0 0;background:rgba(255,255,255,.1)}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:24px;
margin-top:20px;box-shadow:var(--shadow)}}.grid{{display:grid;gap:14px}}.cards{{grid-template-columns:repeat(4,1fr)}}
.two{{grid-template-columns:1fr 1fr}}.three{{grid-template-columns:repeat(3,1fr)}}.card{{border:1px solid var(--line);
border-radius:14px;padding:16px;background:#fff}}.card b.big{{display:block;font-size:28px;line-height:1.2}}
.small,.note{{color:var(--muted);font-size:13px}}.good{{color:var(--green)}}.warn{{color:var(--amber)}}
.bad{{color:var(--red)}}.flow{{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:10px;
align-items:stretch}}.stage{{padding:16px;border-radius:14px;background:#edf3ff;border:1px solid #cad8fa}}
.arrow{{align-self:center;font-size:26px;color:var(--blue)}}.filters{{display:flex;gap:12px;flex-wrap:wrap;
margin-bottom:14px}}select,input{{padding:8px 11px;border:1px solid var(--line);border-radius:9px;background:white}}
.heatmaps{{display:grid;grid-template-columns:repeat(3,minmax(440px,1fr));gap:14px;overflow:auto}}
.model-heat{{border:1px solid var(--line);border-radius:14px;padding:13px;min-width:440px}}
.tierheat{{display:grid;grid-template-columns:55px repeat(6,minmax(52px,1fr));gap:4px}}
.cell{{min-height:52px;padding:5px;border-radius:7px;display:flex;flex-direction:column;align-items:center;
justify-content:center;text-align:center}}.head{{background:#edf1f8;font-weight:750;min-height:34px}}
.v{{color:#fff;font-weight:800}}.v span{{font-size:10px;font-weight:600;opacity:.9}}
.barrow{{display:grid;grid-template-columns:160px 1fr 65px;gap:10px;align-items:center;margin:9px 0}}
.track{{height:12px;background:#edf1f7;border-radius:999px;overflow:hidden}}.fill{{height:100%;border-radius:999px}}
.tablebox{{overflow:auto;border:1px solid var(--line);border-radius:12px}}table{{border-collapse:collapse;width:100%;
min-width:760px}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{background:#f0f4fa;position:sticky;top:0}}tr.click{{cursor:pointer}}tr.click:hover{{background:#f5f8ff}}
.takeaway{{border-left:4px solid var(--blue);padding:11px 14px;background:#f4f7ff;border-radius:0 11px 11px 0}}
.metric{{display:inline-block;padding:2px 7px;border-radius:999px;background:#edf2fb;font-size:12px;margin:2px}}
details{{border:1px solid var(--line);border-radius:10px;padding:9px 12px;margin:8px 0}}summary{{cursor:pointer;font-weight:700}}
pre{{white-space:pre-wrap;word-break:break-word;background:#101827;color:#e8eefc;padding:14px;border-radius:9px;max-height:460px;overflow:auto}}
.drawer{{position:fixed;right:-760px;top:0;width:min(760px,94vw);height:100vh;background:white;z-index:10;
box-shadow:-20px 0 50px rgba(20,30,55,.2);padding:24px;overflow:auto;transition:.22s}}.drawer.open{{right:0}}
.close{{float:right;border:0;background:#edf1f8;border-radius:9px;padding:8px 11px;cursor:pointer}}
.repair-list{{columns:2;column-gap:18px}}.repair{{break-inside:avoid;border:1px solid var(--line);
border-radius:10px;padding:10px;margin:0 0 10px}}a{{color:#245ac3}}footer{{padding:28px;color:var(--muted);text-align:center}}
@media(max-width:1050px){{.cards,.three{{grid-template-columns:1fr 1fr}}.heatmaps{{grid-template-columns:1fr}}}}
@media(max-width:720px){{.wrap{{padding:12px}}.hero{{padding:25px}}h1{{font-size:29px}}.cards,.two,.three{{grid-template-columns:1fr}}
.flow{{grid-template-columns:1fr}}.arrow{{transform:rotate(90deg);text-align:center}}.repair-list{{columns:1}}}}
</style>
</head>
<body><div class="wrap">
<section class="hero">
  <div class="eyebrow">SkillEvolBench v1.1 · Quality & Behavior Study</div>
  <h1>模型能否把一次经验，变成下一次真正可用的 Skill？</h1>
  <p>本报告把“模型表现”“题库质量”“skill 是否被读取”“skill 是否产生因果帮助”分开，
  对比 Qwen 3.7 Max、S1 Fable、Opus 4.8，并记录 v1.1 的修题与真实容器验收。</p>
  <span class="badge">生成时间 {generated}</span><span class="badge">6 个环境</span>
  <span class="badge">30 个 skill families</span><span class="badge">180 个 primary tasks</span>
</section>

<section class="panel"><h2>领导先看：核心结论</h2><div class="grid cards" id="executive"></div>
<div id="takeaways" class="grid two" style="margin-top:14px"></div></section>

<section class="panel"><h2>这个 benchmark 到底怎么测</h2>
<div class="flow">
  <div class="stage"><h3>T1–T3 · 学习</h3><p>同一 family 的不同输入。每题最多 3 次，
  verifier 反馈后在同一 session 修复；终态后总结或修订 skill。</p></div><div class="arrow">→</div>
  <div class="stage"><h3>Freeze · 冻结技能库</h3><p>T3 结束后不再写 skill，避免一边考试一边改答案。</p></div><div class="arrow">→</div>
  <div class="stage"><h3>T4–T6 · 新输入迁移</h3><p>T4 context shift、T5 adversarial、T6 composition；
  每题 one-shot，任务结束后 verifier 给 outcome/process 结果。</p></div>
</div>
<p class="note"><b>Strict pass</b> = Outcome（结果正确）和 Process（关键过程行为）都通过。
<b>Skill utilization</b> = 轨迹中实际读取了 SKILL.md；它证明“用过”，不自动证明“有帮助”。
因果帮助必须与同模型、同任务的 no-skill 对照逐题比较。</p></section>

<section class="panel"><h2>读图前先看：关键术语</h2><div class="grid three">
<div class="card"><h3>Environment（环境）</h3><p>一种工作场景及其 Docker 运行环境，例如软件工程、
数据分析或办公自动化。共 6 个环境，不是 6 道题。</p></div>
<div class="card"><h3>Skill family（技能族）</h3><p>围绕同一种可迁移能力组织的 6 个任务。
每个环境 5 个 family，因此全库共有 30 个 family、180 个 primary tasks。</p></div>
<div class="card"><h3>T1–T6（任务角色）</h3><p>T1–T3 用来学习并总结经验；T4 是换情境，
T5 是干扰或边界输入，T6 是能力组合。它们不是简单的六档同质难度。</p></div>
<div class="card"><h3>Same-session retry</h3><p>同一道 T1–T3 中，模型看到 verifier 反馈后继续在
同一会话里修正，最多 3 次。它测“能否从刚刚的失败中恢复”。</p></div>
<div class="card"><h3>Freeze（冻结）</h3><p>T3 后技能库不再允许修改。T4–T6 只能读取已经形成的
skills，防止模型在考试阶段继续改答案。</p></div>
<div class="card"><h3>Verifier（自动裁判）</h3><p>Outcome 检查结果是否正确，Process 检查关键操作过程；
两者同时通过才记为 Strict pass。本报告不把 AP Job Succeeded 当作答题通过。</p></div>
<div class="card"><h3>Skill creation</h3><p>模型在 T1–T3 后生成或修订 SKILL.md，包括创建数量、
版本演进、长度和是否成功写入技能库。</p></div>
<div class="card"><h3>Skill utilization</h3><p>轨迹证明模型在 T4–T6 实际读取了某个 skill。
“读取过”只能证明使用行为，不能单独证明 skill 带来了通过。</p></div>
<div class="card"><h3>Matched no-skill control</h3><p>让同一个模型做完全相同的新输入，但不给生成的
技能库。逐题比较 skill rescue 与 skill harm，才接近回答“skill 是否有帮助”。</p></div>
</div></section>

<section class="panel"><h2>旧版主实验：三个模型 T1–T6 热力图</h2>
<div class="filters"><label>显示指标 <select id="hmMetric"><option value="strict">Strict</option>
<option value="outcome">Outcome</option><option value="process">Process</option></select></label></div>
<div class="heatmaps" id="heatmaps"></div><p class="note">每格 5 题。T1–T3 显示最多三次后的终态，
T4–T6 是 freeze 后 one-shot，不能把相邻 tier 当作相同预算下的纯难度曲线。</p></section>

<section class="panel"><h2>Opus 4.8 vs S1 Fable：skill creation</h2>
<div class="grid two" id="creationCards"></div><div id="creationBars" style="margin-top:16px"></div>
<p class="note">旧版 reflection rejection 主要来自 benchmark 的 frontmatter parser 缺陷；
报告同时展示原始观测和修复后的解释，不把它当作模型能力差异。</p></section>

<section class="panel"><h2>Opus 4.8 vs S1 Fable：skill utilization 与后续表现</h2>
<div class="grid two" id="utilCards"></div><div class="tablebox" style="margin-top:14px"><table>
<thead><tr><th>模型</th><th>T4 strict/outcome/process</th><th>T5</th><th>T6</th>
<th>任意 skill read</th><th>同 family skill read</th></tr></thead><tbody id="utilRows"></tbody></table></div>
<div id="paired" class="grid three" style="margin-top:14px"></div></section>

<section class="panel"><h2>逐 family 查看 skill 演进</h2>
<div class="filters"><select id="familyModel"><option value="all">两个模型</option>
<option value="sig-fable">S1 Fable</option><option value="opus-4.8">Opus 4.8</option></select>
<select id="familyEnv"><option value="all">全部环境</option></select><input id="familySearch" placeholder="搜索 family / skill"></div>
<div class="tablebox"><table><thead><tr><th>Family</th><th>模型</th><th>T1–T3 attempts / pass</th>
<th>Active skills</th><th>T4–T6 strict</th><th>同 family reads</th></tr></thead><tbody id="familyRows"></tbody></table></div></section>

<section class="panel"><h2>题库质量审计与 v1.1 改进</h2><div class="grid cards" id="auditCards"></div>
<div id="runtimeFinding" style="margin-top:14px"></div>
<div id="skillReflectionFinding" style="margin-top:14px"></div>
<div id="priorityPolicyFinding" style="margin-top:14px"></div>
<div id="rationaleLexicalFinding" style="margin-top:14px"></div>
<div id="labelPolicyFinding" style="margin-top:14px"></div>
<div id="temporalFixtureFinding" style="margin-top:14px"></div>
<div id="routineDeadlineFinding" style="margin-top:14px"></div>
<div id="implicitDpaFinding" style="margin-top:14px"></div>
<div id="bareEodFinding" style="margin-top:14px"></div>
<div id="draftContextFinding" style="margin-top:14px"></div>
<div id="responseContractFinding" style="margin-top:14px"></div>
<div id="releaseDecision" style="margin-top:14px"></div>
<div class="grid two" style="margin-top:14px">
 <div><h3>可解性 Gate</h3><div id="referenceGate"></div></div>
 <div><h3>Skill 迁移可识别性</h3><div id="validity"></div></div>
</div><h3 id="repairHeading" style="margin-top:18px"></h3><div class="repair-list" id="repairs"></div>
<details><summary id="processRewriteSummary"></summary><div id="processRewrites"></div></details></section>

<section class="panel"><h2>v1.1 Opus 回归与 matched no-skill 控制</h2><div id="regression"></div>
<p class="note">Reference solution 90/90 只证明题目资产内部可解；Opus self-generated 与 no-skill 的逐题差异
才用于分析 skill rescue / harm。AP Succeeded 仍需下载 verifier 与轨迹后才能进入这里。</p></section>

<section class="panel"><h2>结论边界与下一步</h2>
<ul><li>旧版模型排名受题目与 verifier 缺陷混淆，不能直接当作纯模型能力榜。</li>
<li>Skill read 是 utilization，不是 causal usefulness；no-skill matched control 是必要条件。</li>
<li>“On-task only” 题仍可测现场执行，但不得宣称证明了 T1–T3 历史 skill 迁移。</li>
<li id="releaseConclusion"></li></ul>
<p class="note" id="claimBoundary"></p></section>

<footer>SkillEvolBench v1.1 quality study · standalone inspectable HTML</footer>
</div>
<aside class="drawer" id="drawer"><button class="close" onclick="drawer.classList.remove('open')">关闭</button>
<div id="drawerBody"></div></aside>
<script>
const D={blob};
const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const pct=(n,d)=>d?Math.round(100*n/d)+'%':'—';
const colors={{'qwen3.7-max':'#3867d6','sig-fable':'#1493a5','opus-4.8':'#7353ba'}};
const totals=D.heatmap.totals;
const refSummary=D.reference_audit.summary||D.reference_audit;
let executive=[
 ['v1.1 标准解验收',`${{refSummary.passed||0}}/${{refSummary.total||90}}`,'真实容器 + 原 verifier'],
 ['契约 / outcome 修复',D.task_audit.summary.outcome_or_contract_repairs,'消除不可解和错误拒绝'],
 ['Process verifier 重写',D.task_audit.summary.runtime_process_verifier_rewrites_without_known_outcome_contract_bug,'从源码词形改为行为'],
 ['E6 隐藏 marker gate 清理',D.task_audit.summary.e6_hidden_source_marker_gates_removed_all_tiers||0,'覆盖 LS1–LS4、T1–T6'],
 ['替换而非硬补的题',D.task_audit.summary.v1_instances_replaced_instead_of_minimally_patched,'E6 scheduling 两题']
];
if(D.regression&&Object.keys(D.regression).length) executive.unshift([
 'v1.1 E6 · Skill vs no-skill',
 `${{D.regression.self_generated.strict_pass}}/15 vs ${{D.regression.no_skill.strict_pass}}/15`,
 '同模型、同 15 题 matched control'
]);
$('executive').innerHTML=executive.map(x=>`<div class="card"><span class="small">${{x[0]}}</span><b class="big">${{x[1]}}</b><span class="small">${{x[2]}}</span></div>`).join('');
$('takeaways').innerHTML=D.behavior_takeaways.map(x=>`<div class="takeaway"><h3>${{esc(x.title)}}</h3><p>${{esc(x.body)}}</p></div>`).join('');
function renderHeat(){{
 const metric=$('hmMetric').value;
 $('heatmaps').innerHTML=D.model_order.map(model=>{{
   const rows=['E1','E2','E3','E4','E5','E6'].map(env=>[1,2,3,4,5,6].map(t=>D.heatmap.records.find(x=>x.model===model&&x.environment_id===env&&x.tier===t)));
   return `<div class="model-heat"><h3>${{D.model_zh[model]}} <span class="small">总计 ${{totals[model][metric]}}/${{totals[model].observed}}</span></h3>
   <div class="tierheat"><div class="cell head">Env</div>${{[1,2,3,4,5,6].map(t=>`<div class="cell head">T${{t}}</div>`).join('')}}
   ${{rows.map((r,i)=>`<div class="cell head">E${{i+1}}</div>`+r.map(x=>{{let p=x[metric]/x.observed;let bg=p>=.8?'#16805b':p>=.4?'#b56b08':'#b43a45';return `<div class="cell v" style="background:${{bg}}">${{x[metric]}}/${{x.observed}}<span>${{pct(x[metric],x.observed)}}</span></div>`}}).join('')).join('')}}</div></div>`}}).join('');
}} $('hmMetric').onchange=renderHeat; renderHeat();
const B=D.behavior.model_summaries;
$('creationCards').innerHTML=['sig-fable','opus-4.8'].map(m=>{{let x=B[m];return `<div class="card"><h3>${{D.model_zh[m]}}</h3>
<p><b>${{x.terminal_passes}}/90</b> T1–T3 终态通过 · <b>${{x.repaired_to_pass}}</b> 次 fail→pass</p>
<p class="small">active skills ${{x.active_skills}} · versions ${{x.total_skill_versions}} · 多版本 skills ${{x.skills_with_multiple_versions}} · 中位长度 ${{Math.round(x.median_skill_chars)}} chars · rejected reflections ${{x.reflection_status_counts.rejected||0}}</p></div>`}}).join('');
const creationMetrics=[['Skill versions','total_skill_versions'],['Active skills','active_skills'],['多版本 skills','skills_with_multiple_versions'],['中位长度 ÷ 500','median_skill_chars']];
$('creationBars').innerHTML=creationMetrics.map(([label,key])=>{{let vals=['sig-fable','opus-4.8'].map(m=>key==='median_skill_chars'?B[m][key]/500:B[m][key]);let max=Math.max(...vals);return `<div class="card"><b>${{label}}</b>${{['sig-fable','opus-4.8'].map((m,i)=>`<div class="barrow"><span>${{D.model_zh[m]}}</span><div class="track"><div class="fill" style="width:${{100*vals[i]/max}}%;background:${{colors[m]}}"></div></div><b>${{key==='median_skill_chars'?Math.round(B[m][key]):B[m][key]}}</b></div>`).join('')}}</div>`}}).join('');
function tier(m,t){{return B[m].by_tier.find(x=>x.tier===t)}} 
$('utilCards').innerHTML=['sig-fable','opus-4.8'].map(m=>`<div class="card"><h3>${{D.model_zh[m]}}</h3><p><b>${{B[m].evaluation_any_skill_used}}/90</b> evaluation tasks 实际读取 skill</p><p><b>${{B[m].evaluation_same_family_skill_used}}/90</b> 读取同 family skill</p><p class="small">“同 family”不是越高必然越好；T6 可合理组合其他 family 的技能。</p></div>`).join('');
$('utilRows').innerHTML=['sig-fable','opus-4.8'].map(m=>`<tr><td><b>${{D.model_zh[m]}}</b></td>${{[4,5,6].map(t=>{{let x=tier(m,t);return `<td>${{x.strict_pass}}/${{x.outcome_pass}}/${{x.process_pass}}</td>`}}).join('')}}<td>${{B[m].evaluation_any_skill_used}}/90</td><td>${{B[m].evaluation_same_family_skill_used}}/90</td></tr>`).join('');
$('paired').innerHTML=['strict','outcome','process'].map(k=>{{let x=D.behavior.paired_summary[k];return `<div class="card"><h3>${{k.toUpperCase()}} · 90 matched tasks</h3><p>都通过 <b>${{x.both_pass}}</b> · 都失败 <b>${{x.both_fail}}</b></p><p class="small">Fable only ${{x['sig-fable_only']}} · Opus only ${{x['opus-4.8_only']}}</p></div>`}}).join('');
['E1','E2','E3','E4','E5','E6'].forEach(e=>$('familyEnv').insertAdjacentHTML('beforeend',`<option>${{e}}</option>`));
function renderFamilies(){{
 let model=$('familyModel').value,env=$('familyEnv').value,q=$('familySearch').value.toLowerCase(),rows=[];
 D.behavior.families.forEach(f=>Object.entries(f.models).forEach(([m,x])=>{{let text=JSON.stringify([f.family_id,x.skills]).toLowerCase();if((model==='all'||m===model)&&(env==='all'||f.environment_id===env)&&text.includes(q))rows.push([f,m,x])}}));
 $('familyRows').innerHTML=rows.map(([f,m,x])=>`<tr class="click" data-family="${{f.family_id}}" data-model="${{m}}"><td><b>${{f.family_id}}</b><br><span class="small">${{f.environment_id}}</span></td><td>${{D.model_zh[m]}}</td><td>${{x.learning_attempts}} / ${{x.terminal_learning_passes}}/3</td><td>${{x.active_skill_count}}<br><span class="small">${{x.skills.map(s=>s.skill_slug).join(', ')}}</span></td><td>${{x.evaluation_strict_passes}}/3</td><td>${{x.same_family_skill_reads}}/3</td></tr>`).join('');
 document.querySelectorAll('#familyRows tr').forEach(tr=>tr.onclick=()=>showFamily(tr.dataset.family,tr.dataset.model));
}}
function showFamily(id,m){{let f=D.behavior.families.find(x=>x.family_id===id),x=f.models[m];
 let learning=x.learning.map(t=>`<tr><td>${{t.task_id}}</td><td>${{t.attempts}}</td><td>${{t.initial_pass?'✓':'✗'}} → ${{t.terminal_pass?'✓':'✗'}}</td><td>${{esc(t.reflection_status)}}${{t.reflection_rejection_reason?'<br><span class="bad">'+esc(t.reflection_rejection_reason)+'</span>':''}}</td></tr>`).join('');
 let skills=x.skills.map(s=>`<details><summary>${{esc(s.skill_id)}} · v${{s.current_version}} · ${{s.generated_chars}} chars</summary><p>${{esc(s.description)}}</p><p class="small">${{esc(s.version_summaries.map(v=>'v'+v.version+': '+v.summary).join('\\n'))}}</p><p class="small">${{esc(s.generated_path)}}</p></details>`).join('')||'<p class="bad">无 active skill</p>';
 let evals=x.evaluation.map(t=>`<tr><td>${{t.task_id}}</td><td>${{t.strict_pass?'✓':'✗'}} / ${{t.outcome_pass?'✓':'✗'}} / ${{t.process_pass?'✓':'✗'}}</td><td>${{esc(t.skills_actually_used.join(', ')||'none')}}</td></tr>`).join('');
 $('drawerBody').innerHTML=`<h2>${{id}} · ${{D.model_zh[m]}}</h2><h3>T1–T3</h3><div class="tablebox"><table><tr><th>任务</th><th>尝试</th><th>初始→终态</th><th>Reflection</th></tr>${{learning}}</table></div><h3 style="margin-top:15px">生成的 skills</h3>${{skills}}<h3 style="margin-top:15px">T4–T6</h3><div class="tablebox"><table><tr><th>任务</th><th>Strict/Outcome/Process</th><th>实际读取</th></tr>${{evals}}</table></div>`;$('drawer').classList.add('open');
}} ['familyModel','familyEnv'].forEach(id=>$(id).onchange=renderFamilies);$('familySearch').oninput=renderFamilies;renderFamilies();
const S=D.task_audit.summary;
$('auditCards').innerHTML=[['Held-out tasks',S.held_out_tasks_total],['修复 contracts',S.outcome_or_contract_repairs],['重写 process checks',S.runtime_process_verifier_rewrites_without_known_outcome_contract_bug],['保持不变',S.unchanged_held_out_tasks]].map(x=>`<div class="card"><span class="small">${{x[0]}}</span><b class="big">${{x[1]}}</b></div>`).join('');
let RF=D.task_audit.model_runtime_finding_after_v1_1_1||{{}};
$('runtimeFinding').innerHTML=Object.keys(RF).length?`<div class="card warn"><h3>为什么 90/90 标准解通过后仍然发布 v1.1@2？</h3><p><b>${{esc(RF.task_id||'E6-LS1-T6')}}</b> 的真实 Opus 输出已经通过全部 outcome tests，却因为源码没有未公开短语 <code>P0 reply</code> 而 process fail。标准解恰好带有该短语，所以 reference audit 无法暴露这个问题。</p><p>${{esc(RF.systematic_audit_zh||RF.systematic_audit||'')}}</p><p class="small">${{esc(RF.v1_1_2_change_zh||RF.v1_1_2_change||'')}}</p></div>`:'';
let SF=D.task_audit.skill_reflection_quality_finding_after_v1_1_2||{{}};
$('skillReflectionFinding').innerHTML=Object.keys(SF).length?`<div class="card warn"><h3>v1.1@2 真实运行发现：skill 可能学会“适配裁判”</h3><p><b>${{esc(SF.task_id||'E6-LS1-T1')}}</b>：${{esc(SF.observed_result_zh||SF.observed_result||'')}}</p><p>${{esc(SF.quality_problem_zh||SF.quality_problem||'')}}</p><p class="small"><b>下一轮改进：</b>${{esc(SF.v1_1_3_change_zh||SF.v1_1_3_change||'')}}</p></div>`:'';
let PF=D.task_audit.priority_policy_gap_after_v1_1_3||{{}};
$('priorityPolicyFinding').innerHTML=Object.keys(PF).length?`<div class="card warn"><h3>v1.1@3 真实运行发现：文案干净不等于规则完整</h3><p><b>${{esc(PF.observed_task||'E6-LS1-T1')}}</b>：${{esc(PF.finding_zh||PF.finding||'')}}</p><p>${{esc(PF.quality_decision_zh||PF.quality_decision||'')}}</p><p class="small"><b>下一轮改进：</b>${{esc(PF.next_split_change||'')}}</p></div>`:'';
let LF=D.task_audit.rationale_lexical_gap_after_v1_1_4||{{}};
$('rationaleLexicalFinding').innerHTML=Object.keys(LF).length?`<div class="card warn"><h3>v1.1@4 真实运行发现：正确决策不应输给隐藏理由词表</h3><p><b>${{esc(LF.observed_task||'E6-LS1-T1')}}</b>：${{esc(LF.observed_result_zh||LF.observed_result||'')}}</p><p>${{esc(LF.false_negative_proof_zh||LF.false_negative_proof||'')}}</p><p class="small"><b>系统修复：</b>${{esc(LF.systematic_change_zh||LF.systematic_change||'')}}</p></div>`:'';
let LP=D.task_audit.label_policy_conflict_after_v1_1_5||{{}};
$('labelPolicyFinding').innerHTML=Object.keys(LP).length?`<div class="card warn"><h3>v1.1@5 真实运行发现：公开政策与隐藏标签必须一致</h3><p><b>${{esc(LP.observed_task||'E6-LS1-T2')}}</b>：${{esc(LP.observed_result_zh||LP.observed_result||'')}}</p><p>${{esc(LP.systematic_audit_zh||LP.systematic_audit||'')}}</p><p>${{esc(LP.false_negative_proof_zh||LP.false_negative_proof||'')}}</p><p class="small"><b>系统修复：</b>${{esc(LP.systematic_change_zh||LP.systematic_change||'')}}</p></div>`:'';
let TF=D.task_audit.temporal_fixture_conflict_after_v1_1_6||{{}};
$('temporalFixtureFinding').innerHTML=Object.keys(TF).length?`<div class="card warn"><h3>v1.1@6 真实运行发现：时间线必须与标签语义一致</h3><p><b>${{esc(TF.observed_task||'E6-LS1-T2')}}</b>：${{esc(TF.observed_result_zh||TF.observed_result||'')}}</p><p>${{esc(TF.quality_problem_zh||TF.quality_problem||'')}}</p><p class="small"><b>系统修复：</b>${{esc(TF.systematic_change_zh||TF.systematic_change||'')}}</p></div>`:'';
let DF=D.task_audit.routine_deadline_boundary_after_v1_1_7||{{}};
$('routineDeadlineFinding').innerHTML=Object.keys(DF).length?`<div class="card warn"><h3>v1.1@7 真实运行发现：标准解可过，不代表公开边界唯一</h3><p><b>${{esc(DF.observed_task||'E6-LS1-T4')}}</b>：${{esc(DF.observed_result_zh||DF.observed_result||'')}}</p><p>${{esc(DF.quality_problem_zh||DF.quality_problem||'')}}</p><p class="small"><b>系统修复：</b>${{esc(DF.systematic_change_zh||DF.systematic_change||'')}}</p></div>`:'';
let IF=D.task_audit.implicit_dpa_blocker_after_v1_1_8||{{}};
$('implicitDpaFinding').innerHTML=Object.keys(IF).length?`<div class="card warn"><h3>v1.1@8 真实运行发现：隐藏的业务后果无法学成可靠 skill</h3><p><b>${{esc(IF.observed_task||'E6-LS1-T2')}}</b>：${{esc(IF.observed_result_zh||IF.observed_result||'')}}</p><p>${{esc(IF.quality_problem_zh||IF.quality_problem||'')}}</p><p class="small"><b>系统修复：</b>${{esc(IF.systematic_change_zh||IF.systematic_change||'')}}</p></div>`:'';
let EF=D.task_audit.bare_eod_policy_conflict_after_v1_1_9||{{}};
$('bareEodFinding').innerHTML=Object.keys(EF).length?`<div class="card warn"><h3>v1.1@9 真实运行发现：含糊反馈会污染 skill，并伤害后续迁移</h3><p><b>${{esc((EF.observed_tasks||[]).join(', ')||'E6-LS1-T3 / T4')}}</b>：${{esc(EF.observed_result_zh||EF.observed_result||'')}}</p><p>${{esc(EF.quality_problem_zh||EF.quality_problem||'')}}</p><p class="small"><b>v1.1@10 系统修复：</b>${{esc(EF.systematic_change_zh||EF.systematic_change||'')}}</p></div>`:'';
let GF=D.task_audit.draft_context_lexical_gap_after_v1_1_10||{{}};
$('draftContextFinding').innerHTML=Object.keys(GF).length?`<div class="card warn"><h3>v1.1@10 真实运行发现：上下文完整的草稿不应输给单个产品名</h3><p><b>${{esc(GF.observed_task||'E6-LS1-T6')}}</b>：${{esc(GF.observed_result_zh||GF.observed_result||'')}}</p><p>${{esc(GF.false_negative_proof_zh||GF.false_negative_proof||'')}}</p><p class="small"><b>v1.1@11 系统修复：</b>${{esc(GF.systematic_change_zh||GF.systematic_change||'')}}</p></div>`:'';
let RF=D.task_audit.response_observability_gap_after_v1_1_11||{{}};
$('responseContractFinding').innerHTML=Object.keys(RF).length?`<div class="card warn"><h3>v1.1@11 真实运行发现：P0 需要行动，不等于邮件必然需要回复</h3><p><b>${{esc(RF.observed_task||'E6-LS1-T4')}}</b>：${{esc(RF.observed_result_zh||RF.observed_result||'')}}</p><p>${{esc(RF.quality_problem_zh||RF.quality_problem||'')}}</p><p class="small"><b>v1.1@12 系统修复：</b>${{esc(RF.systematic_change_zh||RF.systematic_change||'')}}</p><p class="small"><b>冻结输出复核：</b>${{esc(RF.frozen_workspace_proof||'')}}</p></div>`:'';
let RD=D.task_audit.release_decision||{{}},replaced=RD.replace||[];
$('releaseDecision').innerHTML=`<div class="grid three"><div class="card good"><h3>保留：30 个 skill families</h3><p>${{esc(RD.retain_zh||RD.retain||'所有 family 均保留')}}</p></div><div class="card warn"><h3>替换：${{replaced.length}} 个具体实例</h3><p><b>${{esc(replaced.join(', ')||'无')}}</b></p><p class="small">${{esc(RD.reason_zh||RD.reason||'')}}</p></div><div class="card"><h3>整族退役：${{S.whole_skill_families_retired||0}}</h3><p>能力目标仍有评测价值；有缺陷的具体题采用修复或替换，不为维持题量而保留不可解实例。</p></div></div><p class="note">${{esc(RD.low_transfer_identifiability_zh||RD.low_transfer_identifiability||'')}}</p>`;
let R=D.reference_audit;$('referenceGate').innerHTML=`<div class="card"><b class="big good">${{refSummary.passed||0}}/${{refSummary.total||90}}</b><p>${{refSummary.all_reference_solutions_pass?'六个环境全部 15/15 strict pass':'尚未全部通过'}}</p><p class="small">${{esc(R.split||'v1.1@2')}} · Harbor oracle · real task container · unchanged verifier · AP group ${{esc(R.group_id||'—')}}</p></div>`;
$('releaseConclusion').textContent=`${{R.split||'最新 v1.1 候选'}} 已处理当前复现的不可解、隐藏任意 tie-break、标签与时间线冲突、未公开源码词门槛和隐藏理由词表；最终结论仍以逐题 verifier、轨迹与 matched no-skill 证据为准，而不是只看平均分。`;
let mv=(D.measurement_validity.summaries||[])[0]||{{category_counts:{{}},eligible_for_causal_skill_claim:0,controlled_task_count:60}},c=mv.category_counts;
$('validity').innerHTML=`<div class="card"><b class="big">${{mv.eligible_for_causal_skill_claim||0}}/${{mv.controlled_task_count||60}}</b><p>可进入历史 skill 因果分析</p><p class="small">history-supported ${{c.history_supported||0}} · mixed ${{c.mixed_history_and_on_task||0}} · on-task only ${{c.on_task_only||0}}</p></div>`;
$('repairHeading').textContent=`${{S.outcome_or_contract_repairs}} 个 outcome / contract 修复`;
$('repairs').innerHTML=D.task_audit.outcome_or_contract_repairs.map(x=>`<div class="repair"><b>${{x.task_id}}</b><p class="small"><b>原问题：</b>${{esc(x.issue_zh||x.issue)}}</p><p><b>v1.1 改进：</b>${{esc(x.v1_1_change_zh||x.v1_1_change)}}</p></div>`).join('');
$('processRewriteSummary').textContent=`${{S.runtime_process_verifier_rewrites_without_known_outcome_contract_bug}} 个 held-out process verifiers 从隐藏源码形态改为可观察行为`;
$('processRewrites').innerHTML=D.task_audit.runtime_process_verifier_rewrites_without_known_outcome_contract_bug.map(x=>`<span class="metric">${{x}}</span>`).join('');
function rbar(label,n,color){{return `<div class="barrow"><span>${{label}}</span><div class="track"><div class="fill" style="width:${{100*n/15}}%;background:${{color}}"></div></div><b>${{n}}/15</b></div>`}}
function renderRegression(){{let r=D.regression;if(!r||!Object.keys(r).length){{
 let status=D.task_audit.validation_gates?.opus_v1_1_self_generated_regression||'v1.1@2 matched-control regression 尚未完成';
 $('regression').innerHTML=`<div class="card warn"><b>回归运行中</b><p>该区域只接受同一 Opus、同一 E6、同一不可变 split 的 self-generated 与 no-skill 下载证据。AP 状态或旧 split 的结果不会被混入最终对照。</p><p class="small">${{esc(status)}}</p></div>`;return}}
 let L=r.learning,S=r.self_generated,N=r.no_skill;
 let learning=`<div class="grid cards"><div class="card"><span class="small">T1–T3 终态通过</span><b class="big">${{L.terminal_pass}}/${{L.tasks}}</b><span class="small">首次通过 ${{L.initial_pass}} · retry 修复 ${{L.repaired_to_pass}}</span></div><div class="card"><span class="small">Same-session 已验证</span><b class="big">${{L.same_session_verified}}/${{L.tasks}}</b><span class="small">总尝试 ${{L.attempts}}</span></div><div class="card"><span class="small">Active skills</span><b class="big">${{L.active_skills}}</b><span class="small">${{L.skill_versions}} 个版本</span></div><div class="card"><span class="small">T4–T6 skill read</span><b class="big">${{S.any_skill_read}}/15</b><span class="small">证明 utilization，不单独证明帮助</span></div></div>`;
 let metrics=`<div class="grid two" style="margin-top:14px"><div class="card"><h3>Self-generated</h3>${{['strict','outcome','process'].map(k=>rbar(k,S[k+'_pass'],'#7353ba')).join('')}}</div><div class="card"><h3>No-skill</h3>${{['strict','outcome','process'].map(k=>rbar(k,N[k+'_pass'],'#637087')).join('')}}</div></div>`;
 let paired=`<div class="grid three" style="margin-top:14px">${{['strict','outcome','process'].map(k=>{{let x=r.paired_summary[k]||{{}};return `<div class="card"><h3>${{k.toUpperCase()}} · paired</h3><p class="good">Skill rescue <b>${{x.skill_rescue||0}}</b></p><p class="bad">Skill harm <b>${{x.skill_harm||0}}</b></p><p class="small">both pass ${{x.both_pass||0}} · both fail ${{x.both_fail||0}}</p></div>`}}).join('')}}</div>`;
 let tiers=`<div class="tablebox" style="margin-top:14px"><table><thead><tr><th>Tier</th><th>Self-generated S/O/P</th><th>No-skill S/O/P</th><th>Skill reads</th></tr></thead><tbody>${{[4,5,6].map(t=>{{let a=S.by_tier.find(x=>x.tier===t),b=N.by_tier.find(x=>x.tier===t);return `<tr><td><b>T${{t}}</b></td><td>${{a.strict_pass}}/${{a.outcome_pass}}/${{a.process_pass}}</td><td>${{b.strict_pass}}/${{b.outcome_pass}}/${{b.process_pass}}</td><td>${{a.any_skill_read}}/5</td></tr>`}}).join('')}}</tbody></table></div>`;
 let tasks=`<details><summary>查看 15 个 matched tasks 的 verifier 与 skill-read 明细</summary><div class="tablebox"><table><thead><tr><th>Task</th><th>Tier</th><th>Paired state S/O/P</th><th>Selfgen S/O/P</th><th>No-skill S/O/P</th><th>实际读取 skill</th><th>失败测试</th></tr></thead><tbody>${{r.paired_tasks.map(x=>{{let a=x.self_generated,b=x.no_skill,mark=v=>v?'✓':'✗';return `<tr><td><b>${{x.task_id}}</b></td><td>T${{x.tier}}</td><td>${{x.states.strict}}<br><span class="small">${{x.states.outcome}} / ${{x.states.process}}</span></td><td>${{mark(a.strict_pass)}}/${{mark(a.outcome_pass)}}/${{mark(a.process_pass)}}</td><td>${{mark(b.strict_pass)}}/${{mark(b.outcome_pass)}}/${{mark(b.process_pass)}}</td><td>${{esc(a.skills_actually_used.join(', ')||'none')}}</td><td class="small">${{esc([...new Set([...(a.failed_tests||[]),...(b.failed_tests||[])])].join(', ')||'—')}}</td></tr>`}}).join('')}}</tbody></table></div></details>`;
 let skills=`<details><summary>查看 v1.1 E6 生成的 ${{L.active_skills}} 个 active skills 与版本演进</summary>${{L.skills.map(s=>`<div class="card" style="margin-top:10px"><h3>${{esc(s.skill_id)}}</h3><p>${{esc(s.description||'')}}</p><p class="small">${{esc((s.version_summaries||[]).map(v=>'v'+(v.version??'?')+': '+(v.summary||JSON.stringify(v))).join('\\n'))}}</p><details><summary>展开完整 SKILL.md</summary><pre>${{esc(s.generated_text||'未导出完整文本')}}</pre></details><p class="small">${{esc(s.generated_path||'')}}</p></div>`).join('')||'<p class="bad">没有 active skill</p>'}}</details>`;
 let learningTasks=`<details><summary>查看 T1–T3 的 15 条 same-session retry 记录</summary><div class="tablebox"><table><thead><tr><th>Task</th><th>Attempts</th><th>初始→终态</th><th>Same session</th><th>Reflection</th></tr></thead><tbody>${{(L.task_records||[]).map(x=>`<tr><td>${{x.task_id}}</td><td>${{x.attempts}}</td><td>${{x.initial_pass?'✓':'✗'}} → ${{x.terminal_pass?'✓':'✗'}}</td><td>${{x.same_session_verified?'✓':'✗'}}</td><td>${{esc(x.reflection_status||'—')}}</td></tr>`).join('')}}</tbody></table></div></details>`;
 let links=`<p class="small">AP jobs · <a href="https://agentplatform.aliyun-inc.com/?cluster=hk-benchmark-dev#/jobs/${{r.jobs.self_generated}}" target="_blank">self-generated</a> · <a href="https://agentplatform.aliyun-inc.com/?cluster=hk-benchmark-dev#/jobs/${{r.jobs.no_skill}}" target="_blank">no-skill</a><br>${{esc(r.claim_boundary||'')}}</p>`;
 $('regression').innerHTML=learning+metrics+paired+tiers+tasks+skills+learningTasks+links;
}}renderRegression();
$('claimBoundary').textContent=D.claim_boundary||'';
</script></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-report-data", type=Path, required=True)
    parser.add_argument("--behavior-audit", type=Path, required=True)
    parser.add_argument("--task-audit", type=Path, required=True)
    parser.add_argument("--reference-audit", type=Path, required=True)
    parser.add_argument("--regression", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = build_payload(
        load_json(args.old_report_data),
        load_json(args.behavior_audit),
        load_json(args.task_audit),
        load_json(args.reference_audit),
        load_optional_json(args.regression),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(data), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
