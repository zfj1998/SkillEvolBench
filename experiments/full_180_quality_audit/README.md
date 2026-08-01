# SkillEvolBench 180 题五项复查

本目录用于回答一个窄问题：当前 SkillEvolBench 的 180 个 primary tasks
中，哪些题能够为“模型从 T1--T3 总结经验，并在新输入 T4--T6 上受益或受害”
提供可信证据。

它不是新的模型排行榜，也不会把 AP `Succeeded`、skill 被读取、标准解通过或
一次随机采样的分数单独当成 skill 有效的证明。

## 审计单位

- 30 个 family，每个 family 有严格有序的 T1--T6。
- T1--T3 是 learning tasks；同题最多三次 same-session verifier-backed
  repair，终态后反思并更新 skill。
- T3 后冻结环境级 library。
- T4--T6 是不同的新输入；每题 one-shot，不再更新 library。
- 180 题逐题出一行；涉及 transfer 的结论同时保留 family 级证据。

当官方 verifier、same-session 连续性和导出证据都完整时，反思阶段产生畸形
candidate、超时，或擅自修改即将销毁的 task workspace，属于该模型在该题上的
终态反思失败：记录为 `rejected`、禁止更新 library，并继续同环境后续题，不能
用它抹掉已经完成的 verifier 结果或中止其余 29 题。只有缺 verifier、丢失必需
session/trajectory、连续性无法证明或其他证据不完整时，才把 logical unit 记为
`unscoreable`。workspace mutation 仍须保存 before/after 快照与重算哈希，计入
第 1 项的失败证据；它不是 AP retry 的理由。

## 五项问题

1. **T1--T3 能否产生可复用经验？**
   检查 same-session 连续性、reflection 是否完成、skill patch 是否有效落库、
   后续不同输入是否实际读取对应版本。这里只能证明“生成并复用”；是否有帮助
   还必须看第 2--4 项。
2. **T4--T6 是否确实需要历史经验？**
   先检查所需概念是否已经完全写在当前题面；再看同模型同题 no-skill 是否失败。
   题面自足且 no-skill 稳定通过的题只能算现场执行题，不能算历史 transfer 题。
3. **正确 expert skill 是否提高结果？**
   `exact_curated` 只注入 task spec 指定的 primary/required skills。主要比较
   outcome pass；strict/process 作为次要诊断，防止源码形态检查主导结论。
4. **无关 skill 是否不能带来同样提升？**
   `shuffled_curated` 注入数量相同、但来自下一个 environment 的 curated skills，
   与目标 task 的 primary/required skills 完全不重叠。若 shuffled 与 exact
   同样有效，不能把提升归因于正确知识。
5. **失败来自模型/skill，还是 task/verifier？**
   静态检查 instruction、fixture、outcome/process verifier 和 reference solution；
   动态运行 checked-in `solution/solve.sh`；人工复核所有模型一致失败、
   exact/no-skill 翻转及 process-only failure。标准解通过是必要条件，不是充分条件。

## 动态条件

所有可比较条件必须固定 benchmark revision、模型、harness、timeout、任务输入和
AP attempt 语义：

| 条件 | T1--T3 | T4--T6 可见 library | 用途 |
| --- | --- | --- | --- |
| `self_generated` | 正常学习、反思、冻结 | 本 episode 生成的 frozen library | 被测能力 |
| `no_skill` | 不执行 | 空 | 题面自身难度下界 |
| `exact_curated` | 不执行 | task spec 指定的 curated 子集 | 正确知识正对照 |
| `shuffled_curated` | 不执行 | 等数量、跨 environment 的错误 curated 子集 | 无关知识负对照 |
| `reference_solution` | 不用模型 | 不用 skill | task/verifier 内部可解性 |

这里的“5”是五项检查，不是五道题。审计表始终有 180 行。为了给这些行补齐
证据，首轮矩阵有：`self_generated` 180 题，加上 T4--T6 的
`no_skill`、`exact_curated`、`shuffled_curated` 各 90 题，再加
`reference_solution` 180 题，共 630 个 task-condition cells。由于
`self_generated` 的 90 个 T1--T3 task 最多允许 3 次同 session 尝试，实际
task attempts 为 630--810。T1--T3 的第 2--4 项按协议记为“不适用”，而不是
被删除。

