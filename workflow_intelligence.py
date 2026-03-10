#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

MAX_HISTORY_LINES = 12_000
SESSION_GAP_SECONDS = 45 * 60
MIN_STEPS_PER_SESSION = 3
MIN_SUPPORT_SESSIONS = 2
ACTIVITYWATCH_MAX_EVENTS_PER_BUCKET = 8_000
DEFAULT_OLLAMA_MODELS = ("qwen2.5:7b-instruct", "llama3.2:3b")
INTENT_EVENT_RETENTION_DAYS = 120
INTENT_EVENT_MAX_LINES = 250_000
INTENT_EVENT_MIN_FLUSH_INTERVAL_SECONDS = 3600

HISTORY_FILES = (
  Path.home() / ".zsh_history",
  Path.home() / ".bash_history",
  Path.home() / ".bash_eternal_history",
  Path.home() / ".config" / "fish" / "fish_history",
)

WRAPPER_TOKENS = {"sudo", "command", "env", "time", "nohup"}
NOISE_TOOLS = {
  "",
  "cd",
  "pwd",
  "clear",
  "history",
  "ls",
  "ll",
  "la",
  "echo",
  "which",
  "whoami",
  "exit",
}
CODE_SNIPPET_PREFIXES = {
  "def",
  "class",
  "return",
  "import",
  "from",
  "for",
  "while",
  "if",
  "elif",
  "else",
  "print",
  "with",
  "try",
  "except",
  "finally",
  "self",
}
TOOL_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._+-]*$")
PATH_TOKEN_RE = re.compile(r"^[A-Za-z0-9_./+\-]+$")
DOMAIN_IN_TEXT_RE = re.compile(r"(?<!@)\b([a-z0-9][a-z0-9.-]+\.[a-z]{2,})(?:[/:?#]|\b)", re.IGNORECASE)
NON_SITE_SUFFIXES = {
  "pdf",
  "doc",
  "docx",
  "ppt",
  "pptx",
  "xls",
  "xlsx",
  "csv",
  "txt",
  "md",
  "rtf",
  "png",
  "jpg",
  "jpeg",
  "gif",
  "webp",
  "svg",
  "heic",
  "key",
  "pages",
  "numbers",
  "py",
  "js",
  "ts",
  "tsx",
  "jsx",
}
COMMON_TOOLS = {
  "git",
  "python",
  "python3",
  "pip",
  "pip3",
  "uv",
  "node",
  "npm",
  "pnpm",
  "yarn",
  "bun",
  "npx",
  "pytest",
  "ruff",
  "mypy",
  "black",
  "prettier",
  "go",
  "cargo",
  "rustc",
  "javac",
  "java",
  "tsc",
  "vite",
  "docker",
  "kubectl",
  "terraform",
  "aws",
  "gcloud",
  "az",
  "ssh",
  "scp",
  "rsync",
  "make",
  "cmake",
  "bash",
  "zsh",
  "sh",
  "curl",
  "wget",
  "rg",
  "grep",
  "fd",
  "find",
  "sed",
  "awk",
  "cat",
  "less",
  "head",
  "tail",
  "code",
  "cursor",
  "open",
}

APP_TO_TOOL = {
  "cursor": "code",
  "visual studio code": "code",
  "code": "code",
  "iterm2": "terminal",
  "terminal": "terminal",
  "warp": "terminal",
  "google chrome": "browser",
  "chrome": "browser",
  "safari": "browser",
  "arc": "browser",
  "firefox": "browser",
  "brave browser": "browser",
  "notion": "notion",
  "slack": "slack",
  "figma": "figma",
  "zoom": "zoom",
  "microsoft teams": "teams",
  "microsoft powerpoint": "powerpoint",
  "powerpoint": "powerpoint",
  "microsoft excel": "excel",
  "mail": "mail",
  "outlook": "mail",
  "granola": "granola",
}

BROWSER_TITLE_SITE_HINTS: tuple[tuple[str, str], ...] = (
  ("google docs", "docs.google.com"),
  ("google sheets", "sheets.google.com"),
  ("google slides", "slides.google.com"),
  ("google presentation", "slides.google.com"),
  ("google drive", "drive.google.com"),
  ("google calendar", "calendar.google.com"),
  ("google meet", "meet.google.com"),
  ("google gemini", "gemini.google.com"),
  ("gemini", "gemini.google.com"),
  ("gmail", "mail.google.com"),
  ("inbox", "mail.google.com"),
  ("figma", "figma.com"),
  ("figjam", "figma.com"),
  ("github", "github.com"),
  ("gitlab", "gitlab.com"),
  ("notion", "notion.so"),
  ("slack", "slack.com"),
  ("linkedin", "linkedin.com"),
  ("whatsapp web", "web.whatsapp.com"),
  ("whatsapp", "web.whatsapp.com"),
  ("youtube", "youtube.com"),
  ("reddit", "reddit.com"),
  ("chatgpt", "chat.openai.com"),
  ("claude", "claude.ai"),
  ("perplexity", "perplexity.ai"),
  ("canva", "canva.com"),
  ("powerpoint", "powerpoint.office.com"),
  ("microsoft powerpoint", "powerpoint.office.com"),
  ("granola", "granola.ai"),
  ("salesforce", "salesforce.com"),
  ("hubspot", "hubspot.com"),
)

BROWSER_DOMAIN_TOOL_HINTS: tuple[tuple[str, str], ...] = (
  ("docs.google.com", "google_docs"),
  ("sheets.google.com", "google_sheets"),
  ("slides.google.com", "google_slides"),
  ("drive.google.com", "google_drive"),
  ("mail.google.com", "gmail"),
  ("calendar.google.com", "google_calendar"),
  ("meet.google.com", "google_meet"),
  ("gemini.google.com", "gemini"),
  ("figma.com", "figma"),
  ("notion.so", "notion"),
  ("slack.com", "slack"),
  ("linkedin.com", "linkedin"),
  ("salesforce.com", "salesforce"),
  ("hubspot.com", "hubspot"),
  ("zoom.us", "zoom"),
  ("teams.microsoft.com", "teams"),
  ("powerpoint.office.com", "powerpoint"),
  ("office.live.com", "powerpoint"),
  ("granola.ai", "granola"),
)

BROWSER_TITLE_STRIP_TOKENS = (
  " - google chrome",
  " - chrome",
  " - arc",
  " - safari",
  " - firefox",
  " - brave browser",
  " - microsoft edge",
)

MCP_TOOL_LIBRARY = {
  "gmail": {
    "tool": "Gmail",
    "mcp_server": "gmail",
    "purpose": "Monitor new email threads and extract sender, subject, and body snippets.",
  },
  "mail": {
    "tool": "Mail",
    "mcp_server": "gmail",
    "purpose": "Watch inbound messages and classify requests for follow-up.",
  },
  "slack": {
    "tool": "Slack",
    "mcp_server": "slack",
    "purpose": "Send verification summaries and route exceptions to channels.",
  },
  "sheet": {
    "tool": "Google Sheets",
    "mcp_server": "google_sheets",
    "purpose": "Append normalized rows and maintain a structured tracking table.",
  },
  "sheets": {
    "tool": "Google Sheets",
    "mcp_server": "google_sheets",
    "purpose": "Append normalized rows and maintain a structured tracking table.",
  },
  "excel": {
    "tool": "Excel",
    "mcp_server": "excel",
    "purpose": "Write transformed records into workbook tabs and formula ranges.",
  },
  "google_docs": {
    "tool": "Google Docs",
    "mcp_server": "google_docs",
    "purpose": "Read and update document content as part of the workflow.",
  },
  "google_slides": {
    "tool": "Google Slides",
    "mcp_server": "google_slides",
    "purpose": "Create or update slide decks used in the workflow.",
  },
  "powerpoint": {
    "tool": "PowerPoint",
    "mcp_server": "powerpoint",
    "purpose": "Read and update presentation slides and speaker notes.",
  },
  "granola": {
    "tool": "Granola",
    "mcp_server": "granola",
    "purpose": "Capture and summarize meeting notes for downstream actions.",
  },
  "google_drive": {
    "tool": "Google Drive",
    "mcp_server": "google_drive",
    "purpose": "Read and organize shared files tied to this workflow.",
  },
  "google_meet": {
    "tool": "Google Meet",
    "mcp_server": "google_meet",
    "purpose": "Use meeting context and recordings as workflow triggers.",
  },
  "gemini": {
    "tool": "Gemini",
    "mcp_server": "browser",
    "purpose": "Capture generated outputs from Gemini interactions.",
  },
  "linkedin": {
    "tool": "LinkedIn",
    "mcp_server": "linkedin",
    "purpose": "Read outreach context and contact metadata.",
  },
  "salesforce": {
    "tool": "Salesforce",
    "mcp_server": "salesforce",
    "purpose": "Read and update CRM records tied to this workflow.",
  },
  "hubspot": {
    "tool": "HubSpot",
    "mcp_server": "hubspot",
    "purpose": "Sync pipeline and contact updates from repeated workflow steps.",
  },
  "notion": {
    "tool": "Notion",
    "mcp_server": "notion",
    "purpose": "Create structured pages and sync action items.",
  },
  "calendar": {
    "tool": "Google Calendar",
    "mcp_server": "google_calendar",
    "purpose": "Read meeting events and schedule follow-up blocks.",
  },
  "zoom": {
    "tool": "Zoom",
    "mcp_server": "zoom",
    "purpose": "Trigger workflows from new recordings and meeting events.",
  },
  "teams": {
    "tool": "Microsoft Teams",
    "mcp_server": "microsoft_teams",
    "purpose": "Capture chat decisions and send completion summaries.",
  },
  "codex": {
    "tool": "Codex",
    "mcp_server": "codex",
    "purpose": "Execute coding and implementation steps linked to this workflow.",
  },
  "claude": {
    "tool": "Claude",
    "mcp_server": "claude",
    "purpose": "Generate or refine text artifacts for this workflow.",
  },
  "python": {
    "tool": "Python",
    "mcp_server": "python",
    "purpose": "Run deterministic Python scripts for transformation or analysis.",
  },
  "curl": {
    "tool": "Curl",
    "mcp_server": "http",
    "purpose": "Call HTTP endpoints used in the observed workflow.",
  },
  "browser": {
    "tool": "Web Browser",
    "mcp_server": "browser",
    "purpose": "Collect source pages and enrich records with metadata.",
  },
  "terminal": {
    "tool": "Terminal",
    "mcp_server": "filesystem",
    "purpose": "Run deterministic scripts and persist artifacts.",
  },
  "git": {
    "tool": "Git",
    "mcp_server": "git",
    "purpose": "Track changed files and post commit-level summaries.",
  },
}

MCP_TOOL_SYNONYMS = {
  "google sheets": "sheet",
  "google_sheets": "sheet",
  "google docs": "google_docs",
  "google_docs": "google_docs",
  "google slides": "google_slides",
  "google_slides": "google_slides",
  "google drive": "google_drive",
  "google_drive": "google_drive",
  "google calendar": "calendar",
  "google_calendar": "calendar",
  "google meet": "google_meet",
  "google_meet": "google_meet",
  "gemini": "gemini",
  "linkedin": "linkedin",
  "salesforce": "salesforce",
  "hubspot": "hubspot",
  "spreadsheet": "sheet",
  "sheets": "sheet",
  "sheet": "sheet",
  "excel": "excel",
  "google docs": "google_docs",
  "docs": "google_docs",
  "google slides": "google_slides",
  "slides": "google_slides",
  "powerpoint": "powerpoint",
  "ppt": "powerpoint",
  "microsoft powerpoint": "powerpoint",
  "granola": "granola",
  "gmail": "gmail",
  "mail": "mail",
  "outlook": "mail",
  "email": "mail",
  "slack": "slack",
  "notion": "notion",
  "calendar": "calendar",
  "zoom": "zoom",
  "teams": "teams",
  "codex": "codex",
  "claude": "claude",
  "python": "python",
  "curl": "curl",
  "browser": "browser",
  "chrome": "browser",
  "safari": "browser",
  "arc": "browser",
  "terminal": "terminal",
  "shell": "terminal",
  "git": "git",
}

LLM_TOOL_MENTION_GUARD = {
  "slack": "slack",
  "gmail": "gmail",
  "google docs": "google_docs",
  "docs.google.com": "google_docs",
  "google sheets": "sheet",
  "sheets.google.com": "sheet",
  "google slides": "google_slides",
  "slides.google.com": "google_slides",
  "powerpoint": "powerpoint",
  "excel": "excel",
  "figma": "figma",
  "linkedin": "linkedin",
  "salesforce": "salesforce",
  "hubspot": "hubspot",
  "zoom": "zoom",
  "teams": "teams",
  "notion": "notion",
  "granola": "granola",
  "codex": "codex",
  "claude": "claude",
  "gemini": "gemini",
  "python": "python",
  "terminal": "terminal",
  "git": "git",
}

CATEGORY_RULES = {
  "research": {
    "browser",
    "google_docs",
    "google_drive",
    "google_slides",
    "gemini",
    "curl",
    "wget",
    "rg",
    "grep",
    "jupyter",
    "ipython",
    "zotero",
    "obsidian",
    "notion",
    "python",
  },
  "gtm": {
    "hubspot",
    "salesforce",
    "apollo",
    "outreach",
    "mailchimp",
    "linkedin",
    "slack",
    "airtable",
    "notion",
    "figma",
    "canva",
    "sheet",
  },
  "ops": {
    "docker",
    "kubectl",
    "terraform",
    "ansible",
    "aws",
    "gcloud",
    "az",
    "ssh",
    "scp",
    "rsync",
    "systemctl",
    "cron",
  },
  "engineering": {
    "git",
    "code",
    "terminal",
    "npm",
    "pnpm",
    "yarn",
    "bun",
    "python",
    "pytest",
    "ruff",
    "mypy",
    "black",
    "node",
    "go",
    "cargo",
    "make",
    "vite",
  },
  "analytics": {
    "python",
    "jupyter",
    "ipython",
    "duckdb",
    "sqlite",
    "psql",
    "dbt",
    "spark",
    "pandas",
  },
  "admin": {
    "calendar",
    "zoom",
    "teams",
    "mail",
    "outlook",
    "google_docs",
    "google_sheets",
    "powerpoint",
    "granola",
    "notion",
    "slack",
  },
}

TOOL_WORKFLOW_CATEGORY = {
  "google_docs": "research",
  "google_sheets": "analytics",
  "google_slides": "creative",
  "powerpoint": "creative",
  "granola": "meetings",
  "gmail": "admin",
  "mail": "admin",
  "linkedin": "gtm",
  "salesforce": "gtm",
  "hubspot": "gtm",
  "figma": "creative",
  "notion": "admin",
  "excel": "analytics",
  "claude": "deep",
  "codex": "engineering",
  "gemini": "research",
}

TOOL_WORKFLOW_NAME = {
  "google_docs": "Google Docs Workflow",
  "google_sheets": "Google Sheets Workflow",
  "google_slides": "Google Slides Workflow",
  "powerpoint": "PowerPoint Workflow",
  "granola": "Granola Notes Workflow",
  "gmail": "Gmail Workflow",
  "mail": "Email Workflow",
  "linkedin": "LinkedIn Workflow",
  "salesforce": "Salesforce Workflow",
  "hubspot": "HubSpot Workflow",
  "figma": "Figma Workflow",
  "notion": "Notion Workflow",
  "excel": "Excel Workflow",
  "claude": "Claude Workflow",
  "codex": "Codex Workflow",
  "gemini": "Gemini Workflow",
}

TOOL_WORKFLOW_PRIORITY = (
  "google_docs",
  "powerpoint",
  "granola",
  "google_sheets",
  "google_slides",
  "gmail",
  "linkedin",
  "salesforce",
  "hubspot",
  "figma",
  "notion",
  "excel",
  "codex",
  "claude",
  "gemini",
)

CATEGORY_IDEA_LIBRARY = {
  "research": [
    {
      "title": "Source Triage Assistant",
      "proposal": "Auto-cluster new links/notes by topic and produce a daily 5-bullet evidence digest.",
      "impact": "Cuts manual context-switching and speeds synthesis.",
      "effort": "Medium",
    },
    {
      "title": "Reading-to-Tasks Converter",
      "proposal": "Convert research notes into action items with owners, due dates, and confidence tags.",
      "impact": "Moves insight work from passive reading to active execution.",
      "effort": "Low",
    },
  ],
  "gtm": [
    {
      "title": "Pipeline Hygiene Bot",
      "proposal": "Detect stale leads/opportunities and auto-draft follow-up messages and next actions.",
      "impact": "Improves conversion consistency with minimal manual review.",
      "effort": "Medium",
    },
    {
      "title": "Campaign Debrief Generator",
      "proposal": "Merge campaign metrics and meeting notes into a weekly what-worked/what-failed brief.",
      "impact": "Accelerates GTM learning loops and prioritization.",
      "effort": "Low",
    },
  ],
  "ops": [
    {
      "title": "Runbook Auto-Executor",
      "proposal": "Trigger standard remediation steps from incident patterns and log outcomes automatically.",
      "impact": "Reduces MTTR and operational variance.",
      "effort": "Medium",
    },
    {
      "title": "Infra Drift Watcher",
      "proposal": "Track config drift and open a daily diff report with suggested fixes.",
      "impact": "Prevents silent reliability regressions.",
      "effort": "Low",
    },
  ],
  "engineering": [
    {
      "title": "One-Command Dev Bootstrap",
      "proposal": "Combine pull, dependency check, lint, tests, and local run into one orchestrated command.",
      "impact": "Eliminates repetitive setup overhead in coding loops.",
      "effort": "Low",
    },
    {
      "title": "PR Readiness Copilot",
      "proposal": "Detect changed files, run targeted checks, and generate a draft PR summary automatically.",
      "impact": "Shortens ship cycles while preserving quality gates.",
      "effort": "Medium",
    },
  ],
  "analytics": [
    {
      "title": "Notebook-to-Report Pipeline",
      "proposal": "Turn recurring notebook runs into scheduled jobs that publish a concise metrics brief.",
      "impact": "Removes manual rerun/reporting work from analysis cycles.",
      "effort": "Medium",
    },
    {
      "title": "Anomaly Alert Digest",
      "proposal": "Auto-detect KPI anomalies and generate context-rich summaries for review.",
      "impact": "Speeds diagnosis and decision-making.",
      "effort": "Low",
    },
  ],
  "admin": [
    {
      "title": "Meeting Prep Pack",
      "proposal": "Generate agenda, context, and action-item follow-up from calendar + notes.",
      "impact": "Reduces overhead around recurring coordination tasks.",
      "effort": "Low",
    },
    {
      "title": "Inbox Priority Router",
      "proposal": "Classify incoming requests by urgency and auto-suggest the next best action.",
      "impact": "Keeps execution focused on highest-value work.",
      "effort": "Medium",
    },
  ],
  "general": [
    {
      "title": "Workflow Macro Runner",
      "proposal": "Package frequent multi-step routines into replayable scripts with guardrails.",
      "impact": "Converts repeat manual effort into reusable automation assets.",
      "effort": "Medium",
    },
    {
      "title": "Daily Work Recap",
      "proposal": "Summarize repeated actions and suggest top 3 automation opportunities each day.",
      "impact": "Builds a continuous automation backlog.",
      "effort": "Low",
    },
  ],
}

ZSH_HISTORY_RE = re.compile(r"^: (\d+):\d+;(.*)$")
PATH_WRAPPER_RE = re.compile(r"^[A-Za-z0-9_]+=.+$")
_INTENT_LAST_PRUNE_TS = 0


@dataclass(frozen=True)
class CommandEvent:
  source: str
  timestamp: int
  raw: str
  tool: str
  action: str


def _to_iso(ts: int) -> str:
  return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone().isoformat()


def _utc_iso(ts: int) -> str:
  return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _read_recent_lines(path: Path, max_lines: int = MAX_HISTORY_LINES) -> list[str]:
  try:
    lines = path.read_text(errors="ignore").splitlines()
  except Exception:
    return []
  if len(lines) > max_lines:
    return lines[-max_lines:]
  return lines


def _parse_fish_history(lines: list[str]) -> list[tuple[int, str]]:
  rows: list[tuple[int, str]] = []
  i = 0
  while i < len(lines):
    stripped = lines[i].strip()
    if not stripped.startswith("- cmd:"):
      i += 1
      continue

    command = stripped.split(":", 1)[1].strip()
    when_ts = 0
    j = i + 1
    while j < len(lines):
      probe = lines[j].strip()
      if probe.startswith("- cmd:"):
        break
      if probe.startswith("when:"):
        raw_ts = probe.split(":", 1)[1].strip()
        if raw_ts.isdigit():
          when_ts = int(raw_ts)
        break
      j += 1

    rows.append((when_ts, command))
    i = j

  return rows


