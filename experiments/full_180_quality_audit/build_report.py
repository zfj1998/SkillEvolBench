#!/usr/bin/env python3
"""Render the 180-row five-point audit as Chinese Markdown and interactive HTML."""

from __future__ import annotations

import argparse
import html
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POINT_KEYS = (
    "1_experience_generation_and_reuse",
    "2_historical_skill_demand",
    "3_correct_expert_skill_effect",
    "4_unrelated_skill_negative_control",
    "5_task_and_verifier_validity",
)


def load_ledger(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("tasks"), list):
        raise ValueError("ledger must be a JSON object with a tasks array")
    tasks = value["tasks"]
    ids = [str(row.get("task_id")) for row in tasks if isinstance(row, dict)]
    if len(tasks) != 180 or len(set(ids)) != 180:
        raise ValueError(
            f"expected 180 unique task rows, got rows={len(tasks)} unique={len(set(ids))}"
        )
    return value


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(value, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def point_status_counts(tasks: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        key: dict(
            sorted(
                Counter(
                    str((row.get("checks", {}).get(key) or {}).get("status") or "missing")
                    for row in tasks
                ).items()
            )
        )
        for key in POINT_KEYS
    }


def report_payload(ledger: dict[str, Any]) -> dict[str, Any]:
    tasks = ledger["tasks"]
    readiness = Counter(str(row.get("readiness") or "missing") for row in tasks)
    heatmap = []
    for environment in range(1, 7):
        for tier in range(1, 7):
            selected = [
                row
                for row in tasks
                if row.get("environment_id") == f"E{environment}"
                and int(row.get("tier", 0)) == tier
            ]
            heatmap.append(
                {
                    "environment_id": f"E{environment}",
                    "tier": tier,
                    "ready": sum(row.get("readiness") == "ready" for row in selected),
                    "total": len(selected),
                }
            )
    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "ledger_schema_version": ledger.get("schema_version"),
        "benchmark_revision": ledger.get("benchmark_revision"),
        "claim_boundary": ledger.get("claim_boundary"),
        "summary": ledger.get("summary") or {},
        "readiness": dict(sorted(readiness.items())),
        "point_status_counts": point_status_counts(tasks),
        "heatmap": heatmap,
        "tasks": tasks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# SkillEvolBench 180 题五项复查",
        "",
        f"生成时间：`{payload['generated_at_utc']}`  ",
        f"Benchmark revision：`{payload.get('benchmark_revision')}`",
        "",
        "这里的五项是五个审计维度，不是只保留五道题。审计表固定包含 180 个唯一 task。",
        "首轮矩阵固定有 630 个 task-condition cells；计入 T1--T3 的同 session retry 后，实际 task attempts 为 630--810。",
        "",
        "## 覆盖与完成度",
        "",
        f"- 逐题行数：{summary.get('task_count', 0)}",
        f"- 静态 verifier 覆盖：{summary.get('static_verifier_coverage', 0)}/180",
        f"- 当前 T1--T3 learning 覆盖：{summary.get('v1_1_current_learning_coverage', 0)}/90",
        f"- self-generated/no-skill 配对覆盖：{summary.get('v1_1_matched_selfgen_no_skill_coverage', 0)}/90",
        f"- exact curated 覆盖：{summary.get('v1_1_exact_curated_coverage', 0)}/90",
        f"- shuffled curated 覆盖：{summary.get('v1_1_shuffled_curated_coverage', 0)}/90",
        f"- reference solution 覆盖：{summary.get('v1_1_reference_solution_coverage', 0)}/180",
        f"- reference solution strict pass：{summary.get('v1_1_reference_solution_strict_passes', 0)}/180",
        f"- 五项证据已齐：{summary.get('ready_for_final_five_point_decision', 0)}/180",
        f"- 复查优先级：{json.dumps(summary.get('screening_priority_counts', {}), ensure_ascii=False, sort_keys=True)}",
        f"- 已完成人工语义复核：{summary.get('manual_semantic_review_count', 0)}",
        "",
        "## 证据门槛",
        "",
        "- T1--T3：同 session repair、终态 reflection、有效 skill patch、后续不同输入读取/使用，以及 reference/verifier 证据。",
        "- T4--T6：同模型同题的 self-generated、no-skill、exact curated、shuffled curated 四条件 outcome；strict/process 只作诊断。",
        "- shuffled 必须与 gold 等量、跨环境、ID 零重叠且内容 hash 可验证。",
        "- AP/transport/timeout 失败不计为模型零分；reference pass 只证明内部可解，不自动证明 verifier 语义合理。",
        "",
        "## 当前完整性检查",
        "",
    ]
    errors = summary.get("current_evidence_errors") or []
    if errors:
        lines.extend(f"- 未完成：{error}" for error in errors)
    else:
        lines.append("- 通过：当前四条件、180 条 reference records 和协议证据均完整；reference failure 会作为第 5 点结果保留，不会被当作缺数隐藏。")
    lines.extend(
        [
            "",
            "## 逐题索引",
            "",
            "完整逐题证据（含原题面、轨迹路径、skill patch、四条件结果、reference 与 verifier 风险）请查看同目录 HTML 或 JSON；CSV 提供扁平索引。",
            "",
            f"> 结论边界：{payload.get('claim_boundary') or ''}",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    title = "SkillEvolBench 180 题五项复查"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{--bg:#f5f7fb;--panel:#fff;--ink:#172033;--muted:#667085;--line:#dce2ec;--accent:#335cff;--good:#087443;--warn:#a15c00;--bad:#b42318}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 Inter,system-ui,-apple-system,"Noto Sans SC",sans-serif}}
main{{max-width:1480px;margin:auto;padding:28px}} h1{{font-size:28px;margin:0 0 6px}} .muted{{color:var(--muted)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0}} .card,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 2px 10px #1720330a}}
.num{{font-size:27px;font-weight:750}} .toolbar{{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}} input,select{{border:1px solid var(--line);border-radius:9px;background:white;padding:9px 11px}}
.heat{{display:grid;grid-template-columns:56px repeat(6,minmax(72px,1fr));gap:6px;align-items:stretch}} .heat div{{padding:8px;border-radius:8px;text-align:center;border:1px solid var(--line)}} .heat .head{{font-weight:700;background:#eef2ff}} .heat .cell{{cursor:pointer;background:color-mix(in srgb,#2eae72 calc(var(--p)*1%),#fff)}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:12px;background:white}} table{{border-collapse:collapse;width:100%;min-width:1180px}} th,td{{padding:9px 10px;border-bottom:1px solid #edf0f5;text-align:left;vertical-align:top}} th{{position:sticky;top:0;background:#f8faff;z-index:1}} tr.task{{cursor:pointer}} tr.task:hover{{background:#f4f7ff}}
.badge{{display:inline-block;padding:2px 7px;border-radius:999px;background:#eef2f7;font-size:12px;white-space:nowrap}} .ready{{background:#dff5e8;color:var(--good)}} .missing{{background:#fff0dc;color:var(--warn)}}
dialog{{width:min(1100px,94vw);max-height:90vh;border:0;border-radius:15px;padding:0;box-shadow:0 24px 80px #10182855}} dialog::backdrop{{background:#10182888}} .modal-head{{position:sticky;top:0;background:white;border-bottom:1px solid var(--line);padding:16px 20px;display:flex;justify-content:space-between}} .modal-body{{padding:20px;overflow:auto}} button{{border:0;border-radius:8px;padding:8px 12px;cursor:pointer}} pre{{white-space:pre-wrap;word-break:break-word;background:#f7f8fb;border:1px solid var(--line);padding:12px;border-radius:9px;max-height:420px;overflow:auto}} details{{border:1px solid var(--line);border-radius:9px;padding:9px 11px;margin:8px 0}} summary{{cursor:pointer;font-weight:650}}
@media(max-width:760px){{main{{padding:16px}}.heat{{grid-template-columns:44px repeat(6,minmax(46px,1fr));font-size:11px}}}}
</style></head><body><main>
<h1>{html.escape(title)}</h1><div class="muted" id="meta"></div>
<section class="cards" id="cards"></section>
<section class="panel"><h2>证据完整度热力图</h2><div class="muted">每格为该环境、该 tier 已齐五项适用证据的题数 / 5。点击可筛选。</div><div class="heat" id="heat"></div></section>
<section class="panel"><h2>180 题逐题表</h2><div class="toolbar"><input id="q" placeholder="搜索 task id / slug / instruction / flag"><select id="env"><option value="">全部环境</option></select><select id="tier"><option value="">全部 Tier</option></select><select id="priority"><option value="">全部复查优先级</option><option value="high">high</option><option value="medium">medium</option><option value="low">low</option></select><select id="ready"><option value="">全部完成度</option><option value="ready">证据已齐</option><option value="missing">证据未齐</option></select><span class="muted" id="shown"></span></div><div class="table-wrap"><table><thead><tr><th>Task</th><th>Env</th><th>Tier</th><th>角色</th><th>完成度</th><th>复查优先级</th><th>① 生成/复用</th><th>② 历史需求</th><th>③ 正确 skill</th><th>④ 无关 skill</th><th>⑤ task/verifier</th></tr></thead><tbody id="rows"></tbody></table></div></section>
</main><dialog id="detail"><div class="modal-head"><strong id="detail-title"></strong><button id="close">关闭</button></div><div class="modal-body" id="detail-body"></div></dialog>
<script>const DATA={encoded};
const pointKeys={json.dumps(POINT_KEYS, ensure_ascii=False)};
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const sum=DATA.summary||{{}}; $('#meta').textContent=`revision ${{DATA.benchmark_revision||'unknown'}} · ${{DATA.generated_at_utc}} · 首轮动态结果只是 screen，关键翻转需要复跑`;
const cards=[['180','唯一 tasks'],[sum.planned_task_condition_cells||630,'task-condition cells'],[sum.static_verifier_coverage||0,'静态 verifier'],[sum.v1_1_current_learning_coverage||0,'当前 T1–T3'],[sum.v1_1_matched_selfgen_no_skill_coverage||0,'self/no 配对'],[sum.v1_1_exact_curated_coverage||0,'exact skill'],[sum.v1_1_shuffled_curated_coverage||0,'shuffled skill'],[sum.v1_1_reference_solution_coverage||0,'reference records'],[sum.v1_1_reference_solution_strict_passes||0,'reference strict pass'],[sum.manual_semantic_review_count||0,'人工语义复核'],[sum.ready_for_final_five_point_decision||0,'证据已齐']];
$('#cards').innerHTML=cards.map(x=>`<div class="card"><div class="num">${{esc(x[0])}}</div><div class="muted">${{esc(x[1])}}</div></div>`).join('');
for(let i=1;i<=6;i++){{$('#env').insertAdjacentHTML('beforeend',`<option>E${{i}}</option>`);$('#tier').insertAdjacentHTML('beforeend',`<option value="${{i}}">T${{i}}</option>`);}}
const heat=$('#heat'); heat.innerHTML='<div class="head"></div>'+[1,2,3,4,5,6].map(t=>`<div class="head">T${{t}}</div>`).join('');
for(let e=1;e<=6;e++){{heat.insertAdjacentHTML('beforeend',`<div class="head">E${{e}}</div>`);for(let t=1;t<=6;t++){{const x=DATA.heatmap.find(v=>v.environment_id===`E${{e}}`&&v.tier===t);const p=x.total?x.ready/x.total*100:0;heat.insertAdjacentHTML('beforeend',`<div class="cell" style="--p:${{p}}" data-env="E${{e}}" data-tier="${{t}}">${{x.ready}}/${{x.total}}</div>`);}}}}
heat.addEventListener('click',e=>{{const c=e.target.closest('.cell');if(!c)return;$('#env').value=c.dataset.env;$('#tier').value=c.dataset.tier;render();}});
function badge(s,ready=false){{return `<span class="badge ${{ready?'ready':'missing'}}">${{esc(s||'missing')}}</span>`}}
function showDetail(task){{$('#detail-title').textContent=`${{task.task_id}} · ${{task.task_slug}}`;const checks=task.checks||{{}};$('#detail-body').innerHTML=`<p><b>环境 / family / tier：</b>${{esc(task.environment_id)}} / ${{esc(task.family_id)}} / T${{esc(task.tier)}}</p><p><b>完成度：</b>${{badge(task.readiness,task.readiness==='ready')}}　<b>复查优先级：</b>${{badge(task.screening_priority,task.screening_priority==='low')}}</p><p><b>筛查 flags：</b>${{esc((task.screening_flags||[]).join(', ')||'none')}}</p><h3>题面</h3><pre>${{esc(task.instruction)}}</pre><h3>五项证据</h3>${{pointKeys.map((k,i)=>`<details ${{i===0?'open':''}}><summary>${{i+1}}. ${{esc(checks[k]?.status||'missing')}}</summary><pre>${{esc(JSON.stringify(checks[k]||{{}},null,2))}}</pre></details>`).join('')}}`;$('#detail').showModal();}}
function render(){{const q=$('#q').value.toLowerCase(),env=$('#env').value,tier=$('#tier').value,priority=$('#priority').value,ready=$('#ready').value;const selected=DATA.tasks.filter(t=>(!q||`${{t.task_id}} ${{t.task_slug}} ${{t.instruction}} ${{(t.screening_flags||[]).join(' ')}}`.toLowerCase().includes(q))&&(!env||t.environment_id===env)&&(!tier||String(t.tier)===tier)&&(!priority||t.screening_priority===priority)&&(!ready||(ready==='ready')===(t.readiness==='ready')));$('#shown').textContent=`显示 ${{selected.length}} / 180`;const body=$('#rows');body.innerHTML='';for(const t of selected){{const tr=document.createElement('tr');tr.className='task';tr.innerHTML=`<td><b>${{esc(t.task_id)}}</b><br><span class="muted">${{esc(t.task_slug)}}</span></td><td>${{esc(t.environment_id)}}</td><td>T${{esc(t.tier)}}</td><td>${{esc(t.role)}}</td><td>${{badge(t.readiness,t.readiness==='ready')}}</td><td>${{badge(t.screening_priority,t.screening_priority==='low')}}</td>${{pointKeys.map(k=>`<td>${{badge(t.checks?.[k]?.status||'missing',t.readiness==='ready')}}</td>`).join('')}}`;tr.addEventListener('click',()=>showDetail(t));body.appendChild(tr);}}}}
['q','env','tier','priority','ready'].forEach(id=>$('#'+id).addEventListener(id==='q'?'input':'change',render));$('#close').onclick=()=>$('#detail').close();render();
</script></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = report_payload(load_ledger(args.ledger))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "report_summary.json"
    md_path = args.output_dir / "skillevolbench_180_five_point_audit_zh.md"
    html_path = args.output_dir / "skillevolbench_180_five_point_audit_zh.html"
    atomic_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    atomic_text(md_path, render_markdown(payload))
    atomic_text(html_path, render_html(payload))
    print(
        json.dumps(
            {
                "json": str(json_path.resolve()),
                "markdown": str(md_path.resolve()),
                "html": str(html_path.resolve()),
                "task_count": len(payload["tasks"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
