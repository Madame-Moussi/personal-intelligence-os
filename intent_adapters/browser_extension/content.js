(() => {
  const API_URL = "http://127.0.0.1:5180/api/intent/events";
  const SOURCE = "chrome_content_script";

  const intentFromDom = () => {
    const href = String(window.location.href || "").toLowerCase();
    const title = String(document.title || "").toLowerCase();
    const text = `${href} ${title}`;

    if (text.includes("linkedin.com/jobs")) {
      if (text.includes("apply")) {
        return { intent: "job_search", action: "start_application", stage: "interaction" };
      }
      return { intent: "job_search", action: "browse_jobs", stage: "interaction" };
    }
    if (text.includes("linkedin.com/in/")) {
      return { intent: "networking", action: "review_profile", stage: "interaction" };
    }
    if (text.includes("docs.google.com")) {
      return { intent: "drafting", action: "edit_document", stage: "interaction" };
    }
    if (text.includes("sheets.google.com")) {
      return { intent: "tracking", action: "edit_sheet", stage: "interaction" };
    }
    if (text.includes("figma.com")) {
      return { intent: "design_iteration", action: "edit_design", stage: "interaction" };
    }
    return { intent: "research", action: "read_or_browse", stage: "interaction" };
  };

  let lastSent = 0;
  const send = async (event) => {
    const now = Date.now();
    if (now - lastSent < 30000) return;
    lastSent = now;
    try {
      await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event),
        keepalive: true,
      });
    } catch {
      // No-op when local server is down.
    }
  };

  const emit = () => {
    const url = window.location.href;
    let domain = "";
    try {
      domain = new URL(url).hostname.replace(/^www\./, "");
    } catch {
      domain = "";
    }
    if (!domain) return;
    const inferred = intentFromDom();
    send({
      timestamp: new Date().toISOString(),
      source: SOURCE,
      app: "chrome",
      tool: "browser",
      domain,
      url,
      title: document.title || "",
      intent: inferred.intent,
      action: inferred.action,
      stage: inferred.stage,
      confidence: 0.7,
    });
  };

  document.addEventListener("click", () => emit(), { passive: true });
  document.addEventListener("submit", () => emit(), { passive: true });
  window.addEventListener("focus", () => emit(), { passive: true });
})();