def _parse_shell_history(lines: list[str]) -> list[tuple[int, str]]:
  rows: list[tuple[int, str]] = []
  pending_ts = 0

  for line in lines:
    raw = line.strip()
    if not raw:
      continue

    zsh_match = ZSH_HISTORY_RE.match(raw)
    if zsh_match:
      rows.append((int(zsh_match.group(1)), zsh_match.group(2).strip()))
      pending_ts = 0
      continue

    if raw.startswith("#") and raw[1:].isdigit():
      pending_ts = int(raw[1:])
      continue

    rows.append((pending_ts, raw))
    pending_ts = 0

  return rows


def _strip_wrappers(tokens: list[str]) -> list[str]:
  idx = 0
  while idx < len(tokens):
    token = tokens[idx].lower()
    if token in WRAPPER_TOKENS:
      idx += 1
      continue
    if PATH_WRAPPER_RE.match(tokens[idx]) and idx + 1 < len(tokens):
      idx += 1
      continue
    break
  return tokens[idx:]


def _derive_action(tool: str, args: list[str]) -> str:
  if tool == "git":
    verb = args[0] if args else "status"
    if verb.startswith("-") and len(args) > 1:
      verb = args[1]
    return f"git {verb}"

  if tool in {"npm", "pnpm", "yarn", "bun"}:
    verb = args[0] if args else "run"
    if verb == "run" and len(args) > 1:
      return f"{tool} {args[1]}"
    return f"{tool} {verb}"

  if tool in {"python", "python3"}:
    if "-m" in args:
      idx = args.index("-m")
      module = args[idx + 1] if idx + 1 < len(args) else "module"
      module = module.split(".", 1)[0]
      if module in {"pytest", "ruff", "mypy", "black", "pip", "jupyter", "ipython"}:
        return f"{module} run"
      return f"python -m {module}"
    if args:
      first = args[0]
      if first.endswith(".py"):
        return f"python {Path(first).stem}"
      return f"python {first.lstrip('-') or 'script'}"
    return "python repl"

  if tool in {"rg", "grep", "fd", "find"}:
    return f"{tool} search"

  if tool in {"cat", "bat", "less", "head", "tail", "sed", "awk"}:
    return f"{tool} inspect"

  if tool in {"pytest", "ruff", "mypy", "black"}:
    return f"{tool} run"

  if tool in {"docker", "kubectl", "terraform", "aws", "gcloud", "az"}:
    verb = args[0] if args else "run"
    return f"{tool} {verb}"

  if tool in {"open"}:
    return "browser open"

  if tool in {"code", "cursor", "vim", "nvim"}:
    return f"{tool} edit"

  verb = args[0] if args else "run"
  if verb.startswith("-"):
    verb = "run"
  return f"{tool} {verb}"


def _normalize_command(command: str) -> tuple[str, str] | None:
  cmd = str(command or "").strip()
  if not cmd:
    return None

  try:
    tokens = shlex.split(cmd, posix=True)
  except ValueError:
    tokens = cmd.split()
  if not tokens:
    return None

  tokens = _strip_wrappers(tokens)
  if not tokens:
    return None

  raw_head = tokens[0]
  tool = Path(raw_head).name.lower()
  args = tokens[1:]

  if tool in NOISE_TOOLS:
    return None
  if tool in CODE_SNIPPET_PREFIXES:
    return None
  if tool.startswith("self."):
    return None
  if any(ch in tool for ch in "(){}[]=,") and "/" not in tool:
    return None
  if "/" in raw_head:
    if not PATH_TOKEN_RE.match(raw_head):
      return None
  else:
    if tool not in COMMON_TOOLS and not _tool_exists(tool):
      return None

  action = _derive_action(tool, args)
  normalized_tool = action.split(" ", 1)[0].strip().lower()
  if normalized_tool in NOISE_TOOLS:
    return None
  return normalized_tool, action


@lru_cache(maxsize=512)
def _tool_exists(name: str) -> bool:
  if not name or len(name) <= 1:
    return False
  if not TOOL_TOKEN_RE.match(name):
    return False
  return shutil.which(name) is not None


def _load_history_events(path: Path, window_start_ts: int) -> tuple[list[CommandEvent], dict[str, Any] | None]:
  if not path.exists() or not path.is_file():
    return [], None

  lines = _read_recent_lines(path)
  if not lines:
    return [], {"source": str(path), "events": 0, "raw_lines": 0}

  if path.name == "fish_history":
    raw_rows = _parse_fish_history(lines)
  else:
    raw_rows = _parse_shell_history(lines)

  if not raw_rows:
    return [], {"source": str(path), "events": 0, "raw_lines": len(lines)}

  try:
    mtime = int(path.stat().st_mtime)
  except Exception:
    mtime = int(time.time())
  fallback_start = mtime - len(raw_rows) * 90

  events: list[CommandEvent] = []
  for idx, (raw_ts, command) in enumerate(raw_rows):
    parsed = _normalize_command(command)
    if parsed is None:
      continue
    tool, action = parsed
    ts = int(raw_ts) if int(raw_ts or 0) > 0 else fallback_start + idx * 90
    if ts < window_start_ts:
      continue
    events.append(
      CommandEvent(
        source=str(path),
        timestamp=ts,
        raw=command.strip(),
        tool=tool,
        action=action,
      )
    )

  return events, {"source": str(path), "events": len(events), "raw_lines": len(lines)}


def _collect_events(window_days: int) -> tuple[list[CommandEvent], list[dict[str, Any]]]:
  now = int(time.time())
  window_start_ts = now - max(1, int(window_days)) * 86400

  events: list[CommandEvent] = []
  sources: list[dict[str, Any]] = []

  for path in HISTORY_FILES:
    path_events, meta = _load_history_events(path, window_start_ts)
    if meta is not None:
      sources.append({**meta, "kind": "shell_history"})
    events.extend(path_events)

  aw_events, aw_meta = _load_activitywatch_events(window_start_ts, now)
  if aw_meta is not None:
    sources.append(aw_meta)
  events.extend(aw_events)

  intent_events, intent_meta = _load_intent_events(window_start_ts, now)
  if intent_meta is not None:
    sources.append(intent_meta)
  events.extend(intent_events)

  events.sort(key=lambda row: row.timestamp)
  return events, sources


def _events_for_behavioral_analysis(events: list[CommandEvent]) -> list[CommandEvent]:
  if not events:
    return []

  intent_events = [event for event in events if str(event.source or "").startswith("intent:")]
  aw_events = [event for event in events if str(event.source or "").startswith("activitywatch:")]

  if intent_events:
    merged = intent_events + aw_events
    merged.sort(key=lambda row: row.timestamp)
    return merged

  if aw_events:
    aw_events.sort(key=lambda row: row.timestamp)
    return aw_events

  fallback = sorted(events, key=lambda row: row.timestamp)
  return fallback


def _fetch_json(url: str, timeout_seconds: float = 2.5) -> Any:
  req = urllib.request.Request(url=url, method="GET")
  with urllib.request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
    return json.loads(response.read().decode("utf-8", errors="ignore"))


def _intent_event_store_path() -> Path:
  raw = os.environ.get("WORKFLOW_INTENT_EVENT_STORE", "").strip()
  if raw:
    return Path(raw).expanduser()
  return (Path.home() / ".personal_intelligence_os" / "intent_events.ndjson").expanduser()


def _parse_timestamp_any(value: Any) -> int:
  if value is None:
    return 0
  if isinstance(value, (int, float)):
    return int(value)
  text = str(value).strip()
  if not text:
    return 0
  try:
    return int(float(text))
  except ValueError:
    pass
  candidate = text.replace("Z", "+00:00")
  try:
    return int(datetime.fromisoformat(candidate).timestamp())
  except ValueError:
    return 0


def _normalize_intent_token(value: Any, max_len: int = 48) -> str:
  cleaned = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
  if not cleaned:
    return ""
  return cleaned[: max(1, int(max_len))]


def _normalize_intent_event(payload: dict[str, Any], received_ts: int | None = None) -> dict[str, Any] | None:
  if not isinstance(payload, dict):
    return None

  now_ts = int(time.time())
  ts = _parse_timestamp_any(payload.get("timestamp"))
  if ts <= 0:
    ts = _parse_timestamp_any(payload.get("time"))
  if ts <= 0:
    ts = _parse_timestamp_any(payload.get("ts"))
  if ts <= 0:
    ts = _parse_timestamp_any(payload.get("event_time"))
  if ts <= 0:
    ts = int(received_ts or now_ts)
  ts = max(now_ts - (365 * 24 * 3600), min(ts, now_ts + 300))

  source = str(payload.get("source") or payload.get("adapter") or "intent_adapter").strip()[:72]
  app = str(payload.get("app") or payload.get("application") or "").strip().lower()
  url = str(payload.get("url") or payload.get("href") or "").strip()
  title = str(payload.get("title") or payload.get("page_title") or "").strip()

  domain = _canonical_site_host(str(payload.get("domain") or payload.get("host") or payload.get("site") or "").strip())
  if not domain:
    domain = _canonical_site_host(_domain_from_url(url))
  if not domain and title:
    domain = _site_from_browser_title(title)

  inferred_tool = _tool_from_browser_context(domain, title) if domain else ""
  tool = _normalize_tool_key(str(payload.get("tool") or payload.get("platform") or ""))
  if not tool:
    mapped = APP_TO_TOOL.get(app) or APP_TO_TOOL.get(app.replace(".app", "")) or ""
    tool = _normalize_tool_key(mapped)
  if not tool:
    if inferred_tool and inferred_tool != "browser":
      tool = inferred_tool
    elif domain:
      tool = "browser"
    elif app:
      tool = _normalize_tool_key(app.split(" ", 1)[0])
  if not tool:
    tool = "app"

  intent = _normalize_intent_token(payload.get("intent") or payload.get("goal") or payload.get("task"))
  action = _normalize_intent_token(payload.get("action") or payload.get("event") or payload.get("verb"))
  stage = _normalize_intent_token(payload.get("stage") or payload.get("phase"))
  object_hint = _normalize_intent_token(payload.get("object") or payload.get("entity"), max_len=60)

  if domain:
    action_parts = [f"browser visit {domain}"]
    if intent:
      action_parts.append(f"intent {intent}")
    if action:
      action_parts.append(f"action {action}")
    if stage:
      action_parts.append(f"stage {stage}")
    if object_hint:
      action_parts.append(f"object {object_hint}")
    normalized_action = " ".join(action_parts)
  else:
    action_parts = [tool]
    if intent:
      action_parts.append(f"intent {intent}")
    if action:
      action_parts.append(f"action {action}")
    if stage:
      action_parts.append(f"stage {stage}")
    if object_hint:
      action_parts.append(f"object {object_hint}")
    if len(action_parts) == 1:
      action_parts.append("active")
    normalized_action = " ".join(action_parts)

  text_hint = str(payload.get("text_hint") or payload.get("summary") or payload.get("description") or "").strip()
  confidence_raw = payload.get("confidence")
  try:
    confidence = max(0.0, min(1.0, float(confidence_raw))) if confidence_raw is not None else None
  except (TypeError, ValueError):
    confidence = None

  return {
    "timestamp": ts,
    "source": source or "intent_adapter",
    "tool": tool,
    "domain": domain,
    "app": app,
    "url": url,
    "title": title[:220],
    "intent": intent,
    "action": action,
    "stage": stage,
    "object": object_hint,
    "text_hint": text_hint[:220],
    "confidence": confidence,
    "normalized_action": normalized_action,
  }


def _prune_intent_event_store(path: Path, now_ts: int) -> int:
  if not path.exists():
    return 0
  try:
    lines = path.read_text(errors="ignore").splitlines()
  except Exception:
    return 0
  if not lines:
    return 0

  keep_after = now_ts - INTENT_EVENT_RETENTION_DAYS * 86400
  kept: list[str] = []
  for line in lines[-(INTENT_EVENT_MAX_LINES * 2) :]:
    row = line.strip()
    if not row:
      continue
    try:
      item = json.loads(row)
    except json.JSONDecodeError:
      continue
    ts = _parse_timestamp_any(item.get("timestamp"))
    if ts and ts < keep_after:
      continue
    kept.append(json.dumps(item, ensure_ascii=True, separators=(",", ":")))
  kept = kept[-INTENT_EVENT_MAX_LINES:]
  if len(kept) == len(lines):
    return len(kept)
  try:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
  except Exception:
    return len(lines)
  return len(kept)


