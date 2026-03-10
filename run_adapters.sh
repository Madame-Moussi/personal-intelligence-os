#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/Users/hopemoussi/Documents/New project/workflow-automation-dashboard"
ADAPTERS="${1:-all}"
MODE="${2:-once}"
INTERVAL="${3:-300}"

cd "$ROOT_DIR"
if [[ "$MODE" == "daemon" ]]; then
  exec python3 -m intent_adapters.pollers.run_adapters --adapters "$ADAPTERS" --daemon --interval "$INTERVAL"
fi
exec python3 -m intent_adapters.pollers.run_adapters --adapters "$ADAPTERS"
