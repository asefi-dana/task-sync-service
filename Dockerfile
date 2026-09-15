FROM python:3.11-slim AS builder

ARG CORE_REF=main

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 --branch "${CORE_REF}" https://github.com/NousResearch/hermes-agent.git /opt/app-core

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -e "/opt/app-core[messaging,cron,cli,pty]"
RUN pip install --no-cache-dir \
  "fastapi>=0.104.0" \
  "uvicorn[standard]>=0.24.0" \
  "httpx>=0.25.0" \
  "requests>=2.28.0"

FROM python:3.11-slim

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    jq \
    tini \
  && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:${PATH}" \
  PYTHONUNBUFFERED=1 \
  HERMES_HOME=/data/.service_state \
  HOME=/data \
  PORT=8080

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/app-core /opt/app-core

WORKDIR /app
COPY scripts/run.sh /app/scripts/run.sh
RUN chmod +x /app/scripts/run.sh

COPY scripts/health_server.py /app/scripts/health_server.py

ENTRYPOINT ["tini", "--"]
CMD ["/app/scripts/run.sh"]
