#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from workflow_intelligence import (
  build_workflow_insights,
  design_workflow_automation,
  explain_workflow_insight,
  generate_weekly_blueprint,
  intent_event_schema,
  record_intent_events,
  revise_workflow_automation,
)

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"


def _guess_content_type(path: Path) -> str:
  mime, _ = mimetypes.guess_type(str(path))
  return mime or "application/octet-stream"


class WorkflowDashboardHandler(BaseHTTPRequestHandler):
  def _set_cors_headers(self) -> None:
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Headers", "Content-Type")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

  def _send_json(self, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Cache-Control", "no-store")
    self._set_cors_headers()
    self.end_headers()
    self.wfile.write(body)

  def _send_file(self, path: Path, status: int = 200) -> None:
    if not path.exists() or not path.is_file():
      self._send_json({"ok": False, "error": "file_not_found", "path": str(path)}, status=404)
      return
    raw = path.read_bytes()
    self.send_response(status)
    self.send_header("Content-Type", _guess_content_type(path))
    self.send_header("Content-Length", str(len(raw)))
    # Keep UI assets uncached so style/chart iterations appear immediately.
    self.send_header("Cache-Control", "no-store")
    self._set_cors_headers()
    self.end_headers()
    self.wfile.write(raw)

  def _read_json_body(self) -> object:
    raw_len = self.headers.get("Content-Length", "0").strip()
    try:
      length = max(0, int(raw_len or "0"))
    except ValueError:
      length = 0
    if length <= 0:
      return {}
    body = self.rfile.read(length)
    if not body:
      return {}
    try:
      parsed = json.loads(body.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError:
      return {}
    return parsed

  def do_OPTIONS(self) -> None:  # noqa: N802
    self.send_response(204)
    self._set_cors_headers()
    self.send_header("Content-Length", "0")
    self.end_headers()

  def do_GET(self) -> None:  # noqa: N802
    parsed = urlparse(self.path)
    route = parsed.path

    if route == "/api/workflows/insights":
      params = parse_qs(parsed.query)
      raw_days = params.get("days", ["14"])[0]
      try:
        days = max(1, min(90, int(raw_days)))
      except ValueError:
        days = 14
      payload = build_workflow_insights(window_days=days, max_workflows=12)
      self._send_json(payload, status=200)
      return

    if route == "/api/workflows/execute":
      params = parse_qs(parsed.query)
      raw_days = params.get("days", ["14"])[0]
      try:
        days = max(7, min(90, int(raw_days)))
      except ValueError:
        days = 14
      payload = generate_weekly_blueprint(ROOT, window_days=days)
      self._send_json(payload, status=200)
      return

    if route == "/api/workflows/explain":
      params = parse_qs(parsed.query)
      workflow_id = str(params.get("workflow_id", [""])[0]).strip()
      raw_days = params.get("days", ["14"])[0]
      try:
        days = max(1, min(90, int(raw_days)))
      except ValueError:
        days = 14
      payload = explain_workflow_insight(workflow_id=workflow_id, window_days=days, max_workflows=12)
      self._send_json(payload, status=200 if payload.get("ok") else 404)
      return

    if route == "/api/workflows/automation-draft":
      params = parse_qs(parsed.query)
      workflow_id = str(params.get("workflow_id", [""])[0]).strip()
      raw_days = params.get("days", ["14"])[0]
      try:
        days = max(1, min(90, int(raw_days)))
      except ValueError:
        days = 14
      payload = design_workflow_automation(workflow_id=workflow_id, window_days=days, max_workflows=12)
      self._send_json(payload, status=200 if payload.get("ok") else 404)
      return

    if route == "/api/intent/schema":
      self._send_json(intent_event_schema(), status=200)
      return

    if route in {"", "/"}:
      self._send_file(WEB_DIR / "index.html", status=200)
      return

    target = (WEB_DIR / route.lstrip("/")).resolve()
    if WEB_DIR in target.parents and target.exists() and target.is_file():
      self._send_file(target, status=200)
      return

    self._send_file(WEB_DIR / "index.html", status=200)

  def do_POST(self) -> None:  # noqa: N802
    parsed = urlparse(self.path)
    route = parsed.path

    if route == "/api/intent/events":
      body = self._read_json_body()
      if isinstance(body, dict) and isinstance(body.get("events"), list):
        payload: dict | list[dict] = body.get("events") or []
      elif isinstance(body, list):
        payload = body
      elif isinstance(body, dict):
        payload = body
      else:
        payload = {}

      response = record_intent_events(payload)
      self._send_json(response, status=200 if response.get("ok") else 400)
      return

    if route == "/api/workflows/automation-draft/edit":
      body_raw = self._read_json_body()
      body = body_raw if isinstance(body_raw, dict) else {}
      workflow_id = str(body.get("workflow_id", "")).strip()
      instruction = str(body.get("instruction", "")).strip()
      try:
        days = max(1, min(90, int(body.get("days", 14))))
      except (TypeError, ValueError):
        days = 14
      draft = body.get("draft")
      payload = revise_workflow_automation(
        workflow_id=workflow_id,
        edit_instruction=instruction,
        window_days=days,
        max_workflows=12,
        base_draft=draft if isinstance(draft, dict) else None,
      )
      self._send_json(payload, status=200 if payload.get("ok") else 400)
      return

    self._send_json({"ok": False, "error": "route_not_found", "route": route}, status=404)

  def log_message(self, fmt: str, *args) -> None:
    print(f"[workflow-dashboard] {self.address_string()} - {fmt % args}")


def main() -> None:
  parser = argparse.ArgumentParser(description="Personal Intelligence OS Server")
  parser.add_argument("--host", default="127.0.0.1")
  parser.add_argument("--port", type=int, default=5180)
  args = parser.parse_args()

  if not WEB_DIR.exists():
    raise SystemExit(f"Web directory not found at {WEB_DIR}")

  class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

  server = ReusableThreadingHTTPServer((args.host, args.port), WorkflowDashboardHandler)
  print(f"Personal Intelligence OS listening on http://{args.host}:{args.port}")
  print(f"Serving static files from: {WEB_DIR}")
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("Personal Intelligence OS stopped.")
  finally:
    server.server_close()


if __name__ == "__main__":
  main()
