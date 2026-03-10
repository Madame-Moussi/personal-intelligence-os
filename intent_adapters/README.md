# Intent Adapters (Low Overhead)

These adapters enrich Personal Intelligence OS with app-level intent signals, without OCR/screen recording.

## Included adapters

- `browser_extension/`:
  - Chrome extension starter for domain + navigation + interaction intent.
- `pollers/gmail_adapter.py`:
  - Reads Gmail metadata (subject/from/to) and infers likely intent.
- `pollers/slack_adapter.py`:
  - Reads Slack channel messages and infers likely coordination intent.
- `pollers/workspace_adapter.py`:
  - Reads Google Drive Activity (Docs/Sheets/Slides events).
- `pollers/granola_adapter.py`:
  - Scans Granola export files for updated notes.

## Run once

```bash
cd "/Users/hopemoussi/Documents/New project/workflow-automation-dashboard"
python3 -m intent_adapters.pollers.run_adapters --adapters all
```

## Run continuously (low-overhead polling)

```bash
python3 -m intent_adapters.pollers.run_adapters --adapters gmail,slack,workspace,granola --daemon --interval 300
```

## Adapter config

Copy and fill:

```bash
cp "/Users/hopemoussi/Documents/New project/workflow-automation-dashboard/intent_adapters/pollers/.env.example" \
   "/Users/hopemoussi/Documents/New project/workflow-automation-dashboard/.env.adapters"
```

Then export the variables (or source the file) before running adapters.

## Notes

- Events are posted to: `POST /api/intent/events`
- State file defaults to: `~/.personal_intelligence_os/adapter_state.json`
- Gmail/Google Workspace/Slack require API tokens with the right scopes.
