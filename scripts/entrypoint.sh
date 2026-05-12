#!/usr/bin/env bash
set -euo pipefail

export DISPLAY=${DISPLAY:-:99}
export HOME=/home/appuser
SCREEN_WIDTH=${SCREEN_WIDTH:-1600}
SCREEN_HEIGHT=${SCREEN_HEIGHT:-900}
STATE_DIR=${STATE_DIR:-/data/state}
LOG_DIR=${LOG_DIR:-/data/logs}
VNC_PASS_FILE="$STATE_DIR/vnc.pass"

mkdir -p /data/profile "$STATE_DIR" "$LOG_DIR"
chown -R appuser:appuser /data /app /home/appuser

if [ -z "${VNC_PASSWORD:-}" ]; then
  echo "VNC_PASSWORD is required" >&2
  exit 1
fi

x11vnc -storepasswd "$VNC_PASSWORD" "$VNC_PASS_FILE" >/dev/null
chown appuser:appuser "$VNC_PASS_FILE"

cleanup() {
  pkill -TERM -P $$ || true
}
trap cleanup EXIT INT TERM

cd /app
su -s /bin/bash appuser -c "Xvfb $DISPLAY -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x24 -ac +extension GLX +render -noreset" >>"$LOG_DIR/xvfb.log" 2>&1 &
sleep 1
su -s /bin/bash appuser -c "fluxbox" >>"$LOG_DIR/fluxbox.log" 2>&1 &
su -s /bin/bash appuser -c "x11vnc -display $DISPLAY -rfbport 5900 -shared -forever -usepw -rfbauth $VNC_PASS_FILE" >>"$LOG_DIR/x11vnc.log" 2>&1 &
su -s /bin/bash appuser -c "websockify --web=/usr/share/novnc/ 6080 localhost:5900" >>"$LOG_DIR/novnc.log" 2>&1 &
su -s /bin/bash appuser -c "cd /app && uvicorn app.main:app --host 0.0.0.0 --port 8080" >>"$LOG_DIR/app.log" 2>&1 &
su -s /bin/bash appuser -c "cd /app && /app/scripts/launch_chromium.sh" >>"$LOG_DIR/browser-launcher.log" 2>&1 &

wait -n
exit $?
