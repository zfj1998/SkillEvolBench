<div align="center">
  <h1>SkillEvolBench: Benchmarking the Evolution from Episodic Experience to Procedural Skills</h1>

  <p>
    <em>Can one-off task experience become reusable instructions that future agents can follow?</em>
  </p>

  <p>
    <a href="https://arxiv.org/abs/2605.24117"><img alt="arXiv" src="asset/badge-arxiv.svg" /></a> <a href="https://arxiv.org/pdf/2605.24117"><img alt="Paper PDF" src="asset/badge-paper.svg" /></a> <a href="https://huggingface.co/papers/2605.24117"><img alt="Hugging Face Page" src="asset/badge-huggingface.svg" /></a> <a href="https://skillevolbench.github.io/"><img alt="Project Page" src="asset/badge-project.svg" /></a>
  </p>

  <p>
    <sub><strong>
      Yingtie&nbsp;Lei<sup>1,*</sup>, Zhongwei&nbsp;Wan<sup>1,*</sup>, Jiankun&nbsp;Zhang<sup>2</sup>, Samiul&nbsp;Alam<sup>1</sup>, Zixuan&nbsp;Zhong<sup>3</sup>, Peizhou&nbsp;Huang<sup>4</sup>, Xin&nbsp;Wang<sup>1</sup><br />
      Jingxuan&nbsp;Zhang<sup>1</sup>, Donghao&nbsp;Zhou<sup>5</sup>, Yunta&nbsp;Hsieh<sup>4</sup>, Zhihao&nbsp;Dou<sup>6</sup>, Hui&nbsp;Shen<sup>4</sup>, Yan&nbsp;Xu<sup>7</sup>, Dimitrios&nbsp;Dimitriadis<sup>7</sup>, Tuo&nbsp;Zhang<sup>7</sup>, Mi&nbsp;Zhang<sup>1</sup>
    </strong></sub>
  </p>

  <p>
    <sub>
      <sup>1</sup>The Ohio State University,
      <sup>2</sup>The University of Chicago,
      <sup>3</sup>University College London,
      <sup>4</sup>University of Michigan,<br />
      <sup>5</sup>The Chinese University of Hong Kong,
      <sup>6</sup>Case Western Reserve University,
      <sup>7</sup>Amazon<br />
      <sup>*</sup>Equal contribution
    </sub>
  </p>

  <p><strong>SkillEvolBench Team</strong></p>

  <p>
    <sub>
      Correspondence: Tuo Zhang <a href="mailto:tuozhang@amazon.com">tuozhang@amazon.com</a>,
      Mi Zhang <a href="mailto:mizhang.1@osu.edu">mizhang.1@osu.edu</a>
    </sub>
  </p>

  <p>
    <img src="asset/osu2.png" alt="The Ohio State University" height="42" />
    &nbsp;&nbsp;&nbsp;&nbsp;
    <img src="asset/amazon.png" alt="Amazon Science" height="38" />
  </p>
</div>

## 📝 Abstract

Large language model (LLM) agents accumulate rich episodic trajectories while solving real-world tasks, but it remains unclear whether such experience can be distilled into reusable procedural skills. We introduce SkillEvolBench, a diagnostic benchmark for evaluating this step from experience reuse to skill formation. It contains 180 tasks across six real-world agent environments, organized into role-conditioned task families with shared latent procedures. Agents learn from acquisition tasks, update an external skill library using compacted trajectories and verifier feedback, and then face frozen deployment tasks testing context shift, adversarial shortcuts, and composition.

By comparing self-generated and curated-start skill evolution against no-skill and raw-trajectory controls, SkillEvolBench separates procedural abstraction from base capability, curated prior knowledge, and direct reuse of episodic traces. Across ten model configurations and three agent harnesses, we find that current agents often adapt locally but rarely form robust reusable skills. Skill-based conditions can improve acquisition or replay, and individual models sometimes gain on specific deployment axes, but these gains are unstable under frozen deployment.

Raw-trajectory reuse frequently outperforms distilled skills, suggesting that current abstraction procedures discard contextual and procedural cues that remain useful for future tasks. Capacity and cost analyses further show that writing more skills or larger Tier-3 resource libraries is not sufficient: additional updates can improve coverage while introducing episode-specific drift and procedural clutter. These findings position SkillEvolBench as a testbed for measuring when one-off experience becomes durable procedural knowledge rather than task-local memory.

