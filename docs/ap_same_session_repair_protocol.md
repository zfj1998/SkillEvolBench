# AP 同会话多次修复协议

更新日期：2026-07-21

## 目标

T1-T3 的每个学习任务允许模型在同一个 OpenCode session 中，根据有限的
verifier 反馈修复当前任务。通过后立即停止；一直失败时最多运行 AP 参数
`learning_max_attempts` 指定的次数。终止后仍由同一个 session 总结 skill。

T1、T2、T3 彼此使用不同 session，只通过 environment-scoped skill library
传递经验。T4-T6、replay 和 oracle shadow 始终只有一次尝试，且不得更新
skill library。

## AP 参数

Agent-Hub 模板参数：

```yaml
learning_max_attempts: 3
```

允许范围为 1-5。AP 将其注入为 `LEARNING_MAX_ATTEMPTS`。值为 1 时退化为
原来的单次 solve + 单次 reflection 协议。

## 单个学习任务的状态机

```text
solve attempt 1
  -> isolated verifier
  -> failed and budget remains
  -> bounded feedback user turn in the same session
  -> repair /root/task
  -> snapshot repaired task
  -> fresh isolated verifier
  -> ...
  -> pass or budget exhausted
  -> final skill-reflection user turn in the same session
  -> host validates/applies skill candidate once
```

每次 verifier 都使用新的隔离容器。隐藏测试和原始 verifier 日志不会挂载到
agent 容器；agent 只收到由 `feedback_level` 控制的有限反馈。repair 阶段允许
修改 `/root/task`，最终 skill reflection 阶段重新禁止修改任务代码。

## 同 session 证明

每个 repair turn 都必须满足：

- OpenCode adapter、phase stream、session export 和 ATIF trajectory 的 session ID
  完全一致；
- 新 trajectory/session export 以前一阶段为严格前缀；
- agent 容器 identity 在 stop/restart 前后不变；
- 下一次 verifier 使用的 task snapshot 与 repair 后下载快照 hash 一致。

任何证明失败都会使 trial unscoreable，而不是按 reward=0 继续。

## 审计产物

每个发生 repair 的 trial 新增：

```text
same-session-attempts/
  attempt-01/
    official-verifier/
    repair_prompt.md
    repair_feedback.json
    outcome.json
    trajectory.before-repair.json
    trajectory.after-repair.json
    opencode.session.before-repair.json
    opencode.session.after-repair.json
    opencode.repair.jsonl
    task.before-repair/
    task.after-repair/
    repair_result.json
```

后续失败轮次使用 `attempt-02/`。终止轮次的 verifier、最终 solve 前缀、完整
reflection 轨迹和 skill candidate 仍保存在 `self-reflection-audit/`。

## 指标

- `learning_attempts_total`
- `repair_attempts_total`
- `initial_learning_pass_count`
- `terminal_learning_pass_count`
- `repaired_to_pass_count`
- `same_task_repair_success_rate`
- `n_all_attempts_same_session_verified`

主 benchmark 分数仍来自冻结 skill library 后 T4-T6 的单次尝试表现。多轮修复
指标只描述 T1-T3 的同任务恢复能力。

## 当前验证

- SkillEvolBench 全量测试：273 passed。
- 最新同会话/AP 参数针对性测试：124 passed。
- Agent-Hub `task/skillevolbench` 模板测试：26 passed。
- 已验证两次连续 repair 的 trajectory 单调前缀和 session ID 一致。
- 尚需使用新 source bundle 和 Agent-Hub 模板提交一次 AP T1-T6 family smoke。