def record_intent_events(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
  now_ts = int(time.time())
  rows_raw = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
  normalized: list[dict[str, Any]] = []
  for row in rows_raw:
    item = _normalize_intent_event(row, received_ts=now_ts)
    if not item:
      continue
    normalized.append(item)

  path = _intent_event_store_path()
  if not normalized:
    return {"ok": False, "error": "no_valid_events", "ingested": 0, "path": str(path)}

  try:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
      for row in normalized:
        handle.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
  except Exception as exc:
    return {"ok": False, "error": f"intent_store_write_failed: {exc}", "ingested": 0, "path": str(path)}

  global _INTENT_LAST_PRUNE_TS  # noqa: PLW0603
  if now_ts - int(_INTENT_LAST_PRUNE_TS) >= INTENT_EVENT_MIN_FLUSH_INTERVAL_SECONDS:
    _INTENT_LAST_PRUNE_TS = now_ts
    _prune_intent_event_store(path, now_ts)

  tool_counts = Counter(str(row.get("tool") or "") for row in normalized if str(row.get("tool") or "").strip())
  return {
    "ok": True,
    "ingested": len(normalized),
    "path": str(path),
    "tools": [{"tool": tool, "count": count} for tool, count in tool_counts.most_common(12)],
    "received_at": _to_iso(now_ts),
  }


def intent_event_schema() -> dict[str, Any]:
  return {
    "ok": True,
    "name": "intent_event_v1",
    "description": "Low-overhead, event-based activity capture for intent detection.",
    "required_fields": ["timestamp", "tool|app|domain", "action|event|intent"],
    "optional_fields": [
      "source",
      "domain",
      "url",
      "title",
      "intent",
      "action",
      "stage",
      "object",
      "confidence",
      "text_hint",
    ],
    "examples": [
      {
        "timestamp": "2026-03-09T18:41:00Z",
        "source": "browser_extension",
        "domain": "linkedin.com",
        "intent": "job_search",
        "action": "open_job",
        "stage": "exploration",
        "confidence": 0.92,
      },
      {
        "timestamp": "2026-03-09T18:44:12Z",
        "source": "gmail_api",
        "tool": "gmail",
        "intent": "founder_outreach",
        "action": "send_email",
        "object": "portfolio_founder_followup",
      },
      {
        "timestamp": "2026-03-09T19:02:03Z",
        "source": "docs_adapter",
        "tool": "google_docs",
        "intent": "drafting",
        "action": "edit_document",
        "text_hint": "Updated product strategy brief",
      },
    ],
  }


def _load_intent_events(window_start_ts: int, window_end_ts: int) -> tuple[list[CommandEvent], dict[str, Any] | None]:
  if os.environ.get("WORKFLOW_DISABLE_INTENT_ADAPTER", "0") == "1":
    return [], {"source": "intent_adapter", "kind": "intent_adapter", "events": 0, "disabled": True}

  path = _intent_event_store_path()
  if not path.exists():
    return [], {
      "source": "intent_adapter",
      "kind": "intent_adapter",
      "events": 0,
      "available": False,
      "path": str(path),
      "error": "no_store_file",
    }

  lines = _read_recent_lines(path, max_lines=INTENT_EVENT_MAX_LINES)
  events: list[CommandEvent] = []
  by_source: Counter[str] = Counter()
  last_key = ""
  last_ts = 0
  for line in lines:
    raw = line.strip()
    if not raw:
      continue
    try:
      row = json.loads(raw)
    except json.JSONDecodeError:
      continue
    ts = _parse_timestamp_any(row.get("timestamp"))
    if ts <= 0 or ts < window_start_ts or ts > window_end_ts:
      continue
    action = str(row.get("normalized_action") or "").strip()
    tool = _normalize_tool_key(str(row.get("tool") or ""))
    source = str(row.get("source") or "intent_adapter").strip()
    if not action or not tool:
      continue
    dedupe_key = f"{tool}|{action}|{source}"
    if dedupe_key == last_key and ts - last_ts < 20:
      continue
    last_key = dedupe_key
    last_ts = ts
    by_source[source] += 1
    events.append(
      CommandEvent(
        source=f"intent:{source}",
        timestamp=ts,
        raw=action,
        tool=tool,
        action=action,
      )
    )

  events.sort(key=lambda row: row.timestamp)
  return events, {
    "source": "intent_adapter",
    "kind": "intent_adapter",
    "available": True,
    "events": len(events),
    "path": str(path),
    "sources": [{"name": name, "events": count} for name, count in by_source.most_common(8)],
  }


def _parse_ollama_model_list(raw: str) -> list[str]:
  if not raw:
    return []
  parts = [chunk.strip() for chunk in re.split(r"[\n,]+", str(raw)) if chunk.strip()]
  return parts


def _ollama_model_candidates(*env_keys: str) -> list[str]:
  ordered: list[str] = []
  seen: set[str] = set()

  def _push(model_name: str) -> None:
    clean = str(model_name or "").strip()
    if not clean:
      return
    key = clean.lower()
    if key in seen:
      return
    seen.add(key)
    ordered.append(clean)

  for key in env_keys:
    for item in _parse_ollama_model_list(os.environ.get(key, "")):
      _push(item)

  for item in _parse_ollama_model_list(os.environ.get("WORKFLOW_LLM_MODELS", "")):
    _push(item)

  for item in DEFAULT_OLLAMA_MODELS:
    _push(item)

  return ordered


def _ollama_generate(
  *,
  prompt: str,
  timeout_seconds: float,
  format_json: bool,
  env_keys: tuple[str, ...],
) -> tuple[str, str] | None:
  host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
  endpoint = f"{host}/api/generate"
  models = _ollama_model_candidates(*env_keys)
  if not models:
    return None

  for model in models:
    body: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
    if format_json:
      body["format"] = "json"
    req = urllib.request.Request(
      endpoint,
      data=json.dumps(body).encode("utf-8"),
      headers={"Content-Type": "application/json"},
      method="POST",
    )
    try:
      with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
        response = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
      continue
    raw_text = str(response.get("response", "")).strip()
    if raw_text:
      return raw_text, model
  return None


def _parse_event_timestamp(row: dict[str, Any]) -> int:
  raw = row.get("timestamp") or row.get("time") or row.get("end")
  if raw is None:
    return 0
  if isinstance(raw, (int, float)):
    return int(raw)
  if isinstance(raw, str):
    candidate = raw.strip().replace("Z", "+00:00")
    try:
      return int(datetime.fromisoformat(candidate).timestamp())
    except ValueError:
      return 0
  return 0


def _domain_from_url(url: str) -> str:
  if not url:
    return ""
  try:
    parsed = urlparse(url)
  except ValueError:
    return ""
  host = parsed.netloc.lower()
  if host.startswith("www."):
    host = host[4:]
  return host


def _canonical_site_host(host: str) -> str:
  raw = str(host or "").strip().lower().rstrip(".")
  if raw.startswith("www."):
    raw = raw[4:]
  if not raw:
    return ""
  labels = [part for part in raw.split(".") if part]
  if len(labels) < 2:
    return raw
  if raw.endswith(".google.com") and len(labels) >= 3 and labels[-3] in {
    "docs",
    "sheets",
    "slides",
    "drive",
    "mail",
    "calendar",
    "meet",
    "gemini",
  }:
    return ".".join(labels[-3:])
  if raw.endswith(".microsoft.com") and len(labels) >= 3 and labels[-3] in {"teams", "outlook"}:
    return ".".join(labels[-3:])
  if raw.endswith(".office.com") and len(labels) >= 3 and labels[-3] in {"powerpoint", "outlook"}:
    return ".".join(labels[-3:])
  common_second_level = {"co", "com", "org", "net", "gov", "edu", "ac"}
  if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in common_second_level:
    return ".".join(labels[-3:])
  return ".".join(labels[-2:])


def _domain_from_text(text: str) -> str:
  raw = str(text or "").strip().lower()
  if not raw:
    return ""
  match = DOMAIN_IN_TEXT_RE.search(raw)
  if not match:
    return ""
  domain = _canonical_site_host(match.group(1))
  suffix = domain.rsplit(".", 1)[-1] if "." in domain else ""
  if suffix in NON_SITE_SUFFIXES:
    return ""
  return domain


def _site_from_browser_title(title: str) -> str:
  raw = str(title or "").strip()
  if not raw:
    return ""

  lowered = raw.lower()
  trimmed = raw
  for token in BROWSER_TITLE_STRIP_TOKENS:
    pos = lowered.find(token)
    if pos > 0:
      trimmed = raw[:pos].strip()
      break

  direct = _domain_from_text(trimmed) or _domain_from_text(raw)
  if direct:
    return direct

  probe = f"{trimmed} {raw}".lower()
  for needle, domain in BROWSER_TITLE_SITE_HINTS:
    if needle in probe:
      return domain
  return ""


def _extract_browser_visit_domain(action: str) -> str:
  raw = str(action or "").strip()
  lower = raw.lower()
  if not lower.startswith("browser visit "):
    return ""
  domain = raw[len("browser visit ") :].strip().lower()
  domain = re.sub(r"^https?://", "", domain)
  domain = re.sub(r"^www\.", "", domain)
  return re.split(r"[/?#\s]", domain, maxsplit=1)[0].strip(".")


def _tool_from_browser_context(domain: str, title: str = "") -> str:
  clean_domain = str(domain or "").strip().lower()
  clean_title = str(title or "").strip().lower()
  probe = f"{clean_domain} {clean_title}"
  for needle, tool in BROWSER_DOMAIN_TOOL_HINTS:
    if needle in probe:
      return tool
  if "google docs" in probe:
    return "google_docs"
  if "google sheets" in probe:
    return "google_sheets"
  if "google slides" in probe:
    return "google_slides"
  if "powerpoint" in probe:
    return "powerpoint"
  if "granola" in probe:
    return "granola"
  return "browser"


def _normalize_activitywatch_event(data: dict[str, Any]) -> tuple[str, str] | None:
  app = str(data.get("app") or data.get("application") or "").strip().lower()
  title = str(data.get("title") or "").strip()
  url = str(data.get("url") or "").strip()

  mapped = APP_TO_TOOL.get(app) or APP_TO_TOOL.get(app.replace(".app", ""))
  tool = mapped or app.split(" ", 1)[0] or "desktop"
  title_lower = title.lower()
  if tool in {"microsoft", "office"} and "powerpoint" in title_lower:
    tool = "powerpoint"
  elif tool in {"microsoft", "office"} and "excel" in title_lower:
    tool = "excel"
  elif tool == "google" and "docs" in title_lower:
    tool = "google_docs"
  elif tool == "google" and "slides" in title_lower:
    tool = "google_slides"
  elif tool == "google" and "sheets" in title_lower:
    tool = "google_sheets"
  elif tool == "google" and "calendar" in title_lower:
    tool = "google_calendar"
  elif tool == "google" and "meet" in title_lower:
    tool = "google_meet"
  elif tool == "google" and "gemini" in title_lower:
    tool = "gemini"
  elif tool == "google" and "mail" in title_lower:
    tool = "gmail"
  elif tool == "browser" and "granola" in title_lower:
    tool = "granola"

  if tool in {"unknown", "desktop"} and not title and not url:
    return None

  if url:
    domain = _canonical_site_host(_domain_from_url(url))
    if domain:
      browser_tool = _tool_from_browser_context(domain, title)
      return browser_tool, f"browser visit {domain}"
    return "browser", "browser browse"

  if tool == "browser":
    site = _site_from_browser_title(title)
    if site:
      browser_tool = _tool_from_browser_context(site, title)
      return browser_tool, f"browser visit {site}"
    return None

  if tool in {"code", "terminal"}:
    return tool, f"{tool} active"
  if tool in {
    "notion",
    "slack",
    "figma",
    "mail",
    "gmail",
    "zoom",
    "teams",
    "powerpoint",
    "excel",
    "granola",
    "google_docs",
    "google_sheets",
    "google_slides",
    "google_calendar",
    "google_meet",
    "gemini",
  }:
    return tool, f"{tool} active"
  if app:
    return tool, f"{tool} active"
  if title:
    return "desktop", "desktop active"
  return None


def _load_activitywatch_events(window_start_ts: int, window_end_ts: int) -> tuple[list[CommandEvent], dict[str, Any] | None]:
  if os.environ.get("WORKFLOW_DISABLE_ACTIVITYWATCH", "0") == "1":
    return [], {"source": "activitywatch", "kind": "activitywatch", "events": 0, "disabled": True}

  base_url = os.environ.get("ACTIVITYWATCH_API", "http://127.0.0.1:5600/api/0").rstrip("/")
  # ActivityWatch API expects trailing slash here; without it some versions return HTTP 308.
  bucket_url = f"{base_url}/buckets/"
  try:
    payload = _fetch_json(bucket_url, timeout_seconds=1.2)
  except Exception as exc:
    return [], {
      "source": "activitywatch",
      "kind": "activitywatch",
      "events": 0,
      "available": False,
      "error": str(exc),
    }

  if not isinstance(payload, dict):
    return [], {
      "source": "activitywatch",
      "kind": "activitywatch",
      "events": 0,
      "available": False,
      "error": "invalid_buckets_payload",
    }

  start_iso = quote(_utc_iso(window_start_ts), safe="")
  end_iso = quote(_utc_iso(window_end_ts), safe="")

  candidate_ids = [bucket_id for bucket_id in payload.keys() if "aw-watcher" in str(bucket_id)]
  candidate_ids = candidate_ids[:8]
  events: list[CommandEvent] = []
  bucket_count = 0
  for bucket_id in candidate_ids:
    event_url = (
      f"{base_url}/buckets/{quote(str(bucket_id), safe='')}/events"
      f"?start={start_iso}&end={end_iso}&limit={ACTIVITYWATCH_MAX_EVENTS_PER_BUCKET}"
    )
    try:
      rows = _fetch_json(event_url, timeout_seconds=2.0)
    except Exception:
      continue

    if not isinstance(rows, list):
      continue
    bucket_count += 1
    last_action = ""
    for row in rows:
      if not isinstance(row, dict):
        continue
      ts = _parse_event_timestamp(row)
      if ts <= 0 or ts < window_start_ts:
        continue
      parsed = _normalize_activitywatch_event(row.get("data") or {})
      if parsed is None:
        continue
      tool, action = parsed
      if not action or action == last_action:
        continue
      last_action = action
      events.append(
        CommandEvent(
          source=f"activitywatch:{bucket_id}",
          timestamp=ts,
          raw=action,
          tool=tool,
          action=action,
        )
      )

  events.sort(key=lambda row: row.timestamp)
  return events, {
    "source": "activitywatch",
    "kind": "activitywatch",
    "available": True,
    "buckets_considered": len(candidate_ids),
    "buckets_used": bucket_count,
    "events": len(events),
  }


def _build_sessions(events: list[CommandEvent]) -> list[list[CommandEvent]]:
  if not events:
    return []

  sessions: list[list[CommandEvent]] = []
  current: list[CommandEvent] = [events[0]]

  for event in events[1:]:
    last = current[-1]
    time_gap = max(0, event.timestamp - last.timestamp)
    if time_gap > SESSION_GAP_SECONDS or len(current) >= 150:
      if len(current) >= MIN_STEPS_PER_SESSION:
        sessions.append(current)
      current = [event]
      continue
    current.append(event)

  if len(current) >= MIN_STEPS_PER_SESSION:
    sessions.append(current)

  return sessions


def _session_actions(session: list[CommandEvent]) -> list[str]:
  actions: list[str] = []
  for event in session:
    if not actions or actions[-1] != event.action:
      actions.append(event.action)
  return actions


def _is_contained(seq: tuple[str, ...], selected: tuple[str, ...]) -> bool:
  if len(seq) > len(selected):
    return False
  width = len(seq)
  for idx in range(0, len(selected) - width + 1):
    if tuple(selected[idx : idx + width]) == seq:
      return True
  return False


def _tool_keys_from_action(action: str) -> list[str]:
  raw = str(action or "").strip()
  if not raw:
    return []
  lower = raw.lower()
  if lower.startswith("browser visit "):
    domain = _extract_browser_visit_domain(raw)
    if not domain:
      return ["browser"]
    mapped = _tool_from_browser_context(domain)
    if mapped == "browser":
      return ["browser"]
    return ["browser", mapped]
  tool = lower.split(" ", 1)[0].strip()
  return [tool] if tool else []


def _tools_from_sequence(seq: tuple[str, ...]) -> list[str]:
  seen: set[str] = set()
  tools: list[str] = []
  for step in seq:
    for tool in _tool_keys_from_action(step):
      if tool and tool not in seen:
        seen.add(tool)
        tools.append(tool)
  return tools


def _workflow_sites_from_sequence(seq: tuple[str, ...]) -> list[str]:
  sites: list[str] = []
  seen: set[str] = set()
  for step in seq:
    site = _extract_browser_visit_domain(step)
    if not site or site in seen:
      continue
    seen.add(site)
    sites.append(site)
  return sites


def _tool_phrase_for_workflow(tools: list[str], limit: int = 3) -> str:
  primary = _summary_primary_tools(tools, limit=limit)
  labels: list[str] = []
  seen: set[str] = set()
  for tool in primary:
    label = _friendly_tool_name(tool).strip()
    low = label.lower()
    if not label or low in seen:
      continue
    seen.add(low)
    labels.append(label)
  if not labels:
    return "core tools"
  if len(labels) == 1:
    return labels[0]
  if len(labels) == 2:
    return f"{labels[0]} and {labels[1]}"
  return f"{labels[0]}, {labels[1]}, and {labels[2]}"


def _workflow_details_text(
  seq: tuple[str, ...],
  tools: list[str],
  total_runs: int,
  support_sessions: int,
  window_days: int,
  grouped_variants: int = 1,
) -> str:
  tool_line = _tool_phrase_for_workflow(tools, limit=3)
  site_line = _workflow_sites_from_sequence(seq)[:2]
  detail = (
    f"Observed {total_runs} repeated runs across {support_sessions} activity sessions in the last {window_days} days "
    f"using {tool_line}."
  )
  if site_line:
    detail += f" Key sites: {', '.join(site_line)}."
  if grouped_variants > 1:
    detail += f" Grouped from {grouped_variants} similar workflow variants."
  return detail


def _tool_workflow_step_rows(actions: list[str]) -> list[dict[str, Any]]:
  cleaned = [str(item).strip() for item in actions if str(item).strip()]
  if not cleaned:
    return []
  return [
    {
      "order": idx + 1,
      "action": action,
      "tool": (_tool_keys_from_action(action) or [action.split(" ", 1)[0].strip().lower()])[0],
    }
    for idx, action in enumerate(cleaned[:8])
  ]


def _tool_signal_workflows(
  existing_workflows: list[dict[str, Any]],
  events: list[CommandEvent],
  window_days: int,
  max_workflows: int,
) -> list[dict[str, Any]]:
  slots = max(0, int(max_workflows) - len(existing_workflows))
  if slots <= 0:
    return []

  covered: set[str] = set()
  for workflow in existing_workflows:
    for tool in workflow.get("tools") or []:
      key = _normalize_tool_key(str(tool))
      if key:
        covered.add(key)

  source_events = _events_for_behavioral_analysis(events)
  if not source_events:
    return []

  stats: dict[str, dict[str, Any]] = {}
  sorted_events = sorted(source_events, key=lambda row: row.timestamp)
  for idx, event in enumerate(sorted_events):
    next_ts = 0
    if idx + 1 < len(sorted_events):
      next_event = sorted_events[idx + 1]
      if datetime.fromtimestamp(next_event.timestamp).date() == datetime.fromtimestamp(event.timestamp).date():
        next_ts = next_event.timestamp
    if next_ts > event.timestamp:
      duration_seconds = max(60, min(20 * 60, next_ts - event.timestamp))
    else:
      duration_seconds = 180
    minutes = max(1, int(round(duration_seconds / 60)))

    _, tool_key = _tool_label_from_event(event)
    key = _normalize_tool_key(tool_key)
    if not key:
      continue
    row = stats.get(key)
    if row is None:
      row = {
        "minutes": 0,
        "events": 0,
        "last_seen": event.timestamp,
        "actions": [],
      }
      stats[key] = row
    row["minutes"] += minutes
    row["events"] += 1
    row["last_seen"] = max(int(row["last_seen"]), int(event.timestamp))
    action = str(event.action or "").strip()
    if action and action not in row["actions"] and len(row["actions"]) < 5:
      row["actions"].append(action)

  candidates: list[tuple[str, dict[str, Any]]] = []
  for key in TOOL_WORKFLOW_PRIORITY:
    row = stats.get(key)
    if not row:
      continue
    if key in covered:
      continue
    if int(row.get("events", 0)) < 2 and int(row.get("minutes", 0)) < 5:
      continue
    candidates.append((key, row))

  generated: list[dict[str, Any]] = []
  for idx, (key, row) in enumerate(candidates[:slots], start=1):
    name = TOOL_WORKFLOW_NAME.get(key, f"{_friendly_tool_name(key)} Workflow")
    category = TOOL_WORKFLOW_CATEGORY.get(key, "general")
    actions = row.get("actions") or [f"{key} active"]
    event_count = max(1, int(row.get("events", 1)))
    minutes = max(1, int(row.get("minutes", 1)))
    sessions = max(1, min(event_count, int(round(event_count / 4))))
    details = (
      f"Detected {event_count} repeated events ({minutes} min) in the last {window_days} days using "
      f"{_friendly_tool_name(key)}."
    )
    generated.append(
      {
        "id": f"wf-tool-{idx}-{key}",
        "name": name,
        "details": details,
        "category": category,
        "confidence": round(min(0.9, 0.45 + event_count * 0.04), 2),
        "tools": [key],
        "steps": _tool_workflow_step_rows(actions),
        "frequency": {
          "runs_total": event_count,
          "sessions": sessions,
          "per_week": round((event_count / max(1, window_days)) * 7, 2),
          "last_seen": _to_iso(int(row.get("last_seen", int(time.time())))),
        },
        "automation_ideas": [],
      }
    )
  return generated


def _classify_category(seq: tuple[str, ...], tools: list[str]) -> tuple[str, float]:
  tokens = set(tools)
  for step in seq:
    for token in step.split(" "):
      cleaned = token.strip().lower()
      if cleaned:
        tokens.add(cleaned)

  scores: dict[str, float] = {}
  for category, keywords in CATEGORY_RULES.items():
    score = 0.0
    for token in tokens:
      if token in keywords:
        score += 1.0
    scores[category] = score

  if "git" in tokens:
    scores["engineering"] = scores.get("engineering", 0.0) + 0.8
  if "docker" in tokens or "kubectl" in tokens:
    scores["ops"] = scores.get("ops", 0.0) + 0.8
  if "browser" in tokens:
    scores["research"] = scores.get("research", 0.0) + 0.6

  best_category = max(scores, key=scores.get, default="general")
  best_score = scores.get(best_category, 0.0)
  if best_score <= 0:
    return "general", 0.0
  return best_category, best_score


def _workflow_name(seq: tuple[str, ...], tools: list[str], category: str) -> str:
  tool_set = set(tools)
  if {"google_docs", "powerpoint"} <= tool_set or {"google_docs", "google_slides"} <= tool_set:
    return "Docs to Deck Workflow"
  if {"google_docs", "google_sheets"} <= tool_set:
    return "Docs to Sheets Workflow"
  if {"google_docs", "gmail"} <= tool_set or {"google_docs", "mail"} <= tool_set:
    return "Docs and Email Workflow"
  if {"codex", "google_docs"} <= tool_set:
    return "Docs to Codex Draft Workflow"
  if {"granola", "google_docs"} <= tool_set or {"granola", "powerpoint"} <= tool_set:
    return "Meeting Notes to Deliverable Workflow"
  if "granola" in tool_set:
    return "Granola Notes Workflow"
  if {"salesforce", "gmail"} <= tool_set or {"salesforce", "mail"} <= tool_set:
    return "CRM Follow-up Workflow"
  if {"hubspot", "gmail"} <= tool_set or {"hubspot", "mail"} <= tool_set:
    return "HubSpot Follow-up Workflow"
  if "powerpoint" in tool_set and "excel" in tool_set:
    return "Data to Deck Reporting Workflow"
  if "powerpoint" in tool_set:
    return "PowerPoint Build Workflow"

  if category == "engineering":
    if "git" in tool_set and {"pytest", "ruff", "mypy"} & tool_set:
      return "Code Quality and Commit Loop"
    if "git" in tool_set and {"npm", "pnpm", "yarn", "vite"} & tool_set:
      return "Build-Test-Commit Loop"
    if "git" in tool_set:
      return "Code Review and Commit Loop"
  if category == "ops":
    if {"docker", "kubectl"} & tool_set:
      return "Container Deploy and Validate Cycle"
    if {"aws", "gcloud", "az"} & tool_set:
      return "Cloud Ops Command Cycle"
  if category == "research":
    if {"browser", "google_docs"} <= tool_set:
      return "Research to Document Synthesis Flow"
    if {"browser", "gemini", "codex"} <= tool_set:
      return "Research and Draft Iteration Flow"
    if {"rg", "grep", "browser"} & tool_set:
      return "Research and Evidence Synthesis Flow"
    return "Research Capture Workflow"
  if category == "gtm":
    return "GTM Execution Workflow"
  if category == "analytics":
    return "Analysis and Reporting Workflow"
  if len(tools) >= 2:
    return f"{_friendly_tool_name(tools[0])} to {_friendly_tool_name(tools[1])} Workflow"
  if tools:
    return f"{_friendly_tool_name(tools[0])} Workflow"
  return "Repeated Workflow"


WORKFLOW_NAME_STOPWORDS = {
  "workflow",
  "flow",
  "loop",
  "cycle",
  "process",
  "and",
  "to",
  "the",
  "a",
  "an",
}


def _workflow_name_tokens(value: str) -> set[str]:
  cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
  if not cleaned:
    return set()
  return {token for token in cleaned.split() if token and token not in WORKFLOW_NAME_STOPWORDS}


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
  if not left and not right:
    return 1.0
  if not left or not right:
    return 0.0
  union = left | right
  if not union:
    return 0.0
  return len(left & right) / len(union)


def _workflow_action_tokens(workflow: dict[str, Any]) -> set[str]:
  tokens: set[str] = set()
  for step in (workflow.get("steps") or [])[:8]:
    action = str(step.get("action", "")).strip().lower()
    if not action:
      continue
    head = action.split(" ", 1)[0].strip()
    if head and head not in {"active", "run", "open"}:
      tokens.add(head)
    tail = action.split(" ", 1)[1].strip() if " " in action else ""
    if tail and tail not in {"active"}:
      tokens.add(tail)
  return tokens


def _are_workflows_similar(left: dict[str, Any], right: dict[str, Any]) -> bool:
  left_name = _workflow_name_tokens(str(left.get("name", "")))
  right_name = _workflow_name_tokens(str(right.get("name", "")))
  name_score = _jaccard_similarity(left_name, right_name)
  if left_name and right_name and name_score >= 0.82:
    return True

  left_tools = {str(tool).strip().lower() for tool in (left.get("tools") or []) if str(tool).strip()}
  right_tools = {str(tool).strip().lower() for tool in (right.get("tools") or []) if str(tool).strip()}
  tool_score = _jaccard_similarity(left_tools, right_tools)
  step_score = _jaccard_similarity(_workflow_action_tokens(left), _workflow_action_tokens(right))
  same_category = str(left.get("category", "")).strip().lower() == str(right.get("category", "")).strip().lower()

  if same_category and name_score >= 0.55 and tool_score >= 0.5:
    return True
  if same_category and name_score >= 0.3 and tool_score >= 0.88 and step_score >= 0.7:
    return True
  return False


def _merge_workflow_group(group: list[dict[str, Any]], index: int, window_days: int) -> dict[str, Any]:
  if not group:
    return {}
  ranked = sorted(
    group,
    key=lambda row: (
      float((row.get("frequency") or {}).get("per_week", 0.0)),
      int((row.get("frequency") or {}).get("runs_total", 0)),
      float(row.get("confidence", 0.0)),
    ),
    reverse=True,
  )
  primary = ranked[0]

  tool_counter: Counter[str] = Counter()
  for row in group:
    for tool in row.get("tools") or []:
      token = str(tool).strip().lower()
      if token:
        tool_counter[token] += 1
  tools = [tool for tool, _ in tool_counter.most_common(8)]

  best_runs = max(int((row.get("frequency") or {}).get("runs_total", 0)) for row in group)
  best_sessions = max(int((row.get("frequency") or {}).get("sessions", 0)) for row in group)
  best_per_week = max(float((row.get("frequency") or {}).get("per_week", 0.0)) for row in group)
  latest_seen = max(
    (
      int(datetime.fromisoformat(str((row.get("frequency") or {}).get("last_seen", _to_iso(int(time.time())))).replace("Z", "+00:00")).timestamp())
      if str((row.get("frequency") or {}).get("last_seen", "")).strip()
      else int(time.time())
    )
    for row in group
  )

  primary_seq = tuple(
    str(step.get("action") or "").strip() for step in (primary.get("steps") or []) if str(step.get("action") or "").strip()
  )
  details = _workflow_details_text(
    seq=primary_seq,
    tools=tools or [str(tool).strip().lower() for tool in (primary.get("tools") or []) if str(tool).strip()],
    total_runs=best_runs,
    support_sessions=best_sessions,
    window_days=window_days,
    grouped_variants=len(group),
  )

  merged = {
    "id": str(primary.get("id") or f"wf-{index}"),
    "name": str(primary.get("name") or "Workflow"),
    "details": details,
    "category": str(primary.get("category") or "general"),
    "confidence": round(
      max(float(row.get("confidence", 0.0)) for row in group),
      2,
    ),
    "tools": tools or [str(tool).strip().lower() for tool in (primary.get("tools") or []) if str(tool).strip()],
    "steps": (primary.get("steps") or [])[:8],
    "frequency": {
      "runs_total": best_runs,
      "sessions": best_sessions,
      "per_week": round(best_per_week, 2),
      "last_seen": _to_iso(latest_seen),
    },
    "automation_ideas": [],
    "grouped_workflow_count": len(group),
  }
  return merged


def _group_similar_workflows(workflows: list[dict[str, Any]], max_workflows: int, window_days: int) -> list[dict[str, Any]]:
  if len(workflows) <= 1:
    return workflows

  ranked = sorted(
    workflows,
    key=lambda row: (
      float((row.get("frequency") or {}).get("per_week", 0.0)),
      int((row.get("frequency") or {}).get("runs_total", 0)),
      float(row.get("confidence", 0.0)),
    ),
    reverse=True,
  )

  groups: list[list[dict[str, Any]]] = []
  for workflow in ranked:
    matched = False
    for group in groups:
      if _are_workflows_similar(workflow, group[0]):
        group.append(workflow)
        matched = True
        break
    if not matched:
      groups.append([workflow])

  merged_rows = [_merge_workflow_group(group, idx + 1, window_days=window_days) for idx, group in enumerate(groups)]
  merged_rows = [row for row in merged_rows if row]
  merged_rows.sort(
    key=lambda row: (
      float((row.get("frequency") or {}).get("per_week", 0.0)),
      int((row.get("frequency") or {}).get("runs_total", 0)),
      float(row.get("confidence", 0.0)),
    ),
    reverse=True,
  )
  return merged_rows[: max(1, int(max_workflows))]


def _idea_templates_for_workflow(workflow: dict[str, Any]) -> list[dict[str, str]]:
  category = str(workflow.get("category") or "general").lower()
  templates = CATEGORY_IDEA_LIBRARY.get(category) or CATEGORY_IDEA_LIBRARY["general"]
  return templates[:2]


def _heuristic_ideas(workflow: dict[str, Any]) -> list[dict[str, str]]:
  tools_line = ", ".join(workflow.get("tools", [])[:4])
  ideas: list[dict[str, str]] = []
  for idx, item in enumerate(_idea_templates_for_workflow(workflow), start=1):
    ideas.append(
      {
        "id": f"{workflow['id']}-idea-{idx}",
        "title": item["title"],
        "proposal": item["proposal"],
        "impact": item["impact"],
        "effort": item["effort"],
        "tools_hint": tools_line,
      }
    )
  return ideas


def _extract_json_block(text: str) -> str | None:
  start = text.find("{")
  if start < 0:
    return None
  depth = 0
  for idx in range(start, len(text)):
    char = text[idx]
    if char == "{":
      depth += 1
    elif char == "}":
      depth -= 1
      if depth == 0:
        return text[start : idx + 1]
  return None


def _llm_ideas_from_ollama(workflows: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]] | None:
  if not workflows:
    return None

  compact = [
    {
      "workflow_id": row["id"],
      "name": row["name"],
      "category": row["category"],
      "tools": row["tools"],
      "steps": [step["action"] for step in row["steps"]],
      "frequency_per_week": row["frequency"]["per_week"],
    }
    for row in workflows
  ]

  prompt = (
    "You are an automation architect. "
    "Given workflows, suggest at most 2 automation ideas per workflow. "
    "Return JSON only with shape: "
    '{"ideas":[{"workflow_id":"...","title":"...","proposal":"...","impact":"...","effort":"Low|Medium|High"}]}'
    f"\nWorkflows:\n{json.dumps(compact, ensure_ascii=True)}"
  )

  generated = _ollama_generate(
    prompt=prompt,
    timeout_seconds=4,
    format_json=True,
    env_keys=("WORKFLOW_LLM_MODEL",),
  )
  if not generated:
    return None
  raw_text, _used_model = generated

  parsed_payload: dict[str, Any] | None = None
  try:
    parsed_payload = json.loads(raw_text)
  except json.JSONDecodeError:
    block = _extract_json_block(raw_text)
    if block:
      try:
        parsed_payload = json.loads(block)
      except json.JSONDecodeError:
        parsed_payload = None

  if not isinstance(parsed_payload, dict):
    return None

  rows = parsed_payload.get("ideas")
  if not isinstance(rows, list):
    return None

  valid_ids = {row["id"] for row in workflows}
  by_workflow: dict[str, list[dict[str, str]]] = defaultdict(list)
  for idx, row in enumerate(rows):
    if not isinstance(row, dict):
      continue
    workflow_id = str(row.get("workflow_id", "")).strip()
    if workflow_id not in valid_ids:
      continue
    title = str(row.get("title", "")).strip()
    proposal = str(row.get("proposal", "")).strip()
    if not title or not proposal:
      continue
    impact = str(row.get("impact", "Improves speed and consistency.")).strip()
    effort = str(row.get("effort", "Medium")).strip() or "Medium"
    by_workflow[workflow_id].append(
      {
        "id": f"{workflow_id}-llm-{idx + 1}",
        "title": title,
        "proposal": proposal,
        "impact": impact,
        "effort": effort,
      }
    )

  return dict(by_workflow) if by_workflow else None