## 🗂️ GitHub Repo Layout

| Path | Purpose |
| --- | --- |
| `benchmark/tasks/` | 180 benchmark tasks with task metadata, instructions, environments, and validation assets. |
| `benchmark/skills/` | Curated seed skills used by curated-skill baselines. |
| `configs/baselines/` | Baseline YAMLs. Select with `--baseline-name <name>`. |
| `configs/models/` | Model/provider presets for Azure OpenAI, AWS Bedrock Claude, Gemini, and Kimi-style endpoints. Select with `--model-yaml`. |
| `configs/strategies/` | Runtime strategies, mainly `chain` and `chain_tier3`. Most baselines choose this automatically. |
| `configs/env_orders.yaml` | Deterministic environment orders for seeds `A`, `B`, and `C`. |
| `skillevolbench/` | Core benchmark engine: scheduler, runtime, stores, retrieval, prompting, metrics, schemas, and Harbor hooks. |
| `agents_port/` | Preinstalled-agent adapter layer for `codex`, `opencode`, `claude-code`, `gemini-cli`, and `kimi-cli`. |
| `scripts/run.py` | Main single-run launcher. Use this for individual reproductions. |
| `scripts/launch_main_experiment.py` | Batch launcher for canonical baselines. |
| `scripts/launch_multi_model.py` | Batch launcher for baseline × model sweeps. |
| `scripts/validate_configs.py` | Validates YAML configs against schemas. |
| `scripts/validate_assets.py` | Validates benchmark task and skill assets. |
| `scripts/preflight.py` | Checks runtime readiness before expensive model calls. |
| `scripts/summarize.py` | Summarizes a completed run. |
| `docker/agent-build/` | Builds the Harbor task image `agent-runtime:latest`. |
| `workspace/runs/` | Local generated run outputs. Do not commit. |
| `asset/` | README/project visual assets. |

## 🧩 Benchmark Structure

SkillEvolBench uses a fixed stratified design:

```text
6 environments × 5 latent skill families × 6 tasks = 180 tasks
```

For each latent skill family, `T1-T3` are learning/acquisition tasks and `T4-T6` are frozen evaluation tasks:

| Task | Role | Purpose |
| --- | --- | --- |
| `T1` | learning | canonical first encounter |
| `T2` | learning | enriched follow-up |
| `T3` | learning | variant acquisition case |
| `T4` | evaluation | context shift |
| `T5` | evaluation | adversarial variant |
| `T6` | evaluation | skill composition |

## ⚙️ Installation

Python 3.12 is recommended.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m pip install litellm boto3 jinja2 pandas matplotlib
```

Install Harbor and build the task runtime image:

```bash
python -m pip install git+https://github.com/harbor-framework/harbor.git
bash docker/agent-build/build.sh
docker image inspect agent-runtime:latest
```

## 🔐 API Keys and Provider Setup

Create a local credential file. It is ignored by Git.

```bash
touch .harbor-agents.env
chmod 600 .harbor-agents.env
```

Fill only the providers you plan to run:

```bash
# Azure OpenAI / Codex presets
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/openai/v1
AZURE_OPENAI_API_KEY=<your-azure-openai-key>
# Optional if your endpoint requires it:
# AZURE_OPENAI_API_VERSION=<api-version>

# AWS Bedrock Claude presets
AWS_BEARER_TOKEN_BEDROCK=<your-bedrock-bearer-token>
AWS_REGION=us-east-1
CLAUDE_CODE_USE_BEDROCK=1

# Gemini direct presets
GEMINI_API_KEY=<your-gemini-api-key>

