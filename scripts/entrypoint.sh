#!/usr/bin/env bash
set -euo pipefail

export DISPLAY=${DISPLAY:-:99}
export HOME=/home/appuser
APP_PORT=${APP_PORT:-4040}
SCREEN_WIDTH=${SCREEN_WIDTH:-1600}
SCREEN_HEIGHT=${SCREEN_HEIGHT:-900}
STATE_DIR=${STATE_DIR:-/data/state}
LOG_DIR=${LOG_DIR:-/data/logs}

mkdir -p /data/profile "$STATE_DIR" "$LOG_DIR"
chown -R appuser:appuser /data /app /home/appuser

cleanup() {
  pkill -TERM -P $$ || true
}
trap cleanup EXIT INT TERM

cd /app
su -s /bin/bash appuser -c "Xvfb $DISPLAY -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x24 -ac +extension GLX +render -noreset" >>"$LOG_DIR/xvfb.log" 2>&1 &
sleep 1
su -s /bin/bash appuser -c "cd /app && uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT}" >>"$LOG_DIR/app.log" 2>&1 &
su -s /bin/bash appuser -c "cd /app && /app/scripts/launch_chromium.sh" >>"$LOG_DIR/browser-launcher.log" 2>&1 &

wait -n
exit $?
