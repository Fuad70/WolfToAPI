FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    APP_PORT=4040 \
    AGENT_WS_PORT=8765 \
    NOVNC_PORT=6080 \
    BROWSER_PROFILE_DIR=/data/profile \
    STATE_DIR=/data/state \
    LOG_DIR=/data/logs

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    curl \
    dumb-init \
    fluxbox \
    novnc \
    procps \
    tini \
    websockify \
    x11vnc \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash appuser

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY extension ./extension
COPY scripts ./scripts
COPY static ./static
COPY README.md PROJECT_ANALYSIS.md ./

RUN chmod +x /app/scripts/*.sh && mkdir -p /data/profile /data/state /data/logs && chown -R appuser:appuser /app /data

EXPOSE 4040 6080

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
  CMD curl -fsS http://127.0.0.1:4040/health >/dev/null || exit 1

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/app/scripts/entrypoint.sh"]