# Kimi / OpenAI-compatible Mantle endpoint
KIMI_BEDROCK_BASE_URL=<your-openai-compatible-base-url>
KIMI_BEDROCK_API_KEY=<your-kimi-key>
```

Load credentials in the same shell before launching runs:

```bash
set -a
source .harbor-agents.env
set +a
```

Check without printing secret values:

```bash
python -c "import os; [print(k, bool(os.getenv(k))) for k in ['AZURE_OPENAI_ENDPOINT','AZURE_OPENAI_API_KEY','AWS_BEARER_TOKEN_BEDROCK','AWS_REGION','GEMINI_API_KEY','KIMI_BEDROCK_BASE_URL','KIMI_BEDROCK_API_KEY']]"
```

### Provider notes

| Provider family | Presets | Required env vars | Notes |
| --- | --- | --- | --- |
| Azure OpenAI Codex | `gpt-5.2-codex`, `gpt-5.3-codex`, `gpt-5.4` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` | The preset `agent_model_name` must match your Azure deployment name. Edit the YAML if your deployment differs. |
| AWS Bedrock Claude | `claude-sonnet-*`, `claude-opus-*` | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, `CLAUDE_CODE_USE_BEDROCK=1` | Uses Bedrock inference-profile IDs such as `us.anthropic...`. Your AWS account must have model access. |
| Gemini direct | `gemini-*` | `GEMINI_API_KEY` | Included for convenience; adapt the YAML if your Gemini CLI setup differs. |
| Kimi/Mantle | `kimi-*` | `KIMI_BEDROCK_BASE_URL`, `KIMI_BEDROCK_API_KEY` | Requires an OpenAI-compatible endpoint. |

The paper configuration here uses **Azure OpenAI** for Codex-style models and **AWS Bedrock Claude** for Claude. If you use direct OpenAI/Anthropic API keys instead, add a new YAML under `configs/models/` and set the right `provider`, `harbor_agent_name`, `agent_model_name`, `agent_env`, and `host_litellm` fields for your endpoint.

## ✅ Validate Before Running

```bash
python -m scripts.validate_configs
python -m scripts.validate_assets
python -m scripts.preflight
python -m scripts.run --baseline-name no_skill --order-seed A --dry-run
```

A healthy dry run schedules 180 tasks and does not call any model API.

For a stricter check including Harbor and Docker image readiness:

```bash
python -m scripts.preflight --strict
```

## 🚀 Run One Benchmark

General pattern:

```bash
python -m scripts.run \
  --baseline-name <baseline_name> \
  --model-yaml configs/models/<model_preset>.yaml \
  --order-seed A
```

Azure OpenAI example:

```bash
python -m scripts.run \
  --baseline-name no_skill \
  --model-yaml configs/models/gpt-5.4.yaml \
  --order-seed A
```

AWS Bedrock Claude example:

```bash
python -m scripts.run \
  --baseline-name selfgen_experience_always \
  --model-yaml configs/models/claude-sonnet-4.6.yaml \
  --order-seed A
```

Use `--run-id` for a stable output directory:

```bash
python -m scripts.run \
  --baseline-name raw_trajectory_rag \
  --model-yaml configs/models/gpt-5.4.yaml \
  --order-seed A \
  --run-id rawrag_gpt54_seedA
```

## 📊 Paper Baselines

Canonical baselines are defined in `skillevolbench/baselines/policy.py`.

| Baseline | Config name | What it tests |
| --- | --- | --- |
| No Skill | `no_skill` | Bare agent with no skills, memory, or trajectory retrieval. |
| Raw Trajectory RAG | `raw_trajectory_rag` | Retrieves same-family raw learning trajectories instead of distilled skills. |
| Self-Generated Zero-Shot | `selfgen_zero_shot` | Creates skills before experience from task/family context. |
| Self-Generated Experience | `selfgen_experience_always` | Induces skills from experience and revises on every learning trial. |
| Curated Static | `curated_static` | Uses curated seed skills without revision. |
| Curated + Revision | `curated_with_revision_always` | Starts from curated skills and revises on every learning trial. |

Run the full canonical ladder for one model:

```bash
MODEL=configs/models/gpt-5.4.yaml
BASELINES=(
  no_skill
  raw_trajectory_rag
  selfgen_zero_shot
  selfgen_experience_always
  curated_static
  curated_with_revision_always
)

for BASELINE in "${BASELINES[@]}"; do
  python -m scripts.run \
    --baseline-name "$BASELINE" \
    --model-yaml "$MODEL" \
    --order-seed A
done
```

Or use the multi-run launcher after inspecting the plan:

```bash
python -m scripts.launch_multi_model \
  --baselines no_skill,raw_trajectory_rag,selfgen_zero_shot,selfgen_experience_always,curated_static,curated_with_revision_always \
  --models gpt-5.4 \
  --order-seed A \
  --max-workers 1 \
  --dry-run
```

