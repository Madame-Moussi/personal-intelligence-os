#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .common import AdapterResult, infer_intent_from_text, iso_from_ts, post_events


def _collect_files(root: Path) -> list[Path]:
  if not root.exists() or not root.is_dir():
    return []
  rows: list[Path] = []
  for ext in ("*.md", "*.txt", "*.json"):
    rows.extend(root.rglob(ext))
  rows.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0.0, reverse=True)
  return rows[:120]


def _read_snippet(path: Path) -> str:
  try:
    text = path.read_text(encoding="utf-8", errors="ignore")
  except Exception:
    return ""
  cleaned = re.sub(r"\s+", " ", text).strip()
  return cleaned[:260]


def run(state: dict, server_url: str | None = None) -> AdapterResult:
  export_dir = str(os.environ.get("PIOS_GRANOLA_EXPORT_DIR", "")).strip()
  if not export_dir:
    return AdapterResult(name="granola", ok=False, scanned=0, emitted=0, details="missing_export_dir")

  root = Path(export_dir).expanduser()
  files = _collect_files(root)
  if not files:
    return AdapterResult(name="granola", ok=False, scanned=0, emitted=0, details="no_files")

  adapter_state = state.setdefault("granola", {})
  last_mtime = float(adapter_state.get("last_mtime", 0.0) or 0.0)

  events: list[dict[str, object]] = []
  scanned = 0
  newest = last_mtime

  for path in files:
    try:
      mtime = float(path.stat().st_mtime)
    except Exception:
      continue
    scanned += 1
    if mtime <= last_mtime:
      continue
    newest = max(newest, mtime)

    snippet = _read_snippet(path)
    intent, action, stage, confidence = infer_intent_from_text(snippet, fallback="meeting_synthesis")

    events.append(
      {
        "timestamp": iso_from_ts(mtime),
        "source": "granola_adapter",
        "tool": "granola",
        "domain": "granola.ai",
        "intent": intent,
        "action": action,
        "stage": stage if stage != "exploration" else "synthesis",
        "object": "meeting_note",
        "text_hint": f"{path.name}: {snippet[:140]}",
        "confidence": max(confidence, 0.6),
      }
    )

  ok, emitted, detail = post_events(events, server_url=server_url)
  adapter_state["last_mtime"] = newest
  adapter_state["last_run_ts"] = int(time.time())
  return AdapterResult(name="granola", ok=ok, scanned=scanned, emitted=emitted, details=detail)
