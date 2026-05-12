#!/usr/bin/env bash
set -euo pipefail

export HOME=/home/appuser
export DISPLAY=${DISPLAY:-:99}
PROFILE_DIR=${BROWSER_PROFILE_DIR:-/data/profile}
LOG_DIR=${LOG_DIR:-/data/logs}
FLOW_URL=${FLOW_START_URL:-https://labs.google/fx/tools/flow}
CHROMIUM_BIN=${CHROMIUM_BIN:-/usr/bin/chromium}
EXT_DIR=/app/extension

mkdir -p "$PROFILE_DIR" "$LOG_DIR"

while true; do
  "$CHROMIUM_BIN" \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    --password-store=basic \
    --disable-dev-shm-usage \
    --disable-features=Translate,OptimizationHints,MediaRouter \
    --disable-extensions-except="$EXT_DIR" \
    --load-extension="$EXT_DIR" \
    --start-maximized \
    "$FLOW_URL" >>"$LOG_DIR/chromium.log" 2>&1 || true
  sleep 2
done