Remove `--dry-run` to execute.

## 🧪 Ablation Baselines

| Ablation | Config name |
| --- | --- |
| Failure-only self-generated revision | `selfgen_experience` |
| Failure-only curated revision | `curated_with_revision` |
| Required Tier-3 skill files, self-generated | `selfgen_experience_always_with_tier3` |
| Required Tier-3 skill files, curated | `curated_with_revision_always_with_tier3` |

Run an ablation like any other baseline:

```bash
python -m scripts.run \
  --baseline-name selfgen_experience \
  --model-yaml configs/models/gpt-5.4.yaml \
  --order-seed A
```

## 🤖 Model Presets

| Model preset | Provider route | Credentials |
| --- | --- | --- |
| `gpt-5.2-codex.yaml` | Azure OpenAI Codex CLI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` |
| `gpt-5.3-codex.yaml` | Azure OpenAI Codex CLI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` |
| `gpt-5.4.yaml` | Azure OpenAI Codex CLI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` |
| `claude-sonnet-4.5.yaml` | AWS Bedrock Claude Code | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION` |
| `claude-sonnet-4.6.yaml` | AWS Bedrock Claude Code | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION` |
| `claude-opus-4.5.yaml` | AWS Bedrock Claude Code | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION` |
| `claude-opus-4.6.yaml` | AWS Bedrock Claude Code | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION` |
| `gemini-2.5-pro.yaml` | Gemini CLI direct | `GEMINI_API_KEY` |
| `gemini-3-flash.yaml` | Gemini CLI direct | `GEMINI_API_KEY` |
| `gemini-3.1-pro.yaml` | Gemini CLI direct | `GEMINI_API_KEY` |
| `kimi-2-thinking.yaml` | OpenAI-compatible Mantle/Kimi | `KIMI_BEDROCK_BASE_URL`, `KIMI_BEDROCK_API_KEY` |
| `kimi-2.5.yaml` | OpenAI-compatible Mantle/Kimi | `KIMI_BEDROCK_BASE_URL`, `KIMI_BEDROCK_API_KEY` |

Inspect a preset before editing:

```bash
sed -n '1,120p' configs/models/gpt-5.4.yaml
```

## 📦 Outputs

Runs are written to:

```text
workspace/runs/<run_id>/
```

Key files:

| Path | Meaning |
| --- | --- |
| `config.json` | Frozen run configuration. |
| `reports/full_report.json` | Main metrics report. |
| `stores/replay/` | Per-task replay records. |
| `stores/events/` | Runtime event logs. |
| `stores/retrieval/` | Retrieval traces when enabled. |
| `runtime/` | Per-task execution workdirs. |
| `harbor-job/` | Harbor job artifacts. |

Summarize a run:

```bash
python -m scripts.summarize workspace/runs/<run_id>
```

Find recent runs:

```bash
ls -lt workspace/runs | head
```

## 🛠️ Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Please set an Auth method... GEMINI_API_KEY` | `.harbor-agents.env` was not sourced or `GEMINI_API_KEY` is missing. | Source `.harbor-agents.env` in the same shell. |
| `No module named 'harbor'` | Harbor SDK is missing. | `python -m pip install git+https://github.com/harbor-framework/harbor.git` |
| `agent-runtime:latest` missing | Docker image has not been built. | `bash docker/agent-build/build.sh` |
| Azure 401/403 | Endpoint/key/deployment mismatch. | Check `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and `agent_model_name`. |
| Bedrock model identifier error | Region/profile mismatch. | Use the `us.anthropic...` model IDs in `configs/models/claude-*.yaml` and set `AWS_REGION`. |

## 📚 Citation

```bibtex
@article{lei2026skillevolbench,
  title={SkillEvolBench: Benchmarking the Evolution from Episodic Experience to Procedural Skills},
  author={Lei, Yingtie and Wan, Zhongwei and Zhang, Jiankun and Alam, Samiul and Zhong, Zixuan and Huang, Peizhou and Wang, Xin and Zhang, Jingxuan and Zhou, Donghao and Hsieh, Yunta and others},
  journal={arXiv preprint arXiv:2605.24117},
  year={2026}
}
```
