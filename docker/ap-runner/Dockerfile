ARG HARBOR_RUNNER_IMAGE=code-agi-sg-docker-registry-vpc.ap-southeast-1.cr.aliyuncs.com/eflops/harbor-repo:harbor-main-latest
ARG SEVB_BENCHMARK_REVISION=unknown
FROM ${HARBOR_RUNNER_IMAGE}

ARG SEVB_BENCHMARK_REVISION

USER root
WORKDIR /opt/skillevolbench

COPY . /opt/skillevolbench

RUN python3 -m pip install --no-cache-dir -e '.[dev]' \
    && python3 -m pip install --no-cache-dir litellm boto3 jinja2 pandas matplotlib \
    && printf '%s\n' "$SEVB_BENCHMARK_REVISION" > .skillevolbench-revision

ENV PYTHONPATH=/opt/skillevolbench \
    PYTHONUNBUFFERED=1 \
    SEVB_BENCHMARK_REVISION=$SEVB_BENCHMARK_REVISION
