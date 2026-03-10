const API_URL = "http://127.0.0.1:5180/api/intent/events";
const SOURCE = "chrome_extension";
const DEDUPE_WINDOW_MS = 15000;

const recentEvents = new Map();

function nowIso() {
  return new Date().toISOString();
}

function canonicalDomain(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "";
  }
}

function inferIntent(domain, title, url, trigger = "focus") {
  const text = `${domain} ${title || ""} ${url || ""}`.toLowerCase();

  if (domain.includes("linkedin.com")) {
    if (text.includes("/jobs/") || text.includes("job")) {
      return { intent: "job_search", action: "browse_jobs", stage: trigger };
    }
    if (text.includes("/in/") || text.includes("profile")) {
      return { intent: "networking", action: "review_profile", stage: trigger };
    }
    if (text.includes("post") || text.includes("feed")) {
      return { intent: "audience_building", action: "content_engagement", stage: trigger };
    }
  }

  if (domain.includes("docs.google.com")) {
    return { intent: "drafting", action: "edit_document", stage: trigger };
  }
  if (domain.includes("sheets.google.com")) {
    return { intent: "tracking", action: "update_sheet", stage: trigger };
  }
  if (domain.includes("slides.google.com") || domain.includes("powerpoint")) {
    return { intent: "presentation_building", action: "edit_slides", stage: trigger };
  }
  if (domain.includes("mail.google.com")) {
    return { intent: "email_operations", action: "email_triage", stage: trigger };
  }
  if (domain.includes("figma.com")) {
    return { intent: "design_iteration", action: "edit_design", stage: trigger };
  }
  if (domain.includes("github.com") || domain.includes("gitlab.com")) {
    return { intent: "engineering_delivery", action: "repo_navigation", stage: trigger };
  }

  return { intent: "research", action: "browse_context", stage: trigger };
}

function shouldSend(event) {
  const key = `${event.domain}|${event.intent}|${event.action}|${event.stage}`;
  const ts = Date.now();
  const previous = recentEvents.get(key) || 0;
  if (ts - previous < DEDUPE_WINDOW_MS) {
    return false;
  }
  recentEvents.set(key, ts);
  if (recentEvents.size > 300) {
    for (const [oldKey, oldTs] of recentEvents.entries()) {
      if (ts - oldTs > DEDUPE_WINDOW_MS * 6) {
        recentEvents.delete(oldKey);
      }
    }
  }
  return true;
}

async function sendIntentEvent(event) {
  if (!shouldSend(event)) return;
  try {
    await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
      keepalive: true,
    });
  } catch {
    // Keep adapter silent; local server might be down.
  }
}

async function emitFromTab(tab, trigger = "focus") {
  if (!tab || !tab.url) return;
  const domain = canonicalDomain(tab.url);
  if (!domain) return;

  const inferred = inferIntent(domain, tab.title || "", tab.url, trigger);
  await sendIntentEvent({
    timestamp: nowIso(),
    source: SOURCE,
    app: "chrome",
    tool: "browser",
    domain,
    url: tab.url,
    title: tab.title || "",
    intent: inferred.intent,
    action: inferred.action,
    stage: inferred.stage,
    confidence: 0.65,
  });
}

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    const tab = await chrome.tabs.get(tabId);
    await emitFromTab(tab, "focus");
  } catch {
    // ignore
  }
});

chrome.tabs.onUpdated.addListener(async (_tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" || changeInfo.url) {
    await emitFromTab(tab, "navigation");
  }
});

chrome.alarms.create("pios-heartbeat", { periodInMinutes: 5 });
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== "pios-heartbeat") return;
  try {
    const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (tabs && tabs[0]) {
      await emitFromTab(tabs[0], "heartbeat");
    }
  } catch {
    // ignore
  }
});
