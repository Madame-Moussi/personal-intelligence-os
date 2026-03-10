#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/Users/hopemoussi/Documents/New project/workflow-automation-dashboard"
HOST="${1:-127.0.0.1}"
PORT="${2:-5180}"

cd "$ROOT_DIR"
exec python3 "$ROOT_DIR/server.py" --host "$HOST" --port "$PORT"