def _friendly_tool_name(tool: str) -> str:
  key = str(tool or "").strip().lower()
  mapping = {
    "browser": "Web Browser",
    "mail": "Email",
    "gmail": "Gmail",
    "google_docs": "Google Docs",
    "google_sheets": "Google Sheets",
    "google_slides": "Google Slides",
    "google_drive": "Google Drive",
    "google_calendar": "Google Calendar",
    "google_meet": "Google Meet",
    "powerpoint": "PowerPoint",
    "granola": "Granola",
    "gemini": "Gemini",
    "linkedin": "LinkedIn",
    "salesforce": "Salesforce",
    "hubspot": "HubSpot",
    "slack": "Slack",
    "notion": "Notion",
    "code": "Code Editor",
    "terminal": "Terminal",
    "python": "Python",
    "git": "Git",
    "sheet": "Google Sheets",
    "sheets": "Google Sheets",
    "excel": "Excel",
    "codex": "Codex",
    "claude": "Claude",
    "curl": "Curl",
    "pkill": "Pkill",
  }
  if key in mapping:
    return mapping[key]
  if not key:
    return "Tool"
  words = re.sub(r"[_\-]+", " ", key).split()
  return " ".join(part.capitalize() for part in words)


def _workflow_text_blob(workflow: dict[str, Any]) -> str:
  pieces: list[str] = []
  pieces.append(str(workflow.get("name") or ""))
  pieces.append(str(workflow.get("details") or ""))
  pieces.append(str(workflow.get("category") or ""))
  for tool in workflow.get("tools") or []:
    pieces.append(str(tool))
  for step in workflow.get("steps") or []:
    pieces.append(str(step.get("action") or ""))
    pieces.append(str(step.get("tool") or ""))
  return " ".join(pieces).lower()


def _contains_token(text: str, token: str) -> bool:
  normalized = str(token or "").strip().lower()
  if not normalized:
    return False
  if " " in normalized:
    return normalized in text
  return bool(re.search(rf"\b{re.escape(normalized)}\b", text))


def _infer_workflow_intent(workflow: dict[str, Any]) -> dict[str, Any]:
  text = _workflow_text_blob(workflow)
  candidates = [
    {
      "label": "researching open roles and preparing job applications",
      "tokens": {
        "job": 4,
        "jobs": 4,
        "career": 3,
        "application": 3,
        "applications": 3,
        "recruiter": 3,
        "hiring": 2,
        "resume": 3,
        "cv": 3,
        "cover letter": 3,
        "linkedin": 3,
      },
    },
    {
      "label": "sending outreach or follow-ups to portfolio founders and operators",
      "tokens": {
        "portfolio": 5,
        "founder": 5,
        "founders": 5,
        "operator": 3,
        "operators": 3,
        "investor": 3,
        "intro": 2,
        "outreach": 2,
        "mail": 1,
        "gmail": 1,
        "email": 1,
        "slack": 1,
      },
    },
    {
      "label": "performing customer or market research synthesis",
      "tokens": {
        "research": 3,
        "evidence": 2,
        "source": 2,
        "synthesis": 3,
        "analysis": 2,
        "browser": 1,
        "notion": 1,
        "report": 2,
        "summary": 2,
      },
    },
    {
      "label": "coordinating internal operations and admin follow-through",
      "tokens": {
        "admin": 3,
        "ops": 3,
        "invoice": 3,
        "calendar": 2,
        "meeting": 2,
        "slack": 1,
        "mail": 1,
        "sheet": 1,
        "excel": 1,
      },
    },
    {
      "label": "executing a build-and-deliver engineering loop",
      "tokens": {
        "git": 2,
        "code": 2,
        "build": 3,
        "test": 3,
        "deploy": 3,
        "commit": 3,
        "python": 1,
        "npm": 2,
        "pytest": 2,
      },
    },
  ]

  ranked: list[dict[str, Any]] = []
  for row in candidates:
    score = 0
    evidence: list[str] = []
    for token, weight in row["tokens"].items():
      if _contains_token(text, token):
        score += int(weight)
        evidence.append(token)
    ranked.append({"label": row["label"], "score": score, "evidence": evidence})

  ranked.sort(key=lambda item: int(item["score"]), reverse=True)
  primary = ranked[0] if ranked else {"label": "general knowledge work execution", "score": 0, "evidence": []}
  secondary = ranked[1] if len(ranked) > 1 else {"label": "", "score": 0, "evidence": []}

  primary_score = int(primary["score"])
  if primary_score >= 8:
    confidence = "high"
  elif primary_score >= 4:
    confidence = "medium"
  else:
    confidence = "low"

  if primary_score <= 1:
    label = "general context building and execution support"
  else:
    label = str(primary["label"])

  alternatives: list[str] = []
  if int(secondary["score"]) > 0 and int(secondary["score"]) >= max(2, int(primary_score * 0.6)):
    alternatives.append(str(secondary["label"]))

  evidence = [str(item) for item in primary.get("evidence", [])][:4]
  return {
    "label": label,
    "confidence": confidence,
    "evidence": evidence,
    "alternatives": alternatives,
  }


def _intent_lead_sentence(workflow: dict[str, Any]) -> str:
  intent = _infer_workflow_intent(workflow)
  label = str(intent.get("label") or "general context building and execution support")
  confidence = str(intent.get("confidence") or "low")
  evidence = intent.get("evidence") or []
  alternatives = intent.get("alternatives") or []
  if evidence:
    evidence_line = ", ".join(str(item) for item in evidence)
    sentence = f"Likely intent: {label} ({confidence} confidence), based on signals like {evidence_line}."
  else:
    sentence = f"Likely intent: {label} ({confidence} confidence), inferred from repeated tool transitions and task cadence."
  if alternatives:
    sentence += f" A secondary interpretation is {alternatives[0]}."
  return sentence


def _normalize_tool_key(tool: str) -> str:
  raw = str(tool or "").strip().lower()
  if not raw:
    return ""
  if raw.startswith("browser:"):
    maybe_domain = raw.replace("browser:", "", 1).strip()
    mapped = _tool_from_browser_context(maybe_domain)
    if mapped != "browser":
      return mapped
    return "browser"
  if raw in MCP_TOOL_SYNONYMS:
    return MCP_TOOL_SYNONYMS[raw]
  for token in (
    "google docs",
    "google slides",
    "google sheets",
    "google drive",
    "google calendar",
    "google meet",
    "powerpoint",
    "granola",
    "gemini",
    "salesforce",
    "hubspot",
    "google sheets",
    "microsoft teams",
    "web browser",
    "gmail",
    "mail",
    "slack",
    "notion",
    "calendar",
    "zoom",
    "terminal",
    "git",
    "excel",
    "codex",
    "claude",
    "python",
    "curl",
  ):
    if token in raw:
      return MCP_TOOL_SYNONYMS.get(token, token)
  first = raw.split(" ", 1)[0]
  if first and "." in first:
    mapped = _tool_from_browser_context(first)
    if mapped != "browser":
      return mapped
  return MCP_TOOL_SYNONYMS.get(first, first)


def _pretty_tool_name(tool: str) -> str:
  text = re.sub(r"[_\-]+", " ", str(tool or "").strip())
  low = text.lower()
  special = {
    "codex": "Codex",
    "claude": "Claude",
    "python": "Python",
    "curl": "Curl",
    "pkill": "Pkill",
  }
  if low in special:
    return special[low]
  if not text:
    return "Tool"
  return " ".join(part.capitalize() for part in text.split())


def _browser_domains_from_workflow(workflow: dict[str, Any]) -> list[str]:
  domains: list[str] = []
  seen: set[str] = set()
  for step in (workflow.get("steps") or []):
    action = str(step.get("action") or "").strip()
    match = re.match(r"browser\s+visit\s+(.+)$", action, flags=re.IGNORECASE)
    if not match:
      continue
    raw = str(match.group(1) or "").strip().lower()
    if not raw:
      continue
    raw = re.sub(r"^https?://", "", raw)
    raw = re.sub(r"^www\.", "", raw)
    domain = re.split(r"[/?#\s]", raw, maxsplit=1)[0].strip(".")
    if domain and domain not in seen:
      seen.add(domain)
      domains.append(domain)
  return domains[:3]


def _observed_tool_sequence(workflow: dict[str, Any]) -> list[str]:
  observed: list[str] = []
  seen: set[str] = set()
  for tool in (workflow.get("tools") or []):
    raw = str(tool or "").strip()
    if not raw:
      continue
    key = raw.lower()
    if key in seen:
      continue
    seen.add(key)
    observed.append(raw)

  for step in (workflow.get("steps") or []):
    action = str(step.get("action") or "").strip()
    if not action:
      continue
    for step_tool in _tool_keys_from_action(action):
      key = step_tool.lower()
      if key in seen:
        continue
      seen.add(key)
      observed.append(step_tool)
  return observed


def _stack_entry_from_observed_tool(raw_tool: str, browser_domains: list[str]) -> dict[str, str]:
  key = _normalize_tool_key(raw_tool)
  template = MCP_TOOL_LIBRARY.get(key)
  if template:
    tool_name = str(template.get("tool", _pretty_tool_name(raw_tool)))
    purpose = str(template.get("purpose", "Support observed workflow steps for this tool."))
    if key == "browser" and browser_domains:
      top_domains = ", ".join(browser_domains[:2])
      tool_name = f"Web Browser ({top_domains})"
      purpose = f"Work with observed browser activity on {top_domains}."
    return {
      "tool": tool_name,
      "mcp_server": str(template.get("mcp_server", "custom")),
      "purpose": purpose,
    }

  safe_server = re.sub(r"[^a-z0-9_]+", "_", key or str(raw_tool).strip().lower()).strip("_") or "custom_tool"
  return {
    "tool": _pretty_tool_name(raw_tool),
    "mcp_server": safe_server,
    "purpose": "Support observed workflow steps for this tool.",
  }


def _align_stack_and_required_tools_to_workflow(
  workflow: dict[str, Any],
  stack_rows: list[dict[str, str]],
  required_tools: list[str],
) -> tuple[list[dict[str, str]], list[str]]:
  observed_stack = _infer_technical_stack(workflow)
  if not observed_stack:
    return stack_rows[:8], required_tools[:8]

  allowed_by_key: dict[str, list[dict[str, str]]] = {}
  for row in observed_stack:
    key = _normalize_tool_key(str(row.get("tool", "")))
    if not key:
      continue
    allowed_by_key.setdefault(key, []).append(row)

  sanitized_stack: list[dict[str, str]] = []
  key_cursor: dict[str, int] = {}
  for row in stack_rows:
    key = _normalize_tool_key(str(row.get("tool", "")))
    if not key or key not in allowed_by_key:
      continue
    choices = allowed_by_key[key]
    cursor = key_cursor.get(key, 0)
    picked = choices[min(cursor, len(choices) - 1)]
    key_cursor[key] = cursor + 1
    if not any(str(existing.get("tool", "")).lower() == str(picked.get("tool", "")).lower() for existing in sanitized_stack):
      sanitized_stack.append(picked)

  if not sanitized_stack:
    sanitized_stack = observed_stack[:]
  else:
    present = {str(row.get("tool", "")).strip().lower() for row in sanitized_stack if str(row.get("tool", "")).strip()}
    for row in observed_stack:
      name = str(row.get("tool", "")).strip()
      if not name:
        continue
      low = name.lower()
      if low in present:
        continue
      sanitized_stack.append(row)
      present.add(low)
      if len(sanitized_stack) >= 8:
        break

  key_to_name: dict[str, str] = {}
  for row in sanitized_stack:
    key = _normalize_tool_key(str(row.get("tool", "")))
    name = str(row.get("tool", "")).strip()
    if key and name and key not in key_to_name:
      key_to_name[key] = name

  sanitized_required: list[str] = []
  seen_required: set[str] = set()
  for tool in required_tools:
    raw = str(tool or "").strip()
    if not raw:
      continue
    key = _normalize_tool_key(raw)
    name = key_to_name.get(key, "")
    if not name:
      continue
    low = name.lower()
    if low in seen_required:
      continue
    seen_required.add(low)
    sanitized_required.append(name)

  if not sanitized_required:
    sanitized_required = [str(row.get("tool", "")).strip() for row in sanitized_stack if str(row.get("tool", "")).strip()]
  else:
    for row in sanitized_stack:
      name = str(row.get("tool", "")).strip()
      if not name:
        continue
      low = name.lower()
      if low in seen_required:
        continue
      seen_required.add(low)
      sanitized_required.append(name)

  return sanitized_stack[:8], sanitized_required[:8]


def _infer_technical_stack(workflow: dict[str, Any]) -> list[dict[str, str]]:
  observed_tools = _observed_tool_sequence(workflow)
  browser_domains = _browser_domains_from_workflow(workflow)

  stack: list[dict[str, str]] = []
  seen: set[str] = set()
  for raw_tool in observed_tools:
    entry = _stack_entry_from_observed_tool(raw_tool, browser_domains)
    name_key = str(entry.get("tool", "")).strip().lower()
    if not name_key or name_key in seen:
      continue
    seen.add(name_key)
    stack.append(entry)

  if not stack:
    stack.append(
      {
        "tool": "Filesystem",
        "mcp_server": "filesystem",
        "purpose": "Persist run outputs and append execution logs.",
      }
    )

  return stack[:6]


def _workflow_step_actions(workflow: dict[str, Any]) -> list[str]:
  actions = [
    str(step.get("action") or "").strip()
    for step in (workflow.get("steps") or [])
    if str(step.get("action") or "").strip()
  ]
  if actions:
    return actions[:8]

  details = str(workflow.get("details") or "").strip()
  if details:
    bits = [part.strip() for part in re.split(r"[.;]", details) if part.strip()]
    if bits:
      return bits[:6]

  return [
    "Capture a new task trigger",
    "Extract relevant fields from the source",
    "Normalize and classify the data",
    "Write the output into the destination system",
    "Post a completion summary with exceptions",
  ]


