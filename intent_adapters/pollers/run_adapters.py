#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .common import DEFAULT_STATE_PATH, AdapterResult, load_state, save_state
from .gmail_adapter import run as run_gmail
from .granola_adapter import run as run_granola
from .slack_adapter import run as run_slack
from .workspace_adapter import run as run_workspace

ADAPTER_MAP = {
  "gmail": run_gmail,
  "slack": run_slack,
  "workspace": run_workspace,
  "granola": run_granola,
}


def _selected_adapters(raw: str) -> list[str]:
  requested = [chunk.strip().lower() for chunk in str(raw or "").split(",") if chunk.strip()]
  if not requested or requested == ["all"]:
    return list(ADAPTER_MAP.keys())
  output: list[str] = []
  for name in requested:
    if name in ADAPTER_MAP and name not in output:
      output.append(name)
  return output


def _print_results(results: list[AdapterResult]) -> None:
  rows = [
    {
      "adapter": row.name,
      "ok": row.ok,
      "scanned": row.scanned,
      "emitted": row.emitted,
      "details": row.details,
    }
    for row in results
  ]
  print(json.dumps({"ok": True, "results": rows}, ensure_ascii=True))


def run_once(adapter_names: list[str], server_url: str | None, state_path: Path) -> int:
  state = load_state(state_path)
  results: list[AdapterResult] = []

  for name in adapter_names:
    handler = ADAPTER_MAP.get(name)
    if not handler:
      continue
    try:
      result = handler(state, server_url=server_url)
    except Exception as exc:  # noqa: BLE001
      result = AdapterResult(name=name, ok=False, scanned=0, emitted=0, details=f"runtime_error:{exc}")
    results.append(result)

  save_state(state, state_path)
  _print_results(results)

  if not results:
    return 1
  if any(not row.ok for row in results):
    return 2
  return 0


def main() -> int:
  parser = argparse.ArgumentParser(description="Run Personal Intelligence OS metadata adapters")
  parser.add_argument("--adapters", default="all", help="Comma-separated adapters: gmail,slack,workspace,granola")
  parser.add_argument("--server-url", default="", help="Override server URL (default: http://127.0.0.1:5180)")
  parser.add_argument("--state-file", default=str(DEFAULT_STATE_PATH), help="Path to adapter state JSON")
  parser.add_argument("--daemon", action="store_true", help="Run continuously")
  parser.add_argument("--interval", type=int, default=300, help="Daemon interval in seconds")
  args = parser.parse_args()

  adapter_names = _selected_adapters(args.adapters)
  if not adapter_names:
    print(json.dumps({"ok": False, "error": "no_valid_adapters"}, ensure_ascii=True))
    return 1

  state_path = Path(args.state_file).expanduser()
  server_url = args.server_url.strip() or None

  if not args.daemon:
    return run_once(adapter_names, server_url, state_path)

  interval = max(30, int(args.interval))
  while True:
    exit_code = run_once(adapter_names, server_url, state_path)
    if exit_code == 1:
      return 1
    time.sleep(interval)


if __name__ == "__main__":
  sys.exit(main())
