#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/ktm-airwatch"
BACKEND_PORT=8000
FRONTEND_PORT=5173

kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti tcp:"$port" || true)"
    if [ -n "$pids" ]; then
      echo "[run_app] Killing process(es) on port $port: $pids"
      kill -9 $pids || true
    fi
  elif command -v fuser >/dev/null 2>&1; then
    echo "[run_app] Killing process(es) on port $port via fuser"
    fuser -k "${port}/tcp" || true
  else
    echo "[run_app] Warning: neither lsof nor fuser is available; cannot pre-kill port $port"
  fi
}

echo "[run_app] Project root: $ROOT_DIR"

if [ -f "$ROOT_DIR/.env" ]; then
  echo "[run_app] Loading environment from .env"
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
  echo "[run_app] Error: Python venv not found at $ROOT_DIR/.venv/bin/python"
  exit 1
fi

if [ ! -f "$FRONTEND_DIR/package.json" ]; then
  echo "[run_app] Error: Frontend package.json not found at $FRONTEND_DIR/package.json"
  exit 1
fi

echo "[run_app] Starting backend on http://localhost:$BACKEND_PORT ..."
(
  cd "$ROOT_DIR"
  exec "$ROOT_DIR/.venv/bin/python" main.py
) &
BACKEND_PID=$!

echo "[run_app] Starting frontend on http://localhost:$FRONTEND_PORT ..."
(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort
) &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "[run_app] Stopping services..."
  kill "$BACKEND_PID" "$FRONTEND_PID" >/dev/null 2>&1 || true
}

trap cleanup INT TERM EXIT

echo "[run_app] Backend PID: $BACKEND_PID"
echo "[run_app] Frontend PID: $FRONTEND_PID"
echo "[run_app] Press Ctrl+C to stop both services."

echo ""
wait "$BACKEND_PID" "$FRONTEND_PID"