def _normalized_process_steps(raw_steps: list[str]) -> list[str]:
  cleaned: list[str] = []
  for item in raw_steps:
    text = str(item or "").strip()
    if not text:
      continue
    text = re.sub(r"^\s*\d+\s*[\).\-\:]\s*", "", text).strip()
    if text:
      cleaned.append(text)
  return cleaned


def _automation_watchouts(workflow: dict[str, Any], required_tools: list[str]) -> list[str]:
  tools = [str(tool).strip().lower() for tool in required_tools if str(tool).strip()]
  tool_blob = " ".join(tools)
  step_blob = " ".join(
    str(step.get("action") or "").strip().lower() for step in (workflow.get("steps") or []) if str(step.get("action") or "").strip()
  )

  items: list[str] = [
    "Duplicate events and retries can create duplicate outputs unless idempotency keys are enforced.",
    "Auth/session expiry or MCP permission issues can silently fail runs unless surfaced in alerts.",
  ]
  if any(token in tool_blob for token in ("gmail", "mail", "outlook", "slack", "teams")):
    items.append("Outbound communication steps need guardrails to prevent accidental or repeated sends.")
  if any(token in tool_blob for token in ("sheet", "sheets", "excel", "airtable", "salesforce", "hubspot")):
    items.append("Record updates should validate required fields and primary keys before write operations.")
  if "active" in step_blob:
    items.append("Window-focus signals are low fidelity; treat them as hints, not deterministic triggers.")

  deduped: list[str] = []
  seen: set[str] = set()
  for item in items:
    key = item.strip().lower()
    if key and key not in seen:
      seen.add(key)
      deduped.append(item.strip())
  return deduped[:4]


def _automation_avoid_items(required_tools: list[str]) -> list[str]:
  tools = [str(tool).strip().lower() for tool in required_tools if str(tool).strip()]
  items: list[str] = [
    "Avoid destructive writes (delete/overwrite) without an explicit confirmation checkpoint.",
    "Avoid running end-to-end actions on every noisy trigger; require qualifying conditions first.",
    "Avoid swallowing errors; always emit failure context and retry guidance.",
  ]
  if any(token in " ".join(tools) for token in ("gmail", "mail", "outlook", "slack", "teams")):
    items.append("Avoid auto-sending external or customer-facing messages without final human review.")
  return items[:4]


def _unique_prompt_rows(rows: list[str], fallback: str, limit: int = 12) -> list[str]:
  cleaned: list[str] = []
  seen: set[str] = set()
  for row in rows:
    text = " ".join(str(row or "").split()).strip()
    key = text.lower()
    if not text or key in seen:
      continue
    seen.add(key)
    cleaned.append(text)
    if len(cleaned) >= max(1, int(limit)):
      break
  if cleaned:
    return cleaned
  return [fallback]


def _markdown_bullets(rows: list[str], fallback: str, limit: int = 12) -> str:
  cleaned = _unique_prompt_rows(rows, fallback=fallback, limit=limit)
  return "\n".join(f"- {row}" for row in cleaned)


def _is_job_search_workflow(workflow: dict[str, Any], required_tools: list[str], intent_label: str) -> bool:
  tool_keys = _workflow_tool_keys(workflow)
  for tool in required_tools:
    key = _normalize_tool_key(tool)
    if key:
      tool_keys.add(key)
  sites = _browser_domains_from_workflow(workflow)
  if any("linkedin." in str(site).lower() for site in sites):
    return True
  if "linkedin" in tool_keys:
    return True
  text = f"{str(intent_label or '').lower()} {str(workflow.get('name') or '').lower()} {str(workflow.get('details') or '').lower()}"
  return any(token in text for token in ("job", "jobs", "application", "hiring", "recruiter", "career", "resume"))


def _prompt_required_tools(workflow: dict[str, Any], required_tools: list[str]) -> list[str]:
  sites = _browser_domains_from_workflow(workflow)
  rows: list[str] = []
  for raw in required_tools:
    key = _normalize_tool_key(raw)
    pretty = _friendly_tool_name(key or raw)
    if key == "browser" and sites:
      rows.append(f"{pretty} (observed sites: {', '.join(sites[:4])})")
    else:
      rows.append(pretty)
  if not rows and sites:
    rows.append(f"Web Browser (observed sites: {', '.join(sites[:4])})")
  return _unique_prompt_rows(rows, fallback="Observed workflow tools only (no external tools inferred).", limit=10)


def _prompt_core_objective_rows(job_flow: bool, discovery_surface: str) -> list[str]:
  if job_flow:
    return [
      f"find relevant jobs from {discovery_surface},",
      "add them to a tracker in a structured and deduplicated way,",
      "conduct deep research on each company,",
      "produce useful summaries that help me evaluate whether to apply.",
    ]
  return [
    f"find relevant qualifying work items from {discovery_surface},",
    "add them to a tracker in a structured and deduplicated way,",
    "conduct deep context research on each selected item or organization,",
    "produce useful summaries that help me decide what action to take next.",
  ]


def _prompt_success_rows(job_flow: bool, discovery_surface: str) -> list[str]:
  if job_flow:
    return [
      f"relevant {discovery_surface} jobs are consistently identified using clear qualification rules,",
      "jobs are added to a tracker with validated fields and no duplicate entries,",
      "each company is researched in depth using public web sources,",
      "outputs are logged clearly with completion status, confidence, and failure reasons,",
      "exceptions such as auth/session expiry, broken pages, missing fields, or research gaps are surfaced for review rather than silently ignored,",
      "the workflow is idempotent, auditable, and practical to run repeatedly.",
    ]
  return [
    "qualifying workflow items are identified using explicit relevance thresholds,",
    "records are written with validated fields and deduplication safeguards,",
    "supporting context research is generated from observed tools and public sources,",
    "outputs include completion status, confidence notes, and clear failure reasons,",
    "exceptions such as auth/session expiry, missing fields, and source inconsistencies are surfaced for review rather than silently ignored,",
    "the workflow is idempotent, auditable, and practical to run repeatedly.",
  ]


def _prompt_stage_sections(job_flow: bool, discovery_surface: str) -> list[tuple[str, list[str]]]:
  if job_flow:
    return [
      (
        "Stage 1: Job Discovery",
        [
          f"visit {discovery_surface} job search pages",
          "detect job posts that match predefined relevance criteria",
          "extract core job details",
          "identify whether the job is new or already tracked",
          "decide whether to save, skip, or flag for review",
        ],
      ),
      (
        "Stage 2: Structured Tracking",
        [
          "write the selected job into a tracker",
          "ensure deduplication through a strong idempotency key",
          "validate required fields before writing",
          "log status of write success or failure",
          "preserve prior data rather than destructively overwriting it",
        ],
      ),
      (
        "Stage 3: Deep Company Research",
        [
          "company overview",
          "core product or service",
          "business model",
          "stage and traction signals",
          "leadership and notable team members",
          "recent news and major developments",
          "funding history if available",
          "hiring signals",
          "market positioning and competitors",
          "risks or red flags",
          "why the role may or may not be attractive",
        ],
      ),
      (
        "Stage 4: Candidate Decision Support",
        [
          "Is this company worth my time?",
          "Is this role aligned with my goals?",
          "What is differentiated or risky about this opportunity?",
          "What should I investigate further before applying?",
        ],
      ),
    ]
  return [
    (
      "Stage 1: Signal Discovery",
      [
        f"visit {discovery_surface} and related observed workflow surfaces",
        "detect items that match predefined relevance criteria",
        "extract core details needed for downstream decisions",
        "identify whether the item is new or already tracked",
        "decide whether to save, skip, or flag for review",
      ],
    ),
    (
      "Stage 2: Structured Tracking",
      [
        "write selected items into a tracker",
        "ensure deduplication through a strong idempotency key",
        "validate required fields before writing",
        "log status of write success or failure",
        "preserve prior data rather than destructively overwriting it",
      ],
    ),
    (
      "Stage 3: Context Research",
      [
        "subject/company overview",
        "core product, process, or initiative context",
        "business or operational significance",
        "stage and traction signals where relevant",
        "recent updates and noteworthy developments",
        "competitive or comparative positioning",
        "risks or red flags",
        "why the opportunity may or may not be attractive",
      ],
    ),
    (
      "Stage 4: Decision Support",
      [
        "Is this worth deeper follow-up?",
        "Is this aligned with my goals and priorities?",
        "What is differentiated or risky here?",
        "What should I investigate further before acting?",
      ],
    ),
  ]


def _build_llm_prompt_payload(
  *,
  workflow: dict[str, Any],
  window_days: int,
  title: str,
  goal: str,
  process_steps: list[str],
  required_tools: list[str],
) -> str:
  intent = _infer_workflow_intent(workflow)
  intent_label = str(intent.get("label") or "reliable workflow execution and decision support")
  job_flow = _is_job_search_workflow(workflow, required_tools, intent_label)
  discovery_surface = "LinkedIn" if job_flow else "the observed workflow tools"

  role = (
    "You are an Automation Systems Architect focused on reliable workflow agents, "
    "job-search automation, structured data capture, and company intelligence research."
    if job_flow
    else "You are an Automation Systems Architect focused on reliable workflow agents, "
    "intent-aware workflow automation, structured data capture, and company intelligence research."
  )

  objective_rows = _prompt_core_objective_rows(job_flow, discovery_surface)
  success_rows = _prompt_success_rows(job_flow, discovery_surface)
  stage_sections = _prompt_stage_sections(job_flow, discovery_surface)
  watchouts = _automation_watchouts(workflow, required_tools)
  avoid_items = _automation_avoid_items(required_tools)
  process_lines = _markdown_bullets(process_steps[:12], fallback="No process steps provided.", limit=12)
  tool_lines = _markdown_bullets(_prompt_required_tools(workflow, required_tools), fallback="No explicit tools provided.", limit=12)
  watch_lines = _markdown_bullets(watchouts, fallback="No specific risks detected.", limit=6)
  avoid_lines = _markdown_bullets(avoid_items, fallback="No avoid-list provided.", limit=6)
  objective_lines = _markdown_bullets(objective_rows, fallback="design a reliable automation around this workflow.", limit=6)
  success_lines = _markdown_bullets(success_rows, fallback="the workflow runs reliably with validated outputs and visible failure handling.", limit=8)

  constraint_rows = [
    "Only add or process items that pass relevance thresholds.",
    "Avoid duplicate entries caused by retries, repeated visits, or duplicate listing surfaces.",
    "Avoid destructive writes, deletions, or overwrites without an explicit confirmation checkpoint.",
    "Avoid running full deep research on every noisy trigger; require qualification first.",
    "Avoid silent failures; always emit failure context, likely cause, and retry guidance.",
    "Surface auth/session issues explicitly.",
    "Preserve logs for auditability.",
    "Prefer modular architecture so discovery, tracking, and research can run independently if needed.",
  ]
  constraint_lines = _markdown_bullets(constraint_rows, fallback="Apply explicit guardrails for reliability and auditability.", limit=12)

  stage_blocks: list[str] = []
  for stage_title, rows in stage_sections:
    stage_blocks.append(f"### {stage_title}\n{_markdown_bullets(rows, fallback='No stage details provided.', limit=14)}")
  stage_text = "\n\n".join(stage_blocks)

  return (
    "## Role to Assume\n"
    f"{role}\n\n"
    "## Core Objective\n"
    "Design an automation system that helps me:\n"
    f"{objective_lines}\n\n"
    "The system should reduce manual browsing, copying, and context switching while maintaining high reliability and clear human oversight.\n"
    f"Operational target: {goal}\n\n"
    "## Success Criteria\n"
    "Success means:\n"
    f"{success_lines}\n\n"
    "## Instructions for How to Think\n"
    "Reason carefully and systematically before answering, but do not reveal hidden internal reasoning.\n"
    "Instead, provide a structured and transparent analysis that shows:\n"
    "- assumptions,\n"
    "- workflow diagnosis,\n"
    "- system design,\n"
    "- agent responsibilities,\n"
    "- qualifying logic,\n"
    "- data schema,\n"
    "- error handling,\n"
    "- prioritization,\n"
    "- risks and tradeoffs.\n\n"
    "Be practical, not theoretical.\n"
    "Be critical about where full automation is appropriate versus where human review should remain.\n"
    "Do not assume every item should be captured or every company/topic should be researched equally deeply.\n"
    "Design for signal over noise.\n\n"
    "## Workflow to Design\n"
    f"The target workflow should support this inferred intent: {intent_label}.\n\n"
    f"{stage_text}\n\n"
    "## Existing Process Map\n"
    f"{process_lines}\n\n"
    "## Tools Required\n"
    f"{tool_lines}\n\n"
    "## Key Design Constraints\n"
    f"{constraint_lines}\n\n"
    "## What to Look Out For\n"
    f"{watch_lines}\n\n"
    "## What to Avoid\n"
    f"{avoid_lines}\n\n"
    "## Context\n"
    f"- Workflow Title: {title}\n"
    f"- Window: last {int(max(1, window_days))} days\n\n"
    "## What I Want You to Produce\n"
    "Please structure your response exactly as follows:\n\n"
    "### 1. Context Summary\n"
    "Summarize the workflow and operating objective.\n\n"
    "### 2. Assumptions\n"
    "List the assumptions you are making about the process, tracker, and decision goals.\n\n"
    "### 3. Workflow Diagnosis\n"
    "Explain where the current friction likely exists between discovery, data capture, research, and decision-making.\n\n"
    "### 4. Recommended Automation Design\n"
    "Design the automation end-to-end.\n"
    "Include:\n"
    "- triggers,\n"
    "- qualifying conditions,\n"
    "- extraction logic,\n"
    "- deduplication logic,\n"
    "- tracker write logic,\n"
    "- research workflow,\n"
    "- review checkpoints,\n"
    "- completion logging.\n\n"
    "### 5. Recommended Agents\n"
    "Define the agents that should exist in the system.\n"
    "For each agent, include:\n"
    "- name,\n"
    "- mission,\n"
    "- trigger,\n"
    "- inputs,\n"
    "- outputs,\n"
    "- boundaries,\n"
    "- escalation rules,\n"
    "- human-in-the-loop requirements,\n"
    "- key failure modes.\n\n"
    "### 6. Qualification Framework\n"
    "Define how the system should decide whether an item is relevant enough to save.\n"
    "Include:\n"
    "- hard filters,\n"
    "- soft scoring criteria,\n"
    "- reasons to skip,\n"
    "- reasons to flag for review.\n\n"
    "### 7. Tracker Schema\n"
    "Propose the ideal tracker structure and fields.\n"
    "Include:\n"
    "- item-level fields,\n"
    "- organization/company-level fields,\n"
    "- research-level fields,\n"
    "- workflow status fields,\n"
    "- timestamps,\n"
    "- idempotency key design.\n\n"
    "### 8. Research Framework\n"
    "Design the deep research output template.\n"
    "It should capture:\n"
    "- summary,\n"
    "- product/service context,\n"
    "- business model,\n"
    "- market,\n"
    "- team,\n"
    "- traction,\n"
    "- funding when available,\n"
    "- news,\n"
    "- competitors,\n"
    "- risks,\n"
    "- decision thesis,\n"
    "- open questions.\n\n"
    "### 9. Prioritization Logic\n"
    "Explain when the system should:\n"
    "- only save an item,\n"
    "- save plus light research,\n"
    "- save plus deep research,\n"
    "- escalate to me for manual review.\n\n"
    "### 10. Reliability and Error Handling\n"
    "Describe:\n"
    "- retry strategy,\n"
    "- duplicate prevention,\n"
    "- logging,\n"
    "- failure alerts,\n"
    "- fallback behavior,\n"
    "- safe handling of partial completion.\n\n"
    "### 11. What Should Stay Human-Led\n"
    "Identify which parts of the process should remain human-owned and why.\n\n"
    "### 12. Implementation Roadmap\n"
    "Break this into phases:\n"
    "- Phase 1: basic capture and tracking,\n"
    "- Phase 2: qualification and deduplication,\n"
    "- Phase 3: research agent,\n"
    "- Phase 4: decision-support layer.\n\n"
    "### 13. Final Recommendation\n"
    "End with:\n"
    "- the best minimal viable automation,\n"
    "- the best longer-term agent system,\n"
    "- the biggest risk to avoid,\n"
    "- the most important design principle.\n\n"
    "## Quality Bar\n"
    "The answer should be detailed, operational, and implementation-aware.\n"
    "Do not give generic suggestions like 'build an agent'.\n"
    "Specify exactly how the workflow should work, what each component does, and where human judgment should remain.\n"
    "Optimize for usefulness, reliability, and decision quality."
  )


def _heuristic_automation_blueprint(workflow: dict[str, Any], window_days: int) -> dict[str, Any]:
  name = str(workflow.get("name") or "Workflow")
  stack = _infer_technical_stack(workflow)
  actions = _workflow_step_actions(workflow)
  process_map = [f"{idx + 1}. {action}" for idx, action in enumerate(actions)]

  reclaimed_hours = round((_estimate_weekly_minutes(workflow) * 0.65) / 60.0, 2)
  friendly_tools = [entry["tool"] for entry in stack]
  source_tool = friendly_tools[0] if friendly_tools else "Source App"
  target_tool = friendly_tools[1] if len(friendly_tools) > 1 else source_tool
  verification_target = target_tool or source_tool

  instructions = [
    f"Monitor: Watch for a new trigger event in {source_tool} matching this workflow pattern.",
    "Extract: Pull sender, subject/context, priority, due-date, and key payload fields via MCP.",
    f"Action: Standardize the payload and append/update records in {target_tool}.",
    f"Verification: Write a run summary and exceptions to {verification_target} logs for review.",
  ]
  required_tools = [entry["tool"] for entry in stack]
  goal = (
    f"Reclaim {reclaimed_hours:.2f} hours/week by automating the transition between "
    f"{source_tool} and {target_tool}."
  )
  title = f"{name} Automation"
  llm_prompt = _build_llm_prompt_payload(
    workflow=workflow,
    window_days=window_days,
    title=title,
    goal=goal,
    process_steps=_normalized_process_steps(process_map),
    required_tools=required_tools,
  )

  return {
    "title": title,
    "goal": goal,
    "process_map": process_map,
    "technical_stack": stack,
    "instructions": instructions,
    "required_tools": required_tools,
    "llm_prompt": llm_prompt,
  }


