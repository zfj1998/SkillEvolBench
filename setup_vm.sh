#!/usr/bin/env bash
# SkillEvolBench: end-to-end VM setup (Ubuntu + Docker only).
#
# Usage:
#   bash setup_vm.sh                       # full setup
#   ENV_NAME=myenv bash setup_vm.sh        # override conda env name (default: bench)
#   SKIP=docker,image bash setup_vm.sh     # skip steps (csv: system,docker,conda,deps,image)
#
# What this installs (in order):
#   1. system: git, curl, build tools, jq, ripgrep  (Ubuntu apt)
#      -- NOT awscli; Bedrock auth uses AWS_BEARER_TOKEN_BEDROCK + litellm
#   2. Docker (skips if already installed)
#   3. Miniconda (skips if already on PATH)
#   4. uv (fast pip)
#   5. conda env "bench" (python=3.12) + Python deps
#   6. agent-runtime:latest Docker image
#
# What you still need to do MANUALLY after this script:
#   - Place .harbor-agents.env at repo root (with API keys)
#   - Verify provider access: Bedrock model grants, Azure deployment, Gemini key
#   - Source the env: set -a && source .harbor-agents.env && set +a
#   - Run smoke test (instructions printed at end)

set -euo pipefail

# -------------------- knobs --------------------
REPO_DIR="${REPO_DIR:-$(pwd)}"
ENV_NAME="${ENV_NAME:-bench}"
SKIP="${SKIP:-}"
HARBOR_INSTALL_CMD="${HARBOR_INSTALL_CMD:-pip install git+https://github.com/harbor-framework/harbor.git}"

skip()  { [[ ",$SKIP," == *",$1,"* ]]; }
log()   { printf "\n\033[1;36m[setup_vm]\033[0m %s\n" "$*"; }
fail()  { printf "\n\033[1;31m[FAIL]\033[0m %s\n" "$*" >&2; exit 1; }

log "Setup start: REPO_DIR=$REPO_DIR  ENV_NAME=$ENV_NAME"

# -------------------- 1. system packages (Ubuntu) --------------------
if skip system; then
    log "Layer 1/6: SKIP system packages"
else
    log "Layer 1/6: system packages (Ubuntu apt)"
    sudo apt-get update
    # Note: no awscli -- Bedrock auth uses AWS_BEARER_TOKEN_BEDROCK env var
    # via litellm; no `aws` CLI invocations anywhere in the codebase. The
    # apt `awscli` package was also dropped on Ubuntu 24.04 (noble) so this
    # avoids "Package 'awscli' has no installation candidate" failures.
    sudo apt-get install -y --no-install-recommends \
        curl wget git ca-certificates xz-utils \
        build-essential \
        jq ripgrep \
        python3 python3-pip python3-venv
fi

# -------------------- 2. Docker --------------------
if skip docker; then
    log "Layer 2/6: SKIP Docker"
elif command -v docker >/dev/null 2>&1; then
    log "Layer 2/6: Docker already installed ($(docker --version))"
else
    log "Layer 2/6: installing Docker"
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    log "  NOTE: log out + back in (or run 'newgrp docker') for docker group to apply"
fi

# -------------------- 3. Miniconda --------------------
if skip conda; then
    log "Layer 3/6: SKIP Miniconda"
elif command -v conda >/dev/null 2>&1; then
    log "Layer 3/6: conda already installed ($(conda --version))"
    # shellcheck disable=SC1091
    eval "$(conda shell.bash hook)"
else
    log "Layer 3/6: installing Miniconda to \$HOME/miniconda3"
    mkdir -p "$HOME/miniconda3"
    curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
        -o /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -u -p "$HOME/miniconda3"
    rm /tmp/miniconda.sh
    eval "$($HOME/miniconda3/bin/conda shell.bash hook)"
    conda init bash
fi

# -------------------- 4. uv --------------------
if skip deps; then
    log "Layer 4/6: SKIP uv"
elif command -v uv >/dev/null 2>&1; then
    log "Layer 4/6: uv already installed ($(uv --version))"
else
    log "Layer 4/6: installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# -------------------- 5. conda env + python deps --------------------
if skip deps; then
    log "Layer 5/6: SKIP python deps"
else
    log "Layer 5/6: conda env '$ENV_NAME' (python=3.12)"
    if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
        conda create -n "$ENV_NAME" python=3.12 -y
    fi
    # shellcheck disable=SC1091
    conda activate "$ENV_NAME"

    log "Layer 5/6: project + extras"
    if [[ -f "$REPO_DIR/pyproject.toml" ]]; then
        uv pip install -e "$REPO_DIR[dev]"
    else
        fail "pyproject.toml not found in $REPO_DIR; cd into repo root before running"
    fi

    log "Layer 5/6: extras not in pyproject (litellm / boto3 / data / matplotlib / jinja2)"
    # boto3: litellm Bedrock provider falls back to boto3 SigV4 on some
    # code paths (list models, embeddings) even when AWS_BEARER_TOKEN_BEDROCK
    # is set. Without it litellm raises ImportError on the first such call.
    uv pip install litellm boto3 jinja2 matplotlib pandas

    log "Layer 5/6: harbor SDK"
    eval "$HARBOR_INSTALL_CMD" || fail "harbor install failed: $HARBOR_INSTALL_CMD"
fi

# -------------------- 6. agent-runtime image --------------------
if skip image; then
    log "Layer 6/6: SKIP agent-runtime build"
elif ! command -v docker >/dev/null 2>&1; then
    log "Layer 6/6: SKIP image (docker not on PATH)"
elif [[ ! -f "$REPO_DIR/docker/agent-build/build.sh" ]]; then
    log "Layer 6/6: SKIP image (build.sh not in $REPO_DIR/docker/agent-build/)"
else
    log "Layer 6/6: building agent-runtime:latest (~10-15 min, one-time)"
    bash "$REPO_DIR/docker/agent-build/build.sh"
    docker image inspect agent-runtime:latest >/dev/null \
        && log "  agent-runtime:latest verified OK"
fi

# -------------------- done --------------------
log "DONE"
cat <<EOF

================================================================
  NEXT STEPS (manual; run from $REPO_DIR with conda env active)
================================================================
  1. Place .harbor-agents.env at repo root, chmod 600 .harbor-agents.env
     (must contain: AWS_BEARER_TOKEN_BEDROCK / AWS_REGION /
      AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY /
      GEMINI_API_KEY / KIMI_BEDROCK_BASE_URL / KIMI_BEDROCK_API_KEY)

  2. Activate + source env vars:
       conda activate $ENV_NAME
       set -a && source .harbor-agents.env && set +a

  3. Verify install:
       skillevolbench validate-configs                # expect: 12/10 baselines, 2/2 strategies
       python -m scripts.preflight --strict            # all checks PASS
       python -m pytest tests/ -q                      # ~351 passed

  4. Smoke test 1 trial (~5 hours, no SkillAuthor LLM cost):
       python -m scripts.run \\
           --baseline-name no_skill \\
           --model-yaml configs/models/claude-sonnet-4.6.yaml \\
           --order-seed A \\
           --run-id smoke-test
       cat workspace/runs/smoke-test/reports/full_report.json | jq .task_success

  5. Real batch (10 baselines x 10 models x 3 reps = 300 runs):
       SERVER=server-1 REPS=3 MAX_PARALLEL=10 bash scripts/batch_run.sh
       # see scripts/batch_run.sh for SERVER groupings (server-1/2/3/all)
================================================================
EOF
