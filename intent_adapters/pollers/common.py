#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SERVER_URL = "http://127.0.0.1:5180"
DEFAULT_STATE_PATH = Path.home() / ".personal_intelligence_os" / "adapter_state.json"


@dataclass
class AdapterResult:
  name: str
  ok: bool
  scanned: int
  emitted: int
  details: str = ""


def iso_from_ts(ts: float | int) -> str:
  return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)


def load_state(path: Path | None = None) -> dict[str, Any]:
  target = path or DEFAULT_STATE_PATH
  if not target.exists():
    return {}
  try:
    return json.loads(target.read_text(encoding="utf-8"))
  except Exception:
    return {}


def save_state(state: dict[str, Any], path: Path | None = None) -> None:
  target = path or DEFAULT_STATE_PATH
  ensure_dir(target)
  target.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def canonical_domain(value: str) -> str:
  raw = str(value or "").strip().lower()
  raw = raw.replace("https://", "").replace("http://", "")
  raw = raw.split("/", 1)[0]
  return raw.replace("www.", "")


def infer_intent_from_text(text: str, fallback: str = "research") -> tuple[str, str, str, float]:
  blob = str(text or "").lower()
  checks: list[tuple[tuple[str, ...], tuple[str, str, str, float]]] = [
    (("job", "application", "recruiter", "resume", "hiring"), ("job_search", "review_job_signal", "exploration", 0.65)),
    (("portfolio", "founder", "outreach", "intro", "follow up"), ("founder_outreach", "prepare_outreach", "coordination", 0.7)),
    (("customer", "feedback", "market", "research", "synthesis"), ("customer_research", "synthesize_findings", "analysis", 0.68)),
    (("invoice", "ops", "admin", "calendar", "meeting"), ("ops_execution", "process_admin_item", "execution", 0.62)),
    (("design", "figma", "wireframe", "prototype"), ("design_iteration", "iterate_design", "execution", 0.64)),
    (("code", "bug", "repo", "commit", "pr", "feature"), ("product_building", "iterate_code", "execution", 0.66)),
  ]
  for tokens, resolved in checks:
    if any(token in blob for token in tokens):
      return resolved
  return (fallback, "review_activity", "exploration", 0.5)


def sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
  row = dict(event)
  row.setdefault("timestamp", datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"))
  row["source"] = str(row.get("source") or "adapter").strip()[:72]
  row["tool"] = re.sub(r"[^a-z0-9_]+", "_", str(row.get("tool") or "app").strip().lower()).strip("_") or "app"
  if row.get("domain"):
    row["domain"] = canonical_domain(str(row["domain"]))
  if row.get("intent"):
    row["intent"] = re.sub(r"[^a-z0-9_]+", "_", str(row["intent"]).strip().lower()).strip("_")[:48]
  if row.get("action"):
    row["action"] = re.sub(r"[^a-z0-9_]+", "_", str(row["action"]).strip().lower()).strip("_")[:48]
  if row.get("stage"):
    row["stage"] = re.sub(r"[^a-z0-9_]+", "_", str(row["stage"]).strip().lower()).strip("_")[:48]
  if "confidence" in row:
    try:
      row["confidence"] = max(0.0, min(1.0, float(row["confidence"])))
    except Exception:
      row["confidence"] = 0.5
  return row


def post_events(events: list[dict[str, Any]], server_url: str | None = None) -> tuple[bool, int, str]:
  if not events:
    return True, 0, "no_events"

  target = (server_url or os.environ.get("PIOS_SERVER_URL") or DEFAULT_SERVER_URL).rstrip("/") + "/api/intent/events"
  payload = json.dumps({"events": [sanitize_event(event) for event in events]}, ensure_ascii=True).encode("utf-8")
  req = urllib.request.Request(
    target,
    data=payload,
    method="POST",
    headers={"Content-Type": "application/json"},
  )
  try:
    with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
      body = resp.read().decode("utf-8", errors="ignore")
      data = json.loads(body) if body else {}
  except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
    return False, 0, f"post_failed:{exc}"

  ok = bool(data.get("ok"))
  emitted = int(data.get("ingested", 0)) if ok else 0
  return ok, emitted, "ok" if ok else str(data.get("error", "unknown_error"))


def json_get(url: str, headers: dict[str, str] | None = None, timeout: float = 8.0) -> Any:
  req = urllib.request.Request(url, method="GET", headers=headers or {})
  with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
    body = resp.read().decode("utf-8", errors="ignore")
  return json.loads(body)


def json_post(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: float = 8.0) -> Any:
  req_headers = {"Content-Type": "application/json"}
  if headers:
    req_headers.update(headers)
  req = urllib.request.Request(
    url,
    data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
    method="POST",
    headers=req_headers,
  )
  with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
    body = resp.read().decode("utf-8", errors="ignore")
  return json.loads(body)