def _llm_automation_blueprint_from_ollama(workflow: dict[str, Any], window_days: int) -> dict[str, Any] | None:
  compact = {
    "name": workflow.get("name"),
    "category": workflow.get("category"),
    "details": workflow.get("details"),
    "tools": workflow.get("tools"),
    "steps": [step.get("action") for step in (workflow.get("steps") or [])],
    "frequency": workflow.get("frequency"),
    "automation_idea": ((workflow.get("automation_ideas") or [{}])[0] or {}).get("proposal"),
    "observed_stack": [row.get("tool") for row in _infer_technical_stack(workflow)],
  }

  prompt = (
    "You are an automation architect writing a workflow automation package for Claude Cowork. "
    "Return JSON only. Be concrete and operational. "
    "The output must follow this exact shape:\n"
    '{"title":"...","goal":"...","process_map":["1. ...","2. ..."],'
    '"technical_stack":[{"tool":"...","mcp_server":"...","purpose":"..."}],'
    '"instructions":["...","...","...","..."],'
    '"required_tools":["..."],"llm_prompt":"..."}\n'
    "Rules: process_map must be 4-8 steps, instructions must be exactly 4 lines "
    "(Monitor, Extract, Action, Verification), and required_tools must align with technical_stack. "
    "Only use tools present in workflow evidence (tools/steps/observed_stack); do not invent new tools.\n"
    f"Window days: {window_days}\nWorkflow:\n{json.dumps(compact, ensure_ascii=True)}"
  )
  generated = _ollama_generate(
    prompt=prompt,
    timeout_seconds=8,
    format_json=True,
    env_keys=("WORKFLOW_AUTOMATION_MODEL", "WORKFLOW_EXPLAIN_MODEL", "WORKFLOW_LLM_MODEL"),
  )
  if not generated:
    return None
  raw_text, _used_model = generated

  parsed_payload: dict[str, Any] | None = None
  try:
    parsed_payload = json.loads(raw_text)
  except json.JSONDecodeError:
    block = _extract_json_block(raw_text)
    if block:
      try:
        parsed_payload = json.loads(block)
      except json.JSONDecodeError:
        parsed_payload = None

  if not isinstance(parsed_payload, dict):
    return None

  title = str(parsed_payload.get("title", "")).strip()
  goal = str(parsed_payload.get("goal", "")).strip()
  llm_prompt = str(parsed_payload.get("llm_prompt", "")).strip()

  process_map_raw = parsed_payload.get("process_map")
  process_map = [
    str(item).strip()
    for item in (process_map_raw if isinstance(process_map_raw, list) else [])
    if str(item).strip()
  ]
  instructions_raw = parsed_payload.get("instructions")
  instructions = [
    str(item).strip()
    for item in (instructions_raw if isinstance(instructions_raw, list) else [])
    if str(item).strip()
  ]
  required_raw = parsed_payload.get("required_tools")
  required_tools = [
    str(item).strip()
    for item in (required_raw if isinstance(required_raw, list) else [])
    if str(item).strip()
  ]

  stack_raw = parsed_payload.get("technical_stack")
  technical_stack: list[dict[str, str]] = []
  if isinstance(stack_raw, list):
    for row in stack_raw:
      if not isinstance(row, dict):
        continue
      tool = str(row.get("tool", "")).strip()
      mcp_server = str(row.get("mcp_server", "")).strip()
      purpose = str(row.get("purpose", "")).strip()
      if not tool:
        continue
      technical_stack.append(
        {
          "tool": tool,
          "mcp_server": mcp_server or "custom",
          "purpose": purpose or "Support this workflow automation step.",
        }
      )

  if not title or not goal or len(process_map) < 3 or len(instructions) < 4:
    return None

  if not technical_stack:
    technical_stack = _infer_technical_stack(workflow)
  if not required_tools:
    required_tools = [entry["tool"] for entry in technical_stack]
  if not llm_prompt:
    llm_prompt = (
      f"Title: {title}\n"
      f"Goal: {goal}\n"
      "Instructions for Claude Cowork:\n"
      + "\n".join(f"{idx + 1}. {line}" for idx, line in enumerate(instructions[:4]))
      + f"\nRequired Tools: {', '.join(required_tools)}"
    )

  return _coerce_automation_blueprint(
    {
      "title": title,
      "goal": goal,
      "process_map": process_map[:8],
      "technical_stack": technical_stack[:6],
      "instructions": instructions[:4],
      "required_tools": required_tools[:8],
      "llm_prompt": llm_prompt,
    },
    workflow,
    window_days,
  )


def _heuristic_workflow_explanation(workflow: dict[str, Any], window_days: int) -> str:
  summary, _ = _pattern_based_workflow_explanation(workflow, window_days)
  return summary


def _step_parts(action: str) -> tuple[str, str]:
  text = str(action or "").strip().lower()
  if not text:
    return "", ""
  head, _, tail = text.partition(" ")
  return head.strip(), tail.strip()


def _classify_step_pattern(action: str) -> dict[str, str]:
  raw = str(action or "").strip()
  lower = raw.lower()
  tool, tail = _step_parts(raw)

  def row(kind: str, label: str, confidence: str) -> dict[str, str]:
    return {"kind": kind, "label": label, "confidence": confidence, "raw": raw}

  intent_match = re.search(r"\bintent\s+([a-z0-9_]+)\b", lower)
  action_match = re.search(r"\baction\s+([a-z0-9_]+)\b", lower)
  stage_match = re.search(r"\bstage\s+([a-z0-9_]+)\b", lower)
  if intent_match:
    intent_label = intent_match.group(1).replace("_", " ")
    detail_parts: list[str] = []
    if action_match:
      detail_parts.append(action_match.group(1).replace("_", " "))
    if stage_match:
      detail_parts.append(stage_match.group(1).replace("_", " "))
    detail_suffix = f" ({', '.join(detail_parts)})" if detail_parts else ""
    confidence = "high" if action_match else "medium"
    return row("intent_signal", f"Intent signal: {intent_label}{detail_suffix}", confidence)

  if lower.startswith("browser visit "):
    domain = raw.split("browser visit ", 1)[1].strip() if "browser visit " in lower else ""
    suffix = f" ({domain})" if domain else ""
    return row("browser_visit", f"Browser domain visit{suffix}", "medium")
  if tool in {"pkill", "kill", "killall"}:
    return row("process_stop", "Process stop/reset commands", "high")
  if tool == "sleep":
    return row("wait_poll", "Wait/poll intervals", "high")
  if tool in {"curl", "wget"}:
    return row("endpoint_check", "Endpoint/API checks", "high")
  if tool in {"python", "python3", "node"}:
    return row("service_run", "Script or service execution", "high")
  if tool in {"npm", "pnpm", "yarn", "bun"}:
    verb = tail.split(" ", 1)[0].strip() if tail else "run"
    if verb in {"test", "lint", "check"}:
      return row("test_run", "Test/quality command runs", "high")
    if verb in {"build", "dev", "start", "run"}:
      return row("build_run", "Build/dev command runs", "high")
    return row("service_run", "Package manager task execution", "medium")
  if tool == "git":
    return row("repo_sync", "Git repository operations", "high")
  if tool in {"rg", "grep", "fd", "find"}:
    return row("code_search", "Search/query commands", "high")
  if tool in {"cat", "less", "head", "tail", "sed", "awk"}:
    return row("file_inspect", "File/content inspection commands", "high")
  if lower.endswith(" active"):
    if tool in {"mail", "gmail", "outlook", "slack", "teams", "google_docs", "google_sheets", "google_slides", "powerpoint"}:
      return row("comm_workspace", "Communication workspace focus", "low")
    if tool in {"notion", "sheet", "excel", "airtable", "granola"}:
      return row("tracking_workspace", "Tracker/document workspace focus", "low")
    return row("focus_switch", "App focus switches (low semantic detail)", "low")
  return row("generic_command", "General command execution", "medium")


def _pattern_confidence(patterns: list[dict[str, Any]]) -> str:
  if not patterns:
    return "low"
  weight = {"low": 1.0, "medium": 2.0, "high": 3.0}
  score_sum = 0.0
  count_sum = 0.0
  for row in patterns:
    conf = str(row.get("confidence") or "low").lower()
    count = max(1, int(row.get("count") or 1))
    score_sum += weight.get(conf, 1.0) * float(count)
    count_sum += float(count)
  avg = score_sum / max(1.0, count_sum)
  if avg >= 2.4:
    return "high"
  if avg >= 1.8:
    return "medium"
  return "low"


def _tool_use_case_hint(tool: str) -> str:
  key = str(tool or "").strip().lower()
  hints = {
    "salesforce": "updating customer/contact records and pipeline tracking",
    "hubspot": "CRM updates and lead progression tracking",
    "slack": "team coordination and follow-up communication",
    "gmail": "email triage and outbound follow-up",
    "mail": "email triage and outbound follow-up",
    "outlook": "email triage and outbound follow-up",
    "notion": "documentation, planning, and task tracking",
    "sheet": "structured tracker updates and reporting",
    "sheets": "structured tracker updates and reporting",
    "google_docs": "document drafting, synthesis, and collaboration",
    "google_sheets": "structured tracker updates and reporting",
    "google_slides": "building presentation narratives and slide decks",
    "powerpoint": "building presentation narratives and slide decks",
    "granola": "capturing meeting notes and extracting follow-ups",
    "excel": "structured tracker updates and reporting",
    "airtable": "structured tracker updates and reporting",
    "browser": "research, discovery, and external context gathering",
    "gemini": "research, synthesis, and iterative drafting",
    "linkedin": "outreach, hiring, and relationship discovery",
    "codex": "building or iterating on product/code workflows",
    "code": "building or iterating on product/code workflows",
    "git": "code changes, review loops, and delivery flow",
    "python": "automation scripts and backend workflow execution",
    "python3": "automation scripts and backend workflow execution",
    "terminal": "command-driven setup, checks, and operations",
    "zoom": "meetings and stakeholder syncs",
    "teams": "meetings and stakeholder syncs",
  }
  return hints.get(key, "")


def _tool_use_case_line(tools: list[str]) -> str:
  phrases: list[str] = []
  for tool in tools:
    hint = _tool_use_case_hint(tool)
    if hint and hint not in phrases:
      phrases.append(hint)
    if len(phrases) >= 3:
      break
  if not phrases:
    return "routine task execution and cross-tool handoffs"
  if len(phrases) == 1:
    return phrases[0]
  if len(phrases) == 2:
    return f"{phrases[0]} and {phrases[1]}"
  return f"{phrases[0]}, {phrases[1]}, and {phrases[2]}"


def _summary_primary_tools(tools: list[str], limit: int = 2) -> list[str]:
  ordered: list[str] = []
  seen: set[str] = set()
  for item in tools:
    key = str(item).strip().lower()
    if key and key not in seen:
      seen.add(key)
      ordered.append(key)

  if "browser" in seen and any(key != "browser" for key in ordered):
    ordered = [key for key in ordered if key != "browser"] + ["browser"]

  specific_priority = (
    "google_docs",
    "google_sheets",
    "google_slides",
    "powerpoint",
    "granola",
    "gmail",
    "linkedin",
    "salesforce",
    "hubspot",
    "gemini",
  )
  for candidate in specific_priority:
    if "codex" in seen and candidate in seen:
      prioritized = ["codex", candidate]
      for key in ordered:
        if key not in prioritized:
          prioritized.append(key)
      return prioritized[: max(1, int(limit))]

  if "codex" in seen and "browser" in seen:
    prioritized = ["codex", "browser"]
    for key in ordered:
      if key not in prioritized:
        prioritized.append(key)
    return prioritized[: max(1, int(limit))]
  return ordered[: max(1, int(limit))]


def _likely_activity_from_patterns(patterns: list[dict[str, Any]]) -> str:
  kinds = {str(row.get("kind") or "") for row in patterns}
  if "intent_signal" in kinds:
    return "intent-tagged task sequence with explicit activity labels"
  if {"process_stop", "service_run", "endpoint_check"} <= kinds:
    return "local service restart and endpoint validation loop"
  if {"repo_sync", "test_run"} <= kinds or {"repo_sync", "build_run"} <= kinds:
    return "code iteration loop with repository updates and verification"
  if {"comm_workspace", "tracking_workspace"} <= kinds:
    return "communication-to-tracker handoff loop"
  if {"browser_visit", "code_search"} <= kinds or {"browser_visit", "file_inspect"} <= kinds:
    return "research and evidence collection loop"
  if kinds == {"focus_switch"}:
    return "app focus switching only; insufficient detail for deeper activity inference"

  labels = [str(row.get("label") or "").strip() for row in patterns if str(row.get("label") or "").strip()]
  if not labels:
    return "repeated command execution pattern"
  return " + ".join(labels[:2]).lower()