## 最终证据合并

下载并安全扫描全部 AP artifacts 后，先把四个模型条件标准化：

导出阶段仅保留顶层 canonical `trajectory.json`、`opencode.session.json` 和
solve/reflection streams；冗余的 `agent/opencode/xdg-data` SQLite 运行态在上传前
按 trial 计算 no-follow digest 后删除，并写入
`runtime_artifact_pruning_manifest.json`。审计器要求每个被删目录仍有哈希绑定的
canonical trajectory/session，避免用“清理敏感二进制”为由丢失科学证据。

```bash
python scripts/ap/build_t56_oracle_study.py \
  --raw-root /path/to/raw \
  --tasks-root benchmark/tasks \
  --skills-root benchmark/skills \
  --inventory /path/to/watcher/inventory.json \
  --output-dir /path/to/analysis
```

全 180 题 reference audit 用 `--expected-tiers 1,2,3,4,5,6` 聚合。最终调用
`build_audit.py` 时传入 `--v11-full-evidence`、固定模型和 benchmark commit，
并加 `--require-complete-current`。这个严格模式会检查：90 条当前 T1--T3
learning records、四个条件各 90 条 T4--T6 records、24 个完整环境 episode、
180 条 reference records、空 no-skill、精确 expert 注入、等量零重叠 shuffled
注入，以及 freeze 和 lifecycle 证据；少一格就拒绝生成“已完成”结论。
完整的 reference record 不等于 reference 必须通过。失败的官方解正是第 5 项
task/verifier 缺陷证据，聚合器会保留其 score、exception 和组件结果，并让该题
进入语义复查队列，而不会把整份报告当成缺失。

`exact_curated` 不是 solution manual。仓库中的 curated skills 本来就刻意留下
T2/T3 acquisition gap，所以 exact 失败不能自动判题坏。

## 首轮与复核规则

首轮先对全部 90 个 T4--T6 做一次四条件配对，用于筛查而非总体因果估计。
随后仅复跑下列不稳定或关键题，目标是每个条件取得 3 个有效样本：

- no-skill 与 self-generated 或 exact 的 outcome 不同；
- exact 与 shuffled 的 outcome 不同；
- 两个强模型结论相反；
- 模型一致 outcome fail；
- outcome pass 但 process fail；
- AP/transport/timeout 失败（该样本不计入科学尝试）。

任务级建议标签：

- `transfer_positive`：no-skill 多数失败，self-generated 多数通过，生成 skill
  被实际读取，且 shuffled 多数失败；
- `expert_sensitive`：no-skill 多数失败，exact 多数通过，shuffled 多数失败；
- `low_skill_demand`：no-skill 多数通过；
- `wrong_skill_insensitive`：shuffled 与 exact 同样通过，或 shuffled 也救回；
- `generation_gap`：exact 通过但 self-generated 失败；
- `task_or_verifier_defect`：存在可复现的题面矛盾、不可满足约束、未声明任意
  tie-break，或 verifier 拒绝语义有效实现；
- `model_execution_gap`：reference 通过、合同无已知缺陷，且所有 skill 条件均失败；
- `insufficient_evidence`：缺条件、缺轨迹、协议不等价或只有一次关键随机翻转。

## 当前证据边界

- v1.0 有 Qwen 3.7 Max、S1 Fable、Opus 4.8 的完整 self-generated 180/180
  轨迹，以及 Qwen/Fable 的 T4--T6 no-skill/exact/curated-all 结果；这些只能用作
  旧版问题定位，不能替代 v1.1 的 matched 结论。
- v1.1@12 的 T4--T6 reference solution 已在真实容器中 90/90 strict pass。
- v1.1@12 目前只有 Opus E6 完成 matched self-generated vs no-skill：outcome
  8/15 对 6/15，逐题 2 次 rescue、0 次 harm；这不能外推到其他五个环境。
- v1.1 尚缺全六环境的四条件矩阵，尤其缺严格的 `shuffled_curated`。

因此，在四条件矩阵和关键题复跑完成前，最终报告必须把缺失证据显示为
`insufficient_evidence`，不能自动把 180 题判为保留或淘汰。
