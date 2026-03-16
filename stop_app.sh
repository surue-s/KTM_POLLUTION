#!/usr/bin/env bash
set -euo pipefail

BACKEND_PORT=8000
FRONTEND_PORT=5173

kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti tcp:"$port" || true)"
    if [ -n "$pids" ]; then
      echo "[stop_app] Killing process(es) on port $port: $pids"
      kill -9 $pids || true
    else
      echo "[stop_app] No process found on port $port"
    fi
  elif command -v fuser >/dev/null 2>&1; then
    echo "[stop_app] Attempting fuser kill on port $port"
    fuser -k "${port}/tcp" || echo "[stop_app] No process found on port $port"
  else
    echo "[stop_app] Warning: neither lsof nor fuser is available; cannot manage port $port"
  fi
}

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

echo "[stop_app] Done."
