#!/usr/bin/env python3
from __future__ import annotations

import os
import time
import urllib.error
from typing import Any

from .common import AdapterResult, infer_intent_from_text, iso_from_ts, json_get, post_events

SLACK_HISTORY_URL = "https://slack.com/api/conversations.history"


def _headers(token: str) -> dict[str, str]:
  return {"Authorization": f"Bearer {token}"}


def _channel_list() -> list[str]:
  raw = str(os.environ.get("PIOS_SLACK_CHANNELS", "")).strip()
  return [chunk.strip() for chunk in raw.split(",") if chunk.strip()]


def _is_user_message(row: dict[str, Any]) -> bool:
  subtype = str(row.get("subtype") or "").strip().lower()
  return subtype in {"", "thread_broadcast"}


def run(state: dict[str, Any], server_url: str | None = None) -> AdapterResult:
  token = str(os.environ.get("PIOS_SLACK_BOT_TOKEN", "")).strip()
  channels = _channel_list()
  limit = max(5, min(50, int(os.environ.get("PIOS_SLACK_MAX_RESULTS", "20") or "20")))

  if not token:
    return AdapterResult(name="slack", ok=False, scanned=0, emitted=0, details="missing_token")
  if not channels:
    return AdapterResult(name="slack", ok=False, scanned=0, emitted=0, details="missing_channels")

  adapter_state = state.setdefault("slack", {})
  last_ts_by_channel: dict[str, float] = dict(adapter_state.get("last_ts_by_channel") or {})

  events: list[dict[str, Any]] = []
  scanned = 0

  for channel in channels:
    oldest = float(last_ts_by_channel.get(channel, 0.0) or 0.0)
    params = f"?channel={channel}&limit={limit}"
    if oldest > 0:
      params += f"&oldest={oldest:.6f}"

    try:
      payload = json_get(SLACK_HISTORY_URL + params, headers=_headers(token), timeout=10)
    except (urllib.error.URLError, TimeoutError, ValueError):
      continue

    if not bool(payload.get("ok")):
      continue
    rows = payload.get("messages") or []
    if not isinstance(rows, list):
      continue

    newest = oldest
    for row in rows:
      scanned += 1
      if not isinstance(row, dict) or not _is_user_message(row):
        continue

      ts_raw = str(row.get("ts") or "0").strip()
      try:
        ts_float = float(ts_raw)
      except ValueError:
        ts_float = 0.0
      if ts_float <= oldest:
        continue
      newest = max(newest, ts_float)

      text = str(row.get("text") or "").strip()
      intent, action, stage, confidence = infer_intent_from_text(text, fallback="team_coordination")
      events.append(
        {
          "timestamp": iso_from_ts(ts_float or time.time()),
          "source": "slack_adapter",
          "tool": "slack",
          "domain": "slack.com",
          "intent": intent,
          "action": action,
          "stage": stage,
          "object": "channel_message",
          "text_hint": f"{channel}: {text[:160]}",
          "confidence": max(confidence, 0.58),
        }
      )

    if newest > oldest:
      last_ts_by_channel[channel] = newest

  ok, emitted, detail = post_events(events, server_url=server_url)
  adapter_state["last_ts_by_channel"] = last_ts_by_channel
  adapter_state["last_run_ts"] = int(time.time())
  return AdapterResult(name="slack", ok=ok, scanned=scanned, emitted=emitted, details=detail)
