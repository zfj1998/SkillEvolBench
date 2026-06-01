FROM agent-runtime:latest

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=development

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /root/task

COPY . /root/task/

RUN rm -rf /root/task/tests /root/task/solution \
    && rm -f /root/task/Dockerfile \
    && mkdir -p /logs/verifier /logs/agent
