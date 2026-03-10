#!/usr/bin/env python3
from __future__ import annotations

import os
import time
import urllib.error
from datetime import datetime
from typing import Any

from .common import AdapterResult, infer_intent_from_text, iso_from_ts, json_post, post_events

DRIVE_ACTIVITY_URL = "https://driveactivity.googleapis.com/v2/activity:query"


def _headers(token: str) -> dict[str, str]:
  return {"Authorization": f"Bearer {token}"}


def _parse_activity_ts(row: dict[str, Any]) -> float:
  timestamp = str(row.get("timestamp") or "").strip()
  if timestamp:
    try:
      return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
      pass
  time_range = row.get("timeRange") or {}
  if isinstance(time_range, dict):
    end_time = str(time_range.get("endTime") or "").strip()
    if end_time:
      try:
        return datetime.fromisoformat(end_time.replace("Z", "+00:00")).timestamp()
      except ValueError:
        pass
  return time.time()


def _target_title(row: dict[str, Any]) -> tuple[str, str]:
  target = row.get("target") or {}
  if not isinstance(target, dict):
    return "", ""
  drive_item = target.get("driveItem") or {}
  if not isinstance(drive_item, dict):
    return "", ""
  title = str(drive_item.get("title") or "").strip()
  mime = str(drive_item.get("mimeType") or "").strip().lower()
  return title, mime


def _tool_from_mime(mime: str) -> tuple[str, str]:
  if "document" in mime:
    return "google_docs", "docs.google.com"
  if "spreadsheet" in mime:
    return "google_sheets", "sheets.google.com"
  if "presentation" in mime:
    return "google_slides", "slides.google.com"
  return "google_drive", "drive.google.com"


def _action_from_activity(primary_action: dict[str, Any]) -> str:
  if not isinstance(primary_action, dict):
    return "update_file"
  keys = list(primary_action.keys())
  if not keys:
    return "update_file"
  return str(keys[0]).strip().lower() or "update_file"


def run(state: dict[str, Any], server_url: str | None = None) -> AdapterResult:
  token = str(os.environ.get("PIOS_GOOGLE_ACCESS_TOKEN", "")).strip()
  page_size = max(5, min(50, int(os.environ.get("PIOS_WORKSPACE_MAX_RESULTS", "20") or "20")))

  if not token:
    return AdapterResult(name="workspace", ok=False, scanned=0, emitted=0, details="missing_token")

  adapter_state = state.setdefault("workspace", {})
  last_ts = float(adapter_state.get("last_ts", 0.0) or 0.0)

  payload: dict[str, Any] = {"pageSize": page_size}
  try:
    response = json_post(DRIVE_ACTIVITY_URL, payload, headers=_headers(token), timeout=12)
  except (urllib.error.URLError, TimeoutError, ValueError) as exc:
    return AdapterResult(name="workspace", ok=False, scanned=0, emitted=0, details=f"query_failed:{exc}")

  rows = response.get("activities") or []
  if not isinstance(rows, list):
    rows = []

  events: list[dict[str, Any]] = []
  scanned = 0
  newest = last_ts

  for row in rows:
    if not isinstance(row, dict):
      continue
    scanned += 1
    ts = _parse_activity_ts(row)
    if ts <= last_ts:
      continue
    newest = max(newest, ts)

    targets = row.get("targets") or []
    title = ""
    mime = ""
    if isinstance(targets, list):
      for target in targets:
        if isinstance(target, dict):
          title, mime = _target_title(target)
          if title or mime:
            break
    tool, domain = _tool_from_mime(mime)

    action = _action_from_activity(row.get("primaryActionDetail") or {})
    intent, inferred_action, stage, confidence = infer_intent_from_text(f"{title} {mime} {action}", fallback="document_work")

    events.append(
      {
        "timestamp": iso_from_ts(ts),
        "source": "workspace_adapter",
        "tool": tool,
        "domain": domain,
        "intent": intent,
        "action": inferred_action if inferred_action != "review_activity" else action,
        "stage": stage,
        "object": "workspace_file",
        "text_hint": title[:180],
        "confidence": max(confidence, 0.6),
      }
    )

  ok, emitted, detail = post_events(events, server_url=server_url)
  adapter_state["last_ts"] = newest
  adapter_state["last_run_ts"] = int(time.time())
  return AdapterResult(name="workspace", ok=ok, scanned=scanned, emitted=emitted, details=detail)
