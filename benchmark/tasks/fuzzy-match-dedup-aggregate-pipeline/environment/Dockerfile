FROM agent-runtime:latest

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && ln -sf /usr/bin/pip3 /usr/local/bin/pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /root/task

COPY . /root/task/

RUN python -m pip install --no-cache-dir -r /root/task/requirements.txt \
    && rm -rf /root/task/tests /root/task/solution \
    && rm -f /root/task/Dockerfile \
    && mkdir -p /logs/verifier /logs/agent