def _workflow_pattern_rows(workflow: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
  raw_steps = [
    str(step.get("action") or "").strip()
    for step in (workflow.get("steps") or [])
    if str(step.get("action") or "").strip()
  ]
  if not raw_steps:
    return [], []

  ordered_kinds: list[str] = []
  by_kind: dict[str, dict[str, Any]] = {}
  for action in raw_steps:
    parsed = _classify_step_pattern(action)
    kind = str(parsed["kind"])
    if kind not in by_kind:
      ordered_kinds.append(kind)
      by_kind[kind] = {
        "kind": kind,
        "label": parsed["label"],
        "confidence": parsed["confidence"],
        "count": 0,
        "examples": [],
      }
    by_kind[kind]["count"] += 1
    if len(by_kind[kind]["examples"]) < 3:
      by_kind[kind]["examples"].append(parsed["raw"])

  rows = [by_kind[kind] for kind in ordered_kinds]
  return rows, raw_steps


def _pattern_based_workflow_explanation(workflow: dict[str, Any], window_days: int) -> tuple[str, list[dict[str, Any]]]:
  tools = [str(tool).strip() for tool in (workflow.get("tools") or []) if str(tool).strip()]
  primary_tools = _summary_primary_tools(tools, limit=2)
  patterns, _ = _workflow_pattern_rows(workflow)
  tool_line = ", ".join(_friendly_tool_name(tool) for tool in primary_tools) if primary_tools else "your observed tools"
  use_case_line = _tool_use_case_line(primary_tools or tools)
  intent = _infer_workflow_intent(workflow)
  label = str(intent.get("label") or "general context building and execution support")
  alternatives = [str(item).strip() for item in (intent.get("alternatives") or []) if str(item).strip()]
  secondary = f" with a secondary possibility of {alternatives[0]}" if alternatives else ""
  summary = (
    f"You primarily used {tool_line}; these tools are commonly associated with {use_case_line}, "
    f"suggesting intent around {label}{secondary}."
  )
  return summary, patterns


def _workflow_intent_signal_rows(workflow: dict[str, Any]) -> list[str]:
  rows: list[str] = []
  seen: set[str] = set()
  for step in workflow.get("steps") or []:
    action = str(step.get("action") or "").strip().lower()
    if not action:
      continue
    intent = ""
    event = ""
    stage = ""
    intent_match = re.search(r"\bintent\s+([a-z0-9_]+)\b", action)
    event_match = re.search(r"\baction\s+([a-z0-9_]+)\b", action)
    stage_match = re.search(r"\bstage\s+([a-z0-9_]+)\b", action)
    if intent_match:
      intent = intent_match.group(1).replace("_", " ")
    if event_match:
      event = event_match.group(1).replace("_", " ")
    if stage_match:
      stage = stage_match.group(1).replace("_", " ")
    if not intent and not event and not stage:
      continue

    parts = []
    if intent:
      parts.append(f"intent {intent}")
    if event:
      parts.append(f"action {event}")
    if stage:
      parts.append(f"stage {stage}")
    label = ", ".join(parts).strip()
    if label and label not in seen:
      seen.add(label)
      rows.append(label)
  return rows[:8]


def _workflow_evidence_rows(workflow: dict[str, Any], window_days: int, patterns: list[dict[str, Any]]) -> list[str]:
  evidence: list[str] = []
  freq = workflow.get("frequency") or {}
  runs_total = int(freq.get("runs_total", 0) or 0)
  sessions = int(freq.get("sessions", 0) or 0)
  per_week = float(freq.get("per_week", 0.0) or 0.0)
  evidence.append(
    f"{runs_total} runs across {sessions} sessions in last {int(max(1, window_days))} days (~{per_week:.2f} runs/week)."
  )

  tools = [str(tool).strip() for tool in (workflow.get("tools") or []) if str(tool).strip()]
  tool_labels = [_friendly_tool_name(tool) for tool in _summary_primary_tools(tools, limit=3)]
  if tool_labels:
    evidence.append(f"Observed tools: {', '.join(tool_labels)}.")

  domains = _browser_domains_from_workflow(workflow)
  if domains:
    evidence.append(f"Observed sites: {', '.join(domains[:3])}.")

  intent_rows = _workflow_intent_signal_rows(workflow)
  if intent_rows:
    evidence.append(f"Intent signals: {intent_rows[0]}.")
  elif patterns:
    first_pattern = str((patterns[0] or {}).get("label") or "").strip()
    if first_pattern:
      evidence.append(f"Primary repeated pattern: {first_pattern}.")
  return evidence[:4]


def _split_sentences(text: str) -> list[str]:
  cleaned = " ".join(str(text or "").split()).strip()
  if not cleaned:
    return []
  rows = [row.strip() for row in re.split(r"(?<=[.!?])\s+", cleaned) if row.strip()]
  return rows


def _normalize_confidence_label(value: Any, fallback: str = "low") -> str:
  raw = str(value or "").strip().lower()
  if raw in {"low", "medium", "high"}:
    return raw
  return str(fallback or "low").strip().lower() or "low"


def _llm_mentions_unseen_tools(summary: str, workflow: dict[str, Any]) -> bool:
  text = str(summary or "").strip().lower()
  if not text:
    return True

  allowed_tool_keys = _workflow_tool_keys(workflow)
  for site in _browser_domains_from_workflow(workflow):
    mapped = _normalize_tool_key(_tool_from_browser_context(site))
    if mapped:
      allowed_tool_keys.add(mapped)

  for phrase, tool_key in LLM_TOOL_MENTION_GUARD.items():
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    if not re.search(pattern, text):
      continue
    normalized = _normalize_tool_key(tool_key)
    if normalized and normalized not in allowed_tool_keys:
      return True
  return False


def _llm_mentions_unseen_domains(summary: str, workflow: dict[str, Any]) -> bool:
  text = str(summary or "").strip().lower()
  mentioned = [_canonical_site_host(match) for match in DOMAIN_IN_TEXT_RE.findall(text)]
  mentioned = [row for row in mentioned if row]
  if not mentioned:
    return False

  allowed = {_canonical_site_host(row) for row in _browser_domains_from_workflow(workflow) if _canonical_site_host(row)}
  if not allowed:
    return True
  for domain in mentioned:
    if domain not in allowed:
      return True
  return False


def _llm_decipher_workflow_explanation_from_ollama(
  workflow: dict[str, Any],
  window_days: int,
  patterns: list[dict[str, Any]],
) -> dict[str, Any] | None:
  if os.environ.get("WORKFLOW_DISABLE_EXPLAIN_LLM", "0") == "1":
    return None

  fallback_confidence = _pattern_confidence(patterns)
  evidence_rows = _workflow_evidence_rows(workflow, window_days=window_days, patterns=patterns)
  compact = {
    "name": workflow.get("name"),
    "window_days": int(max(1, window_days)),
    "frequency": workflow.get("frequency") or {},
    "tools": [str(tool) for tool in (workflow.get("tools") or []) if str(tool).strip()],
    "sites": _browser_domains_from_workflow(workflow),
    "intent_signals": _workflow_intent_signal_rows(workflow),
    "actions": [str(step.get("action") or "") for step in (workflow.get("steps") or []) if str(step.get("action") or "").strip()][:10],
    "evidence_rows": evidence_rows,
  }
  prompt = (
    "You are a strict workflow analyst. Infer likely user intent from observed evidence only.\n"
    "Return JSON only with this exact shape:\n"
    '{"summary":"...","confidence":"low|medium|high","evidence":["...","..."]}\n'
    "Rules:\n"
    "- `summary` must be exactly 3 sentences.\n"
    "- Mention only tools/sites/intents that appear in the provided evidence JSON.\n"
    "- Do not invent apps, sites, actions, or outcomes.\n"
    "- If evidence is weak, sentence 3 must explicitly note limited evidence.\n"
    "- `evidence` must have 2-4 short lines grounded in provided data.\n"
    "- No markdown.\n"
    f"Evidence JSON:\n{json.dumps(compact, ensure_ascii=True)}"
  )
  generated = _ollama_generate(
    prompt=prompt,
    timeout_seconds=10,
    format_json=True,
    env_keys=("WORKFLOW_EXPLAIN_MODEL", "WORKFLOW_LLM_MODEL"),
  )
  if not generated:
    return None
  raw_text, used_model = generated

  parsed_payload: dict[str, Any] | None = None
  try:
    parsed_payload = json.loads(raw_text)
  except json.JSONDecodeError:
    block = _extract_json_block(raw_text)
    if block:
      try:
        parsed_payload = json.loads(block)
      except json.JSONDecodeError:
        parsed_payload = None
  if not isinstance(parsed_payload, dict):
    return None

  summary_raw = str(parsed_payload.get("summary") or "").strip()
  if not summary_raw:
    return None
  sentences = _split_sentences(summary_raw)
  if len(sentences) >= 3:
    summary = " ".join(sentences[:3])
  elif len(sentences) == 2:
    summary = f"{sentences[0]} {sentences[1]} Evidence remains limited, so this is a low-confidence draft."
  else:
    return None
  summary = " ".join(summary.split()).strip()
  if len(summary) < 40:
    return None
  if len(summary) > 420:
    summary = summary[:420].rsplit(" ", 1)[0].strip() + "."
  if _llm_mentions_unseen_tools(summary, workflow):
    return None
  if _llm_mentions_unseen_domains(summary, workflow):
    return None

  confidence = _normalize_confidence_label(parsed_payload.get("confidence"), fallback=fallback_confidence)
  evidence_raw = parsed_payload.get("evidence")
  evidence: list[str] = []
  if isinstance(evidence_raw, list):
    for row in evidence_raw:
      text = " ".join(str(row or "").split()).strip()
      if text:
        evidence.append(text)
  if not evidence:
    evidence = evidence_rows[:]
  if len(evidence) < 2:
    evidence.extend(evidence_rows)
  evidence = evidence[:4]

  return {
    "summary": summary,
    "confidence": confidence,
    "evidence": evidence,
    "model": used_model,
  }


def _llm_workflow_explanation_from_ollama(workflow: dict[str, Any], window_days: int) -> str | None:
  _, patterns = _pattern_based_workflow_explanation(workflow, window_days)
  deciphered = _llm_decipher_workflow_explanation_from_ollama(workflow, window_days, patterns)
  if not deciphered:
    return None
  return str(deciphered.get("summary") or "").strip() or None
  compact = {
    "name": workflow.get("name"),
    "category": workflow.get("category"),
    "details": workflow.get("details"),
    "tools": workflow.get("tools"),
    "steps": [step.get("action") for step in (workflow.get("steps") or [])],
    "frequency": workflow.get("frequency"),
  }
  prompt = (
    "You are writing an intent-first workflow recap for a productivity dashboard. "
    "Write 4-6 sentences in plain English. "
    "Sentence 1 must start with 'Likely intent:' and infer why the user did this workflow "
    "(for example: job search, portfolio founder outreach, customer research, or internal ops). "
    "Then explain the evidence behind that intent using tools, repeated actions, and sequence. "
    "Include rough scope and likely outcome. If intent is ambiguous, include one secondary intent. "
    "Avoid bullet points and avoid mentioning AI.\n"
    f"Window days: {window_days}\n"
    f"Workflow:\n{json.dumps(compact, ensure_ascii=True)}"
  )
  generated = _ollama_generate(
    prompt=prompt,
    timeout_seconds=6,
    format_json=False,
    env_keys=("WORKFLOW_EXPLAIN_MODEL", "WORKFLOW_LLM_MODEL"),
  )
  if not generated:
    return None
  text, _used_model = generated
  cleaned = " ".join(text.split())
  if len(cleaned) < 30:
    return None
  return cleaned


def design_workflow_automation(workflow_id: str, window_days: int = 14, max_workflows: int = 12) -> dict[str, Any]:
  wid = str(workflow_id or "").strip()
  if not wid:
    return {"ok": False, "error": "workflow_id_required"}

  insights = build_workflow_insights(window_days=window_days, max_workflows=max_workflows)
  workflows = insights.get("workflows") or []
  workflow = next((row for row in workflows if str(row.get("id")) == wid), None)
  if not workflow:
    return {"ok": False, "error": "workflow_not_found", "workflow_id": wid}

  draft = _llm_automation_blueprint_from_ollama(workflow, window_days=window_days)
  source = "llm"
  if not draft:
    source = "heuristic"
    draft = _heuristic_automation_blueprint(workflow, window_days=window_days)

  reclaimed_hours = round((_estimate_weekly_minutes(workflow) * 0.65) / 60.0, 2)
  title = str(draft.get("title") or f"{workflow.get('name', 'Workflow')} Automation")
  process_steps = _normalized_process_steps([str(item) for item in (draft.get("process_map") or [])])
  if not process_steps:
    process_steps = _normalized_process_steps(_workflow_step_actions(workflow))
  stack_rows = [
    {
      "tool": str(row.get("tool", "")).strip(),
      "mcp_server": str(row.get("mcp_server", "")).strip(),
      "purpose": str(row.get("purpose", "")).strip(),
    }
    for row in (draft.get("technical_stack") or [])
    if isinstance(row, dict) and str(row.get("tool", "")).strip()
  ]
  if not stack_rows:
    stack_rows = _infer_technical_stack(workflow)
  required_tools = [str(item).strip() for item in (draft.get("required_tools") or []) if str(item).strip()]
  if not required_tools:
    required_tools = [str(row.get("tool", "")).strip() for row in stack_rows if str(row.get("tool", "")).strip()]
  stack_rows, required_tools = _align_stack_and_required_tools_to_workflow(workflow, stack_rows, required_tools)
  stack_tools = [str(row.get("tool", "")).strip() for row in stack_rows if str(row.get("tool", "")).strip()]
  source_tool = stack_tools[0] if stack_tools else "Source App"
  target_tool = stack_tools[1] if len(stack_tools) > 1 else source_tool
  goal = (
    f"Reclaim {reclaimed_hours:.2f} hours/week by automating the transition between "
    f"{source_tool} and {target_tool}."
  )
  llm_prompt = _build_llm_prompt_payload(
    workflow=workflow,
    window_days=window_days,
    title=title,
    goal=goal,
    process_steps=process_steps,
    required_tools=required_tools,
  )

  return {
    "ok": True,
    "workflow_id": wid,
    "workflow_name": workflow.get("name"),
    "source": source,
    "process_map": process_steps,
    "technical_stack": stack_rows,
    "skill_draft": {
      "title": title,
      "goal": goal,
      "instructions": draft.get("instructions", []),
      "required_tools": required_tools,
    },
    "llm_prompt": llm_prompt,
    "estimated_hours_saved_per_week": reclaimed_hours,
    "generated_at": _to_iso(int(time.time())),
  }


def _coerce_automation_blueprint(
  payload: dict[str, Any],
  workflow: dict[str, Any],
  window_days: int,
) -> dict[str, Any]:
  fallback = _heuristic_automation_blueprint(workflow, window_days=window_days)
  fallback_steps = _normalized_process_steps([str(item) for item in (fallback.get("process_map") or [])])
  fallback_stack = fallback.get("technical_stack") or _infer_technical_stack(workflow)
  fallback_required = [str(item).strip() for item in (fallback.get("required_tools") or []) if str(item).strip()]
  fallback_instructions = [str(item).strip() for item in (fallback.get("instructions") or []) if str(item).strip()]

  title = str(payload.get("title") or fallback.get("title") or f"{workflow.get('name', 'Workflow')} Automation").strip()

  process_steps = _normalized_process_steps([str(item) for item in (payload.get("process_map") or [])])
  if not process_steps:
    process_steps = fallback_steps

  stack_rows: list[dict[str, str]] = []
  raw_stack = payload.get("technical_stack")
  if isinstance(raw_stack, list):
    for row in raw_stack:
      if not isinstance(row, dict):
        continue
      tool = str(row.get("tool", "")).strip()
      if not tool:
        continue
      stack_rows.append(
        {
          "tool": tool,
          "mcp_server": str(row.get("mcp_server", "") or "custom").strip() or "custom",
          "purpose": str(row.get("purpose", "") or "Support this workflow automation step.").strip(),
        }
      )
  if not stack_rows:
    stack_rows = [
      {
        "tool": str(row.get("tool", "Tool")),
        "mcp_server": str(row.get("mcp_server", "custom")),
        "purpose": str(row.get("purpose", "Support this workflow automation step.")),
      }
      for row in fallback_stack
      if isinstance(row, dict)
    ]

  required_tools = [str(item).strip() for item in (payload.get("required_tools") or []) if str(item).strip()]
  if not required_tools:
    required_tools = [str(row.get("tool", "")).strip() for row in stack_rows if str(row.get("tool", "")).strip()]
  if not required_tools:
    required_tools = fallback_required

  stack_rows, required_tools = _align_stack_and_required_tools_to_workflow(workflow, stack_rows, required_tools)
  recovered_hours = round((_estimate_weekly_minutes(workflow) * 0.65) / 60.0, 2)
  stack_tools = [str(row.get("tool", "")).strip() for row in stack_rows if str(row.get("tool", "")).strip()]
  source_tool = stack_tools[0] if stack_tools else "Source App"
  target_tool = stack_tools[1] if len(stack_tools) > 1 else source_tool
  goal = (
    f"Reclaim {recovered_hours:.2f} hours/week by automating the transition between "
    f"{source_tool} and {target_tool}."
  )

  instructions = [str(item).strip() for item in (payload.get("instructions") or []) if str(item).strip()]
  if len(instructions) < 4:
    instructions = (instructions + fallback_instructions)[:4]
  if len(instructions) < 4:
    instructions = [
      "Monitor: Watch for qualifying trigger events in the source system.",
      "Extract: Pull required fields and classify them by workflow schema.",
      "Action: Transform and write data to destination systems with idempotency checks.",
      "Verification: Send a summary notification and log anomalies for review.",
    ]

  llm_prompt = _build_llm_prompt_payload(
    workflow=workflow,
    window_days=window_days,
    title=title,
    goal=goal,
    process_steps=process_steps,
    required_tools=required_tools,
  )

  return {
    "title": title,
    "goal": goal,
    "process_map": process_steps[:10],
    "technical_stack": stack_rows[:8],
    "instructions": instructions[:4],
    "required_tools": required_tools[:8],
    "llm_prompt": llm_prompt,
  }


def _llm_edit_automation_blueprint_from_ollama(
  workflow: dict[str, Any],
  window_days: int,
  edit_instruction: str,
  current_blueprint: dict[str, Any],
) -> dict[str, Any] | None:
  compact_workflow = {
    "name": workflow.get("name"),
    "category": workflow.get("category"),
    "details": workflow.get("details"),
    "tools": workflow.get("tools"),
    "steps": [step.get("action") for step in (workflow.get("steps") or [])],
    "frequency": workflow.get("frequency"),
  }
  compact_current = {
    "title": current_blueprint.get("title"),
    "goal": current_blueprint.get("goal"),
    "process_map": current_blueprint.get("process_map"),
    "instructions": current_blueprint.get("instructions"),
    "required_tools": current_blueprint.get("required_tools"),
    "technical_stack": current_blueprint.get("technical_stack"),
  }

  prompt = (
    "You are editing an automation blueprint for a productivity workflow dashboard. "
    "Apply the user's natural-language edit request to the existing blueprint. "
    "Return JSON only with this exact shape:\n"
    '{"title":"...","goal":"...","process_map":["..."],'
    '"technical_stack":[{"tool":"...","mcp_server":"...","purpose":"..."}],'
    '"instructions":["...","...","...","..."],"required_tools":["..."]}\n'
    "Rules: process_map must be 3-10 concise steps; instructions must be exactly 4 lines "
    "(Monitor, Extract, Action, Verification); required_tools must match technical_stack tools. "
    "Only use tools present in workflow evidence/current blueprint; do not invent new tools. Do not output markdown.\n"
    f"User edit request:\n{edit_instruction}\n"
    f"Current blueprint:\n{json.dumps(compact_current, ensure_ascii=True)}\n"
    f"Workflow evidence:\n{json.dumps(compact_workflow, ensure_ascii=True)}\n"
    f"Window days: {int(max(1, window_days))}"
  )
  generated = _ollama_generate(
    prompt=prompt,
    timeout_seconds=10,
    format_json=True,
    env_keys=("WORKFLOW_AUTOMATION_MODEL", "WORKFLOW_EXPLAIN_MODEL", "WORKFLOW_LLM_MODEL"),
  )
  if not generated:
    return None
  raw_text, _used_model = generated

  parsed_payload: dict[str, Any] | None = None
  try:
    parsed_payload = json.loads(raw_text)
  except json.JSONDecodeError:
    block = _extract_json_block(raw_text)
    if block:
      try:
        parsed_payload = json.loads(block)
      except json.JSONDecodeError:
        parsed_payload = None
  if not isinstance(parsed_payload, dict):
    return None

  return _coerce_automation_blueprint(parsed_payload, workflow, window_days)


def _heuristic_edit_automation_blueprint(
  workflow: dict[str, Any],
  window_days: int,
  edit_instruction: str,
  current_blueprint: dict[str, Any],
) -> dict[str, Any]:
  edited = _coerce_automation_blueprint(current_blueprint, workflow, window_days)
  instruction = str(edit_instruction or "").strip()
  if not instruction:
    return edited

  low = instruction.lower()
  steps = _normalized_process_steps([str(item) for item in (edited.get("process_map") or [])])
  if not steps:
    steps = _workflow_step_actions(workflow)

  replace_match = re.search(r"replace\s+(.+?)\s+with\s+(.+)$", low)
  if replace_match:
    old_token = replace_match.group(1).strip()
    new_token = instruction[replace_match.start(2) :].strip()
    replaced = False
    for idx, step in enumerate(steps):
      if old_token and old_token in step.lower():
        steps[idx] = new_token
        replaced = True
    if not replaced:
      steps.append(new_token)
  else:
    remove_match = re.search(r"remove\s+(.+?)(?:\s+step|\s+from|$)", low)
    if remove_match:
      token = remove_match.group(1).strip()
      filtered = [step for step in steps if token not in step.lower()]
      if filtered:
        steps = filtered
    add_match = re.search(r"(?:add|insert)\s+(?:a\s+)?(?:step\s+)?(?:to\s+)?(.+)$", instruction, flags=re.IGNORECASE)
    if add_match:
      steps.append(add_match.group(1).strip())
    elif not remove_match:
      steps.append(f"Apply operator edit: {instruction}")

  edited["process_map"] = _normalized_process_steps(steps)[:10]
  instructions = [str(item).strip() for item in (edited.get("instructions") or []) if str(item).strip()]
  if instructions:
    instructions[2] = f"Action: Execute the revised process map and apply user edit: {instruction}"
  edited["instructions"] = (instructions + ["Verification: Confirm outcomes and report exceptions."])[:4]
  edited["goal"] = f"{str(edited.get('goal') or '').strip()} Updated with operator edit."
  edited["llm_prompt"] = _build_llm_prompt_payload(
    workflow=workflow,
    window_days=window_days,
    title=str(edited.get("title") or f"{workflow.get('name', 'Workflow')} Automation"),
    goal=str(edited.get("goal") or "Automate repetitive transitions between tools."),
    process_steps=[str(item) for item in (edited.get("process_map") or [])],
    required_tools=[str(item) for item in (edited.get("required_tools") or []) if str(item).strip()],
  )
  return edited


def revise_workflow_automation(
  workflow_id: str,
  edit_instruction: str,
  window_days: int = 14,
  max_workflows: int = 12,
  base_draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
  wid = str(workflow_id or "").strip()
  instruction = str(edit_instruction or "").strip()
  if not wid:
    return {"ok": False, "error": "workflow_id_required"}
  if not instruction:
    return {"ok": False, "error": "edit_instruction_required", "workflow_id": wid}

  insights = build_workflow_insights(window_days=window_days, max_workflows=max_workflows)
  workflows = insights.get("workflows") or []
  workflow = next((row for row in workflows if str(row.get("id")) == wid), None)
  if not workflow:
    return {"ok": False, "error": "workflow_not_found", "workflow_id": wid}

  baseline_payload = base_draft if isinstance(base_draft, dict) else {}
  baseline_skill = baseline_payload.get("skill_draft") if isinstance(baseline_payload.get("skill_draft"), dict) else {}
  baseline_blueprint = _coerce_automation_blueprint(
    {
      "title": baseline_skill.get("title") or baseline_payload.get("title"),
      "goal": baseline_skill.get("goal") or baseline_payload.get("goal"),
      "process_map": baseline_payload.get("process_map"),
      "technical_stack": baseline_payload.get("technical_stack"),
      "instructions": baseline_skill.get("instructions") or baseline_payload.get("instructions"),
      "required_tools": baseline_skill.get("required_tools") or baseline_payload.get("required_tools"),
    },
    workflow,
    window_days,
  )

  source = "llm-edit"
  edited = _llm_edit_automation_blueprint_from_ollama(workflow, window_days, instruction, baseline_blueprint)
  if not edited:
    source = "heuristic-edit"
    edited = _heuristic_edit_automation_blueprint(workflow, window_days, instruction, baseline_blueprint)

  reclaimed_hours = round((_estimate_weekly_minutes(workflow) * 0.65) / 60.0, 2)
  return {
    "ok": True,
    "workflow_id": wid,
    "workflow_name": workflow.get("name"),
    "source": source,
    "process_map": edited.get("process_map", []),
    "technical_stack": edited.get("technical_stack", []),
    "skill_draft": {
      "title": str(edited.get("title") or f"{workflow.get('name', 'Workflow')} Automation"),
      "goal": str(edited.get("goal") or "Automate repetitive transitions between tools."),
      "instructions": edited.get("instructions", []),
      "required_tools": edited.get("required_tools", []),
    },
    "llm_prompt": str(edited.get("llm_prompt") or ""),
    "estimated_hours_saved_per_week": reclaimed_hours,
    "edit_instruction": instruction,
    "generated_at": _to_iso(int(time.time())),
  }


def explain_workflow_insight(workflow_id: str, window_days: int = 14, max_workflows: int = 12) -> dict[str, Any]:
  wid = str(workflow_id or "").strip()
  if not wid:
    return {"ok": False, "error": "workflow_id_required"}

  insights = build_workflow_insights(window_days=window_days, max_workflows=max_workflows)
  workflows = insights.get("workflows") or []
  workflow = next((row for row in workflows if str(row.get("id")) == wid), None)
  if not workflow:
    return {"ok": False, "error": "workflow_not_found", "workflow_id": wid}

  narrative, patterns = _pattern_based_workflow_explanation(workflow, window_days=window_days)
  confidence = _pattern_confidence(patterns)
  evidence = _workflow_evidence_rows(workflow, window_days=window_days, patterns=patterns)
  source = "pattern"

  llm_deciphered = _llm_decipher_workflow_explanation_from_ollama(workflow, window_days=window_days, patterns=patterns)
  if llm_deciphered:
    narrative = str(llm_deciphered.get("summary") or narrative)
    confidence = _normalize_confidence_label(llm_deciphered.get("confidence"), fallback=confidence)
    evidence = [
      str(item).strip()
      for item in (llm_deciphered.get("evidence") or evidence)
      if str(item).strip()
    ][:4]
    model = str(llm_deciphered.get("model") or "").strip()
    source = f"llm:{model}" if model else "llm"

  return {
    "ok": True,
    "workflow_id": wid,
    "workflow_name": workflow.get("name"),
    "summary": narrative,
    "source": source,
    "confidence": confidence,
    "evidence": evidence,
    "patterns": patterns,
    "generated_at": _to_iso(int(time.time())),
  }


def _category_ideas(workflows: list[dict[str, Any]]) -> list[dict[str, Any]]:
  grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
  for workflow in workflows:
    category = str(workflow.get("category") or "general")
    grouped[category].extend(workflow.get("automation_ideas", []))

  category_counts = Counter(str(w.get("category") or "general") for w in workflows)
  output: list[dict[str, Any]] = []
  for category, count in category_counts.most_common():
    ideas = grouped.get(category, [])
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for idea in ideas:
      key = str(idea.get("title", "")).strip().lower()
      if not key or key in seen:
        continue
      seen.add(key)
      deduped.append(
        {
          "title": str(idea.get("title", "")),
          "proposal": str(idea.get("proposal", "")),
          "impact": str(idea.get("impact", "")),
        }
      )
      if len(deduped) >= 3:
        break
    output.append({"category": category, "workflow_count": count, "ideas": deduped})
  return output


def _sequence_workflows(sessions: list[list[CommandEvent]], window_days: int, max_workflows: int) -> list[dict[str, Any]]:
  sequence_session_support: dict[tuple[str, ...], set[int]] = defaultdict(set)
  sequence_total_runs: Counter[tuple[str, ...]] = Counter()
  sequence_last_seen: dict[tuple[str, ...], int] = {}

  for session_id, session in enumerate(sessions):
    actions = _session_actions(session)
    if len(actions) < 3:
      continue

    seen_here: set[tuple[str, ...]] = set()
    upper_n = min(6, len(actions))
    for width in range(3, upper_n + 1):
      for start in range(0, len(actions) - width + 1):
        seq = tuple(actions[start : start + width])
        sequence_total_runs[seq] += 1
        if seq not in seen_here:
          sequence_session_support[seq].add(session_id)
          seen_here.add(seq)
        seq_ts = session[min(len(session) - 1, start + width - 1)].timestamp
        if seq_ts > sequence_last_seen.get(seq, 0):
          sequence_last_seen[seq] = seq_ts

  scored: list[tuple[float, tuple[str, ...], int, int]] = []
  for seq, total_runs in sequence_total_runs.items():
    support_sessions = len(sequence_session_support[seq])
    if support_sessions < MIN_SUPPORT_SESSIONS and total_runs < 3:
      continue
    score = support_sessions * 2.6 + len(seq) * 1.2 + total_runs * 0.8
    scored.append((score, seq, support_sessions, total_runs))

  scored.sort(key=lambda row: row[0], reverse=True)

  selected: list[tuple[float, tuple[str, ...], int, int]] = []
  for candidate in scored:
    _, seq, _, _ = candidate
    if any(_is_contained(seq, existing[1]) for existing in selected):
      continue
    selected.append(candidate)
    if len(selected) >= max_workflows:
      break

  workflows: list[dict[str, Any]] = []
  for index, (_, seq, support_sessions, total_runs) in enumerate(selected, start=1):
    tools = _tools_from_sequence(seq)
    category, category_score = _classify_category(seq, tools)
    confidence = min(0.97, 0.35 + support_sessions * 0.12 + len(seq) * 0.04 + category_score * 0.03)
    last_seen = sequence_last_seen.get(seq, int(time.time()))
    workflow = {
      "id": f"wf-{index}",
      "name": _workflow_name(seq, tools, category),
      "details": _workflow_details_text(
        seq=seq,
        tools=tools,
        total_runs=total_runs,
        support_sessions=support_sessions,
        window_days=window_days,
      ),
      "category": category,
      "confidence": round(confidence, 2),
      "tools": tools,
      "steps": [
        {
          "order": step_idx + 1,
          "action": action,
          "tool": (_tool_keys_from_action(action) or [action.split(" ", 1)[0].strip().lower()])[0],
        }
        for step_idx, action in enumerate(seq)
      ],
      "frequency": {
        "runs_total": total_runs,
        "sessions": support_sessions,
        "per_week": round((support_sessions / max(1, window_days)) * 7, 2),
        "last_seen": _to_iso(last_seen),
      },
      "automation_ideas": [],
    }
    workflows.append(workflow)

  return workflows


def _fallback_tool_workflows(events: list[CommandEvent], window_days: int, max_workflows: int) -> list[dict[str, Any]]:
  by_tool: dict[str, list[CommandEvent]] = defaultdict(list)
  for event in events:
    by_tool[event.tool].append(event)

  workflows: list[dict[str, Any]] = []
  for index, (tool, rows) in enumerate(sorted(by_tool.items(), key=lambda kv: len(kv[1]), reverse=True), start=1):
    if len(rows) < 6:
      continue
    action_counts = Counter(row.action for row in rows)
    top_steps = [action for action, _ in action_counts.most_common(3)]
    if len(top_steps) < 2:
      continue
    seq = tuple(top_steps)
    tools = _tools_from_sequence(seq)
    category, category_score = _classify_category(seq, tools)
    confidence = min(0.91, 0.4 + len(rows) / 80.0 + category_score * 0.03)
    last_seen = max(row.timestamp for row in rows)
    workflow = {
      "id": f"wf-{index}",
      "name": _workflow_name(seq, tools, category),
      "details": _workflow_details_text(
        seq=seq,
        tools=tools,
        total_runs=len(rows),
        support_sessions=max(1, int(len(rows) / 5)),
        window_days=window_days,
      ),
      "category": category,
      "confidence": round(confidence, 2),
      "tools": tools,
      "steps": [
        {
          "order": step_idx + 1,
          "action": action,
          "tool": (_tool_keys_from_action(action) or [action.split(" ", 1)[0].strip().lower()])[0],
        }
        for step_idx, action in enumerate(seq)
      ],
      "frequency": {
        "runs_total": len(rows),
        "sessions": max(1, int(len(rows) / 5)),
        "per_week": round((len(rows) / max(1, window_days)) * 7, 2),
        "last_seen": _to_iso(last_seen),
      },
      "automation_ideas": [],
    }
    workflows.append(workflow)
    if len(workflows) >= max_workflows:
      break

  return workflows


def _sample_workflows(window_days: int) -> list[dict[str, Any]]:
  now = int(time.time())
  return [
    {
      "id": "wf-1",
      "name": "Research to Draft Loop",
      "details": "Sample fallback workflow: gather sources, synthesize, and draft outputs.",
      "category": "research",
      "confidence": 0.62,
      "tools": ["browser", "notion", "python"],
      "steps": [
        {"order": 1, "action": "browser open", "tool": "browser"},
        {"order": 2, "action": "notion update", "tool": "notion"},
        {"order": 3, "action": "python synthesize", "tool": "python"},
      ],
      "frequency": {
        "runs_total": 9,
        "sessions": 4,
        "per_week": round((4 / max(1, window_days)) * 7, 2),
        "last_seen": _to_iso(now - 3600),
      },
      "automation_ideas": [],
    },
    {
      "id": "wf-2",
      "name": "Build-Test-Commit Loop",
      "details": "Sample fallback workflow: iterative coding and quality checks.",
      "category": "engineering",
      "confidence": 0.69,
      "tools": ["git", "npm", "pytest"],
      "steps": [
        {"order": 1, "action": "git status", "tool": "git"},
        {"order": 2, "action": "npm test", "tool": "npm"},
        {"order": 3, "action": "git commit", "tool": "git"},
      ],
      "frequency": {
        "runs_total": 13,
        "sessions": 6,
        "per_week": round((6 / max(1, window_days)) * 7, 2),
        "last_seen": _to_iso(now - 5400),
      },
      "automation_ideas": [],
    },
  ]


def _event_to_ledger_category(event: CommandEvent) -> str:
  text = f"{event.tool} {event.action}".lower()
  action = str(event.action or "").strip().lower()

  if action.startswith("browser visit "):
    domain = action.replace("browser visit ", "", 1).strip().lower()
    if any(token in domain for token in ("meet.google.com", "zoom.us", "teams.microsoft.com")):
      return "meetings"
    if any(token in domain for token in ("figma.com", "canva.com", "miro.com", "youtube.com")):
      return "creative"
    if any(
      token in domain
      for token in (
        "mail.google.com",
        "gmail.com",
        "docs.google.com",
        "sheets.google.com",
        "drive.google.com",
        "calendar.google.com",
        "web.whatsapp.com",
        "linkedin.com",
        "slack.com",
        "salesforce.com",
        "hubspot.com",
      )
    ):
      return "admin"
    return "deep"

  if any(token in text for token in ("zoom", "teams", "meet", "calendar", "call")):
    return "meetings"
  if any(token in text for token in ("figma", "canva", "design", "draft", "creative", "write", "notion", "powerpoint", "slides")):
    return "creative"
  if any(
    token in text
    for token in (
      "mail",
      "gmail",
      "slack",
      "sheet",
      "excel",
      "airtable",
      "admin",
      "ops",
      "google_docs",
      "google_sheets",
      "granola",
    )
  ):
    return "admin"
  return "deep"


def _blank_period_row(label: str, curr: date) -> dict[str, Any]:
  return {
    "day": label,
    "date": curr.isoformat(),
    "admin": 0,
    "deep": 0,
    "creative": 0,
    "meetings": 0,
    "total": 0,
    "event_count": 0,
    "switch_count": 0,
    "_last_tool": "",
    "friction_score": 0,
  }


def _blank_daily_rows(start: date, days: int) -> list[dict[str, Any]]:
  rows: list[dict[str, Any]] = []
  count = max(1, int(days))
  for idx in range(count):
    curr = start + timedelta(days=idx)
    label = curr.strftime("%a") if count <= 14 else curr.strftime("%d")
    rows.append(_blank_period_row(label, curr))
  return rows


def _blank_weekly_rows(start: date, window_days: int) -> list[dict[str, Any]]:
  rows: list[dict[str, Any]] = []
  bucket_count = max(1, (max(1, int(window_days)) + 6) // 7)
  for idx in range(bucket_count):
    curr = start + timedelta(days=idx * 7)
    row = _blank_period_row(f"W{idx + 1}", curr)
    rows.append(row)
  return rows


def _bucket_index(target_day: date, start_day: date, mode: str) -> int:
  delta_days = (target_day - start_day).days
  if delta_days < 0:
    return -1
  if mode == "weekly":
    return delta_days // 7
  return delta_days


def _build_weekly_horizon(events: list[CommandEvent], window_days: int = 7) -> dict[str, Any]:
  days = max(1, min(90, int(window_days)))
  mode = "daily" if days <= 30 else "weekly"
  now_local = datetime.now().date()
  current_end = now_local
  current_start = current_end - timedelta(days=days - 1)
  previous_end = current_start - timedelta(days=1)
  previous_start = previous_end - timedelta(days=days - 1)

  if mode == "weekly":
    current_rows = _blank_weekly_rows(current_start, days)
    previous_rows = _blank_weekly_rows(previous_start, days)
  else:
    current_rows = _blank_daily_rows(current_start, days)
    previous_rows = _blank_daily_rows(previous_start, days)

  sorted_events = sorted(events, key=lambda row: row.timestamp)
  for idx, event in enumerate(sorted_events):
    next_ts = 0
    if idx + 1 < len(sorted_events):
      next_event = sorted_events[idx + 1]
      if datetime.fromtimestamp(next_event.timestamp).date() == datetime.fromtimestamp(event.timestamp).date():
        next_ts = next_event.timestamp
    if next_ts > event.timestamp:
      duration_seconds = max(60, min(20 * 60, next_ts - event.timestamp))
    else:
      duration_seconds = 180
    minutes = max(1, int(round(duration_seconds / 60)))

    event_day = datetime.fromtimestamp(event.timestamp).date()
    category = _event_to_ledger_category(event)
    row = None
    if current_start <= event_day <= current_end:
      curr_idx = _bucket_index(event_day, current_start, mode)
      if 0 <= curr_idx < len(current_rows):
        row = current_rows[curr_idx]
    elif previous_start <= event_day <= previous_end:
      prev_idx = _bucket_index(event_day, previous_start, mode)
      if 0 <= prev_idx < len(previous_rows):
        row = previous_rows[prev_idx]
    if row is None:
      continue
    row[category] += minutes
    row["total"] += minutes
    row["event_count"] += 1
    tool = str(event.tool or "").lower()
    if tool and row["_last_tool"] and row["_last_tool"] != tool:
      row["switch_count"] += 1
    if tool:
      row["_last_tool"] = tool

  for rows in (current_rows, previous_rows):
    for row in rows:
      event_count = max(1, int(row["event_count"]))
      switch_density = float(row["switch_count"]) / float(event_count)
      admin_ratio = float(row["admin"]) / float(max(1, int(row["total"])))
      friction_score = min(100, int(round((switch_density * 70.0 + admin_ratio * 30.0) * 100.0)))
      row["friction_score"] = friction_score
      row.pop("_last_tool", None)

  def aggregate(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
      "admin": int(sum(int(row["admin"]) for row in rows)),
      "deep": int(sum(int(row["deep"]) for row in rows)),
      "creative": int(sum(int(row["creative"]) for row in rows)),
      "meetings": int(sum(int(row["meetings"]) for row in rows)),
      "total_minutes": int(sum(int(row["total"]) for row in rows)),
    }

  active_current = [int(row["total"]) for row in current_rows if int(row["total"]) > 0]
  if active_current:
    target_focus_minutes = int(round(sum(active_current) / len(active_current)))
  else:
    target_focus_minutes = 240 if mode == "daily" else 1200
  target_focus_minutes = max(30, target_focus_minutes)

  return {
    "days": [row["day"] for row in current_rows],
    "bucket_mode": mode,
    "bucket_count": len(current_rows),
    "window_days": days,
    "current_week": current_rows,
    "previous_week": previous_rows,
    "totals": {
      "current_week": aggregate(current_rows),
      "previous_week": aggregate(previous_rows),
    },
    "target_focus_minutes": target_focus_minutes,
  }


def _tool_label_from_event(event: CommandEvent) -> tuple[str, str]:
  action = str(event.action or "").strip()
  domain = _extract_browser_visit_domain(action)
  if domain:
    key = _tool_from_browser_context(domain)
    return f"Browser: {domain}", key
  key = _normalize_tool_key(str(event.tool or ""))
  if not key:
    key = str(event.tool or "").strip().lower() or "tool"
  return _friendly_tool_name(key), key


def _workflow_tool_keys(workflow: dict[str, Any]) -> set[str]:
  keys: set[str] = set()
  for raw in workflow.get("tools") or []:
    key = _normalize_tool_key(str(raw or ""))
    if key:
      keys.add(key)
  for step in workflow.get("steps") or []:
    action = str(step.get("action") or "").strip()
    for step_key in _tool_keys_from_action(action):
      key = _normalize_tool_key(step_key)
      if key:
        keys.add(key)
  return keys


def _aggregate_tool_usage(events: list[CommandEvent], workflows: list[dict[str, Any]]) -> list[dict[str, Any]]:
  if not events:
    return []

  usage: dict[str, dict[str, Any]] = {}
  source_events = _events_for_behavioral_analysis(events)
  sorted_events = sorted(source_events, key=lambda row: row.timestamp)
  for idx, event in enumerate(sorted_events):
    next_ts = 0
    if idx + 1 < len(sorted_events):
      next_event = sorted_events[idx + 1]
      if datetime.fromtimestamp(next_event.timestamp).date() == datetime.fromtimestamp(event.timestamp).date():
        next_ts = next_event.timestamp
    if next_ts > event.timestamp:
      duration_seconds = max(60, min(20 * 60, next_ts - event.timestamp))
    else:
      duration_seconds = 180
    minutes = max(1, int(round(duration_seconds / 60)))

    label, tool_key = _tool_label_from_event(event)
    row = usage.get(label)
    if row is None:
      row = {
        "tool": label,
        "tool_key": tool_key,
        "minutes": 0,
        "workflows_count": 0,
      }
      usage[label] = row
    row["minutes"] += minutes

  workflow_key_sets = [_workflow_tool_keys(workflow) for workflow in workflows]
  for row in usage.values():
    key = str(row.get("tool_key", "")).strip().lower()
    count = 0
    for key_set in workflow_key_sets:
      if key and key in key_set:
        count += 1
      elif key == "browser" and "browser" in key_set:
        count += 1
    row["workflows_count"] = count

  rows = list(usage.values())
  rows.sort(key=lambda row: (-int(row.get("minutes", 0)), str(row.get("tool", "")).lower()))
  return rows[:120]


def _estimate_weekly_minutes(workflow: dict[str, Any]) -> float:
  per_week = float(workflow.get("frequency", {}).get("per_week", 0.0))
  steps = max(1, len(workflow.get("steps") or []))
  tools = max(1, len(workflow.get("tools") or []))
  return per_week * (steps * 3 + tools * 1.5)


def _workflow_dna_rows(workflows: list[dict[str, Any]], max_rows: int = 6) -> list[dict[str, Any]]:
  rows: list[dict[str, Any]] = []
  for workflow in workflows:
    steps = workflow.get("steps") or []
    sequence = " -> ".join(str(step.get("action", "")).strip() for step in steps[:5] if str(step.get("action", "")).strip())
    if not sequence:
      continue
    rows.append(
      {
        "name": str(workflow.get("name", "Workflow")),
        "sequence": sequence,
        "category": str(workflow.get("category", "general")),
        "runs_per_week": float(workflow.get("frequency", {}).get("per_week", 0.0)),
      }
    )
  rows.sort(key=lambda row: row["runs_per_week"], reverse=True)
  return rows[:max_rows]


def _time_reclamation_summary(workflows: list[dict[str, Any]]) -> dict[str, Any]:
  items: list[dict[str, Any]] = []
  total_minutes = 0.0
  for workflow in workflows:
    weekly_minutes = _estimate_weekly_minutes(workflow)
    reclaim_minutes = weekly_minutes * 0.65
    total_minutes += reclaim_minutes
    items.append(
      {
        "name": str(workflow.get("name", "Workflow")),
        "hours_saved_per_week": round(reclaim_minutes / 60.0, 2),
      }
    )
  items.sort(key=lambda row: row["hours_saved_per_week"], reverse=True)
  return {
    "hours_saved_per_week": round(total_minutes / 60.0, 2),
    "top_workflows": items[:5],
  }


def generate_weekly_blueprint(base_dir: Path, window_days: int = 14) -> dict[str, Any]:
  insights = build_workflow_insights(window_days=max(7, int(window_days)), max_workflows=12)
  workflows = insights.get("workflows", [])
  dna = insights.get("workflow_dna", [])
  reclamation = insights.get("time_reclamation", {"hours_saved_per_week": 0.0, "top_workflows": []})
  generated_at = insights.get("generated_at", _to_iso(int(time.time())))
  path = base_dir / "WEEKLY_BLUEPRINT.md"

  lines: list[str] = [
    "# WEEKLY_BLUEPRINT",
    "",
    f"Generated: {generated_at}",
    "",
    "## Workflow DNA",
    "Repetitive app-switching sequences detected over the last 7 days:",
  ]
  if dna:
    for row in dna:
      lines.append(
        f"- **{row['name']}** ({row['category']}): `{row['sequence']}` "
        f"~ {row['runs_per_week']:.2f} runs/week"
      )
  else:
    lines.append("- No high-confidence repetitive sequences detected.")

  lines.extend(["", "## Time Reclamation"])
  lines.append(
    "Estimated hours saved if repetitive tasks are offloaded to an automation agent:"
    f" **{float(reclamation.get('hours_saved_per_week', 0.0)):.2f} hours/week**."
  )
  top = reclamation.get("top_workflows", [])
  if top:
    lines.append("")
    lines.append("Breakdown:")
    for item in top:
      lines.append(f"- {item['name']}: {float(item['hours_saved_per_week']):.2f} h/week")

  lines.extend(["", "## Candidate Agent Targets"])
  if workflows:
    for workflow in workflows[:5]:
      idea = (workflow.get("automation_ideas") or [{}])[0]
      lines.append(f"- **{workflow.get('name', 'Workflow')}**: {idea.get('proposal', 'Package as reusable automation.')}")
  else:
    lines.append("- No workflows available.")

  path.write_text("\n".join(lines) + "\n", encoding="utf-8")
  return {
    "ok": True,
    "file": str(path),
    "workflow_dna_count": len(dna),
    "time_reclamation_hours_per_week": reclamation.get("hours_saved_per_week", 0.0),
  }


def build_workflow_insights(window_days: int = 14, max_workflows: int = 10) -> dict[str, Any]:
  days = max(1, min(90, int(window_days)))
  events, sources = _collect_events(days)
  analysis_events = _events_for_behavioral_analysis(events)
  sessions = _build_sessions(analysis_events)

  workflows = _sequence_workflows(sessions, days, max_workflows=max_workflows)
  if not workflows:
    workflows = _fallback_tool_workflows(analysis_events, days, max_workflows=max_workflows)
  if not workflows:
    workflows = _sample_workflows(days)
  workflows = _group_similar_workflows(workflows, max_workflows=max_workflows, window_days=days)
  workflows.extend(_tool_signal_workflows(workflows, analysis_events, window_days=days, max_workflows=max_workflows))
  workflows.sort(
    key=lambda row: (
      float((row.get("frequency") or {}).get("per_week", 0.0)),
      int((row.get("frequency") or {}).get("runs_total", 0)),
      float(row.get("confidence", 0.0)),
    ),
    reverse=True,
  )
  workflows = workflows[: max(1, int(max_workflows))]

  llm_ideas = _llm_ideas_from_ollama(workflows)
  idea_source = "heuristic"
  if llm_ideas:
    idea_source = "llm"

  for workflow in workflows:
    if llm_ideas and workflow["id"] in llm_ideas and llm_ideas[workflow["id"]]:
      workflow["automation_ideas"] = llm_ideas[workflow["id"]][:2]
    else:
      workflow["automation_ideas"] = _heuristic_ideas(workflow)

  category_counts = Counter(str(workflow["category"]) for workflow in workflows)
  tool_usage = _aggregate_tool_usage(analysis_events, workflows)
  if tool_usage:
    top_tools = [{"tool": str(row.get("tool", "")), "score": int(row.get("minutes", 0))} for row in tool_usage[:8]]
    unique_tools = len(tool_usage)
  else:
    tool_weight = Counter()
    for workflow in workflows:
      for tool in workflow.get("tools", []):
        tool_weight[tool] += max(1, int(workflow["frequency"]["runs_total"]))
    top_tools = [{"tool": tool, "score": score} for tool, score in tool_weight.most_common(8)]
    unique_tools = len(tool_weight)

  summary = {
    "workflows_detected": len(workflows),
    "estimated_runs_per_week": round(sum(float(row["frequency"]["per_week"]) for row in workflows), 2),
    "unique_tools": unique_tools,
    "top_tools": top_tools,
    "category_breakdown": [{"category": name, "count": count} for name, count in category_counts.most_common()],
  }

  payload = {
    "ok": True,
    "generated_at": _to_iso(int(time.time())),
    "window_days": days,
    "idea_source": idea_source,
    "scan": {
      "events_analyzed": len(analysis_events),
      "events_collected": len(events),
      "sessions_analyzed": len(sessions),
      "sources": sources,
    },
    "summary": summary,
    "workflows": workflows,
    "tool_usage": tool_usage,
    "category_ideas": _category_ideas(workflows),
    "weekly_horizon": _build_weekly_horizon(analysis_events, days),
    "workflow_dna": _workflow_dna_rows(workflows),
    "time_reclamation": _time_reclamation_summary(workflows),
  }
  return payload
