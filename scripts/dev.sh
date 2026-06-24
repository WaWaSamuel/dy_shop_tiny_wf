#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" ]; then
  echo "Missing backend runtime: $BACKEND_DIR/.venv/bin/uvicorn"
  echo "Create the backend virtualenv and install requirements first."
  exit 1
fi

if [ ! -f "$FRONTEND_DIR/package.json" ]; then
  echo "Missing frontend package.json in $FRONTEND_DIR"
  exit 1
fi

cleanup() {
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

echo "Starting backend on http://127.0.0.1:8000"
(
  cd "$BACKEND_DIR"
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

echo "Starting frontend on http://127.0.0.1:3000"
(
  cd "$FRONTEND_DIR"
  npm run dev -- --host 127.0.0.1 --port 3000
) &
FRONTEND_PID=$!

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID"
    exit $?
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID"
    exit $?
  fi

  sleep 1
done
