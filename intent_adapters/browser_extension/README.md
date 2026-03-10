# Browser Intent Adapter (Starter)

This Chrome extension sends lightweight intent events to the local Personal Intelligence OS server.

## Load extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select this folder:
   - `/Users/hopemoussi/Documents/New project/workflow-automation-dashboard/intent_adapters/browser_extension`

## Required server route

- `POST http://127.0.0.1:5180/api/intent/events`

## Event shape (example)

```json
{
  "timestamp": "2026-03-09T18:44:12Z",
  "source": "chrome_extension",
  "app": "chrome",
  "tool": "browser",
  "domain": "linkedin.com",
  "url": "https://www.linkedin.com/jobs/search/",
  "title": "LinkedIn Jobs",
  "intent": "job_search",
  "action": "browse_jobs",
  "stage": "navigation",
  "confidence": 0.65
}
```

## Notes

- This is event-based and low overhead (no OCR, no screenshots, no video capture).
- The heuristics are intentionally simple; refine `service_worker.js` and `content.js` per your workflows.
