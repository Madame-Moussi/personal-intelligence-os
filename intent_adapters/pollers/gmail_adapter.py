#!/usr/bin/env python3
from __future__ import annotations

import os
import time
import urllib.error
import urllib.parse
from typing import Any

from .common import AdapterResult, infer_intent_from_text, iso_from_ts, json_get, post_events

GMAIL_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/{user}/messages"
GMAIL_MESSAGE_URL = "https://gmail.googleapis.com/gmail/v1/users/{user}/messages/{message_id}"


def _headers(token: str) -> dict[str, str]:
  return {"Authorization": f"Bearer {token}"}


def _message_headers(payload: dict[str, Any]) -> dict[str, str]:
  rows = payload.get("headers") or []
  output: dict[str, str] = {}
  for row in rows:
    name = str(row.get("name") or "").strip().lower()
    value = str(row.get("value") or "").strip()
    if name:
      output[name] = value
  return output


def run(state: dict[str, Any], server_url: str | None = None) -> AdapterResult:
  token = str(os.environ.get("PIOS_GMAIL_ACCESS_TOKEN", "")).strip()
  user = str(os.environ.get("PIOS_GMAIL_USER", "me")).strip() or "me"
  query = str(os.environ.get("PIOS_GMAIL_QUERY", "newer_than:2d")).strip() or "newer_than:2d"
  max_results = max(1, min(30, int(os.environ.get("PIOS_GMAIL_MAX_RESULTS", "12") or "12")))

  if not token:
    return AdapterResult(name="gmail", ok=False, scanned=0, emitted=0, details="missing_token")

  adapter_state = state.setdefault("gmail", {})
  seen: list[str] = list(adapter_state.get("seen_ids") or [])
  seen_set = set(seen)

  params = urllib.parse.urlencode({"q": query, "maxResults": max_results})
  list_url = f"{GMAIL_LIST_URL.format(user=urllib.parse.quote(user))}?{params}"
  try:
    listing = json_get(list_url, headers=_headers(token), timeout=10)
  except (urllib.error.URLError, TimeoutError, ValueError) as exc:
    return AdapterResult(name="gmail", ok=False, scanned=0, emitted=0, details=f"list_failed:{exc}")

  rows = listing.get("messages") or []
  if not isinstance(rows, list):
    rows = []

  events: list[dict[str, Any]] = []
  scanned = 0
  for row in rows:
    message_id = str(row.get("id") or "").strip()
    if not message_id:
      continue
    scanned += 1
    if message_id in seen_set:
      continue

    msg_url = GMAIL_MESSAGE_URL.format(user=urllib.parse.quote(user), message_id=urllib.parse.quote(message_id))
    msg_url += "?format=metadata&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=To"
    try:
      message = json_get(msg_url, headers=_headers(token), timeout=10)
    except (urllib.error.URLError, TimeoutError, ValueError):
      continue

    payload = message.get("payload") or {}
    headers = _message_headers(payload if isinstance(payload, dict) else {})
    subject = headers.get("subject", "")
    sender = headers.get("from", "")
    to = headers.get("to", "")
    combined = " ".join(part for part in (subject, sender, to) if part)

    intent, action, stage, confidence = infer_intent_from_text(combined, fallback="email_operations")
    internal_ms = str(message.get("internalDate") or "0").strip()
    try:
      ts = max(1.0, float(internal_ms) / 1000.0)
    except ValueError:
      ts = time.time()

    events.append(
      {
        "timestamp": iso_from_ts(ts),
        "source": "gmail_adapter",
        "tool": "gmail",
        "domain": "mail.google.com",
        "intent": intent,
        "action": action,
        "stage": stage,
        "object": "email_thread",
        "text_hint": subject[:180],
        "confidence": max(confidence, 0.62),
      }
    )
    seen.append(message_id)
    seen_set.add(message_id)

  ok, emitted, detail = post_events(events, server_url=server_url)
  adapter_state["seen_ids"] = seen[-400:]
  adapter_state["last_run_ts"] = int(time.time())
  return AdapterResult(name="gmail", ok=ok, scanned=scanned, emitted=emitted, details=detail)
