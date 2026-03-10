const CATEGORY_META = {
  admin: { label: "Admin/Email", pattern: "solid", stroke: "#0A0A0A", ghost: "#D1D1D1", fill: "#F7C7A3" },
  deep: { label: "Deep Work", pattern: "hatch", stroke: "#0A0A0A", ghost: "#D1D1D1", fill: "#FDECB2" },
  creative: { label: "Creative", pattern: "dots", stroke: "#0A0A0A", ghost: "#D1D1D1", fill: "#FFD7E6" },
  meetings: { label: "Meetings", pattern: "wash", stroke: "#8F8F8F", ghost: "#D1D1D1", fill: "#CBE0F8" },
}

const NARRATIVE_OVERRIDES_KEY = "workflow.narrative.overrides.v1"
const WORKFLOW_NAME_OVERRIDES_KEY = "workflow.name.overrides.v1"
const COMPLETED_AUTOMATIONS_KEY = "workflow.automation.completed.v1"

function loadNarrativeOverrides() {
  try {
    const raw = window.localStorage.getItem(NARRATIVE_OVERRIDES_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === "object" ? parsed : {}
  } catch {
    return {}
  }
}

function persistNarrativeOverrides(overrides) {
  try {
    window.localStorage.setItem(NARRATIVE_OVERRIDES_KEY, JSON.stringify(overrides || {}))
  } catch {
    // Ignore storage failures in restricted browser contexts.
  }
}

function loadWorkflowNameOverrides() {
  try {
    const raw = window.localStorage.getItem(WORKFLOW_NAME_OVERRIDES_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === "object" ? parsed : {}
  } catch {
    return {}
  }
}

function persistWorkflowNameOverrides(overrides) {
  try {
    window.localStorage.setItem(WORKFLOW_NAME_OVERRIDES_KEY, JSON.stringify(overrides || {}))
  } catch {
    // Ignore storage failures in restricted browser contexts.
  }
}

function loadCompletedAutomations() {
  try {
    const raw = window.localStorage.getItem(COMPLETED_AUTOMATIONS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === "object" ? parsed : {}
  } catch {
    return {}
  }
}

function persistCompletedAutomations(completedAutomations) {
  try {
    window.localStorage.setItem(COMPLETED_AUTOMATIONS_KEY, JSON.stringify(completedAutomations || {}))
  } catch {
    // Ignore storage failures in restricted browser contexts.
  }
}

const state = {
  activeTab: "overview",
  days: 7,
  selectedMonthKey: "",
  payload: null,
  loading: false,
  search: "",
  selectedWorkflowId: "",
  detailOpen: false,
  approvedWorkflowIds: {},
  workflowNarratives: {},
  narrativeSources: {},
  workflowNarrativeConfidence: {},
  workflowNarrativeEvidence: {},
  loadingNarratives: {},
  narrativeOverrides: loadNarrativeOverrides(),
  workflowNameOverrides: loadWorkflowNameOverrides(),
  editingWorkflowNameId: "",
  workflowNameDraft: "",
  editingNarrativeWorkflowId: "",
  narrativeDraftText: "",
  automationDrafts: {},
  automationDraftSources: {},
  loadingAutomationDrafts: {},
  signedAutomationIds: {},
  currentAutomationWorkflowId: "",
  selectedDayIndex: new Date().getDay() === 0 ? 6 : new Date().getDay() - 1,
  pendingReload: false,
  processMapEditing: false,
  processMapEditText: "",
  processMapUpdating: false,
  promptEditing: false,
  promptEditText: "",
  completedAutomations: loadCompletedAutomations(),
  toolUsageRows: [],
  toolAnalysisPopupOpen: false,
}

const els = {
  tabButtons: [...document.querySelectorAll(".tab-btn")],
  panels: {
    overview: document.getElementById("overviewTab"),
    claude: document.getElementById("claudeTab"),
  },
  statusLine: document.getElementById("statusLine"),
  searchInput: document.getElementById("searchInput"),
  daysSelect: document.getElementById("days"),
  monthSelect: document.getElementById("monthFilter"),
  refreshBtn: document.getElementById("refreshBtn"),
  performanceHeading: document.getElementById("performanceHeading"),
  performanceLegend: document.getElementById("performanceLegend"),
  distributionHeading: document.getElementById("distributionHeading"),
  distributionSub: document.getElementById("distributionSub"),
  performanceModule: document.querySelector("#overviewTab .performance-module"),
  toolAnalysisModule: document.querySelector("#overviewTab .tool-analysis-module"),
  daySelector: document.getElementById("daySelector"),
  ledgerChart: document.getElementById("ledgerChart"),
  workflowCards: document.getElementById("workflowCards"),
  toolAnalysisPopupOverlay: document.getElementById("toolAnalysisPopupOverlay"),
  toolAnalysisPopup: document.getElementById("toolAnalysisPopup"),
  closeToolAnalysisPopupBtn: document.getElementById("closeToolAnalysisPopupBtn"),
  toolPopupHeading: document.getElementById("toolPopupHeading"),
  toolPopupSub: document.getElementById("toolPopupSub"),
  toolPopupCards: document.getElementById("toolPopupCards"),
  workflowRows: document.getElementById("workflowRows"),
  detailPanel: document.getElementById("detailPanel"),
  sourceRows: document.getElementById("sourceRows"),
  automationIdeas: document.getElementById("automationIdeas"),
  completedAutomations: document.getElementById("completedAutomations"),
  emptyWorkflowRow: document.getElementById("emptyWorkflowRow"),
  postitPanel: document.getElementById("postitPanel"),
  draftingState: document.getElementById("draftingState"),
  postitTiles: document.getElementById("postitTiles"),
  processMapTile: document.getElementById("processMapTile"),
  editProcessMapBtn: document.getElementById("editProcessMapBtn"),
  processMapEditWrap: document.getElementById("processMapEditWrap"),
  processMapEditInput: document.getElementById("processMapEditInput"),
  applyProcessMapEditBtn: document.getElementById("applyProcessMapEditBtn"),
  cancelProcessMapEditBtn: document.getElementById("cancelProcessMapEditBtn"),
  editPromptBtn: document.getElementById("editPromptBtn"),
  copyPromptBtn: document.getElementById("copyPromptBtn"),
  promptEditWrap: document.getElementById("promptEditWrap"),
  promptEditInput: document.getElementById("promptEditInput"),
  savePromptEditBtn: document.getElementById("savePromptEditBtn"),
  cancelPromptEditBtn: document.getElementById("cancelPromptEditBtn"),
  llmPromptTile: document.getElementById("llmPromptTile"),
  postitMeta: document.getElementById("postitMeta"),
  closePostitBtn: document.getElementById("closePostitBtn"),
  reviewSignBtn: document.getElementById("reviewSignBtn"),
  executeBtn: document.getElementById("executeBtn"),
  postitSignature: document.getElementById("postitSignature"),
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
}

if (typeof window !== "undefined" && typeof window.__workflowLogoError !== "function") {
  window.__workflowLogoError = (img) => {
    try {
      const encoded = String(img?.dataset?.logoCandidates || "")
      const decoded = encoded ? decodeURIComponent(encoded) : ""
      const candidates = decoded
        .split("|")
        .map((row) => String(row || "").trim())
        .filter(Boolean)
      const currentIndex = Math.max(0, Number.parseInt(String(img?.dataset?.logoIndex || "0"), 10) || 0)
      const nextIndex = currentIndex + 1
      if (nextIndex < candidates.length) {
        img.dataset.logoIndex = String(nextIndex)
        img.src = candidates[nextIndex]
        return
      }
    } catch {
      // Fall through to fallback badge.
    }
    img.style.display = "none"
    const fallback = img.nextElementSibling
    if (fallback) fallback.style.display = "inline-grid"
  }
}

function toNumber(value, fallback = 0) {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function fmtInt(value) {
  return Math.round(toNumber(value, 0)).toLocaleString()
}

function fmtOne(value) {
  return toNumber(value, 0).toFixed(1)
}

async function copyTextToClipboard(text) {
  const value = String(text || "")
  if (!value.trim()) return false
  if (navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value)
      return true
    } catch {
      // Fall through to legacy copy path.
    }
  }
  try {
    const textarea = document.createElement("textarea")
    textarea.value = value
    textarea.setAttribute("readonly", "readonly")
    textarea.style.position = "fixed"
    textarea.style.opacity = "0"
    textarea.style.pointerEvents = "none"
    document.body.appendChild(textarea)
    textarea.select()
    textarea.setSelectionRange(0, textarea.value.length)
    const copied = document.execCommand("copy")
    document.body.removeChild(textarea)
    return Boolean(copied)
  } catch {
    return false
  }
}

function setStatus(text, isError = false) {
  els.statusLine.textContent = text
  els.statusLine.style.color = isError ? "#b42020" : "#4c4a43"
}

function timeframeMeta(days) {
  const d = toNumber(days, 7)
  if (d >= 90) {
    return {
      performanceHeading: "Quarterly Performance",
      distributionHeading: "Quarter Tool Analysis",
      periodWord: "quarter",
    }
  }
  if (d >= 30) {
    return {
      performanceHeading: "Monthly Performance",
      distributionHeading: "Month Tool Analysis",
      periodWord: "month",
    }
  }
  return {
    performanceHeading: "Weekly Performance",
    distributionHeading: "Week Tool Analysis",
    periodWord: "week",
  }
}

function distributionSubText(days) {
  const d = toNumber(days, 7)
  if (d >= 90) return "Breakdown of time spent in each tool across the last 90 days."
  if (d >= 30) return "Breakdown of time spent in each tool across the last 30 days."
  return "Breakdown of time spent in each tool across the last 7 days."
}

function updateTimeframeHeadings() {
  const meta = timeframeMeta(state.days)
  if (els.performanceHeading) els.performanceHeading.textContent = meta.performanceHeading
  if (els.distributionHeading) els.distributionHeading.textContent = meta.distributionHeading
  if (els.distributionSub) els.distributionSub.textContent = distributionSubText(state.days)
  if (els.toolPopupHeading) els.toolPopupHeading.textContent = meta.distributionHeading
  if (els.toolPopupSub) els.toolPopupSub.textContent = distributionSubText(state.days)
}

function renderPerformanceLegend() {
  if (!els.performanceLegend) return
  const items = Object.entries(CATEGORY_META)
    .map(
      ([key, meta]) => `
      <span class="legend-item">
        <span class="legend-swatch pattern-${escapeHtml(meta.pattern)}"></span>
        <span>${escapeHtml(meta.label)}</span>
      </span>`,
    )
    .join("")
  els.performanceLegend.innerHTML = `
    ${items}
    <span class="legend-item">
      <span class="legend-swatch legend-ghost"></span>
      <span>Previous period (ghost)</span>
    </span>
  `
}

function workflowType(workflow) {
  const category = String(workflow?.category || "").toLowerCase()
  const tools = Array.isArray(workflow?.tools) ? workflow.tools.map((tool) => String(tool).toLowerCase()) : []
  const text = `${category} ${tools.join(" ")} ${(workflow?.details || "").toLowerCase()}`
  if (/(meeting|zoom|teams|calendar|call)/.test(text)) return "meetings"
  if (/(admin|mail|gmail|slack|ops|excel|sheet|airtable|notion|google_docs|docs|salesforce|hubspot|linkedin)/.test(text))
    return "admin"
  if (/(creative|design|figma|canva|draft|write|powerpoint|slides|granola)/.test(text)) return "creative"
  return "deep"
}

function workflowDurationMinutes(workflow) {
  const runs = toNumber(workflow?.frequency?.runs_total, 0)
  const steps = Math.max(1, (workflow?.steps || []).length)
  return Math.max(5, Math.round(runs * steps * 2.8))
}

function frictionRaw(workflow) {
  const runs = toNumber(workflow?.frequency?.runs_total, 0)
  const tools = Math.max(1, (workflow?.tools || []).length)
  const steps = Math.max(1, (workflow?.steps || []).length)
  return runs * steps * 2 + tools * 4 + workflowDurationMinutes(workflow) * 0.2
}

function workflowActionFrequencyText(workflow) {
  const runs = Math.max(0, toNumber(workflow?.frequency?.runs_total, 0))
  const sessions = Math.max(0, toNumber(workflow?.frequency?.sessions, 0))
  const steps = Math.max(1, Array.isArray(workflow?.steps) ? workflow.steps.length : 0)
  return `${fmtInt(runs)}x runs / ${fmtInt(sessions)} sessions / ${fmtInt(steps)} steps`
}

function derivedWorkflows(payload) {
  const raw = Array.isArray(payload?.workflows) ? payload.workflows : []
  const rows = raw.map((workflow) => {
    const workflowId = String(workflow?.id || "").trim()
    const baseName = String(workflow?.name || "Workflow")
    const overrideName = String(state.workflowNameOverrides?.[workflowId] || "").trim()
    return {
      ...workflow,
      name: overrideName || baseName,
      _baseName: baseName,
      typeKey: workflowType(workflow),
      durationMinutes: workflowDurationMinutes(workflow),
      frictionRaw: frictionRaw(workflow),
    }
  })
  const maxScore = Math.max(...rows.map((row) => row.frictionRaw), 0)
  return rows
    .map((row) => ({
      ...row,
      frictionScore: maxScore <= 0 ? 0 : Math.max(6, Math.round((row.frictionRaw / maxScore) * 100)),
      actionFrequency: workflowActionFrequencyText(row),
    }))
    .sort((a, b) => b.frictionScore - a.frictionScore)
}

function filteredWorkflows(workflows) {
  const term = state.search.trim().toLowerCase()
  if (!term) return workflows
  return workflows.filter((workflow) => {
    const hay = [
      workflow?.name,
      workflow?.details,
      workflow?.category,
      ...(workflow?.tools || []),
      ...((workflow?.steps || []).map((step) => step?.action || "")),
    ]
      .join(" ")
      .toLowerCase()
    return hay.includes(term)
  })
}

function titleCase(value) {
  return String(value || "")
    .split(/[\s._-]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1).toLowerCase())
    .join(" ")
}

function normalizeWorkflowName(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/\b(workflow|flow)\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
}

function sanitizeWorkflowDisplayName(value) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, 120)
}

function automationGroupKey(workflow) {
  const canonicalName = workflow?._baseName || workflow?.name || workflow?.workflow_name || "workflow"
  const nameKey = normalizeWorkflowName(canonicalName)
  const categoryKey = String(workflow?.category || workflow?.typeKey || "general")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
  const toolKey = (Array.isArray(workflow?.tools) ? workflow.tools : [])
    .map((tool) => String(tool || "").toLowerCase().replace(/[^a-z0-9]+/g, ""))
    .filter(Boolean)
    .sort()
    .join("_")
  return `${nameKey || "workflow"}|${categoryKey || "general"}|${toolKey || "tools"}`
}

function isWorkflowCompleted(workflow) {
  if (!workflow) return false
  const key = automationGroupKey(workflow)
  return Boolean(state.completedAutomations[key])
}

function groupAutomationCandidates(payload) {
  const groups = new Map()
  const workflows = derivedWorkflows(payload || {})
  for (const workflow of workflows) {
    const key = automationGroupKey(workflow)
    const existing = groups.get(key)
    const savings = estimateWorkflowTimeSavings(workflow)
    const runsTotal = toNumber(workflow?.frequency?.runs_total, 0)
    const lastSeenMs = parseLastSeen(workflow).getTime()
    if (!existing) {
      groups.set(key, {
        key,
        name: String(workflow?.name || "Workflow"),
        category: String(workflow?.category || workflow?.typeKey || "general"),
        workflowIds: new Set([String(workflow?.id || "")]),
        tools: new Set(Array.isArray(workflow?.tools) ? workflow.tools.map((tool) => titleCase(tool)) : []),
        runsTotal,
        hoursSavedPerWeek: toNumber(savings.hoursPerWeek, 0),
        lastSeenMs,
      })
      continue
    }
    existing.workflowIds.add(String(workflow?.id || ""))
    if (Array.isArray(workflow?.tools)) {
      for (const tool of workflow.tools) existing.tools.add(titleCase(tool))
    }
    existing.runsTotal += runsTotal
    existing.hoursSavedPerWeek += toNumber(savings.hoursPerWeek, 0)
    existing.lastSeenMs = Math.max(existing.lastSeenMs, lastSeenMs)
  }
  return [...groups.values()]
    .map((group) => ({
      key: group.key,
      name: group.name,
      category: group.category,
      workflowIds: [...group.workflowIds].filter(Boolean),
      tools: [...group.tools].filter(Boolean),
      runsTotal: group.runsTotal,
      hoursSavedPerWeek: group.hoursSavedPerWeek,
      lastSeenMs: group.lastSeenMs,
    }))
    .sort(
      (a, b) =>
        toNumber(b.hoursSavedPerWeek, 0) - toNumber(a.hoursSavedPerWeek, 0) ||
        toNumber(b.runsTotal, 0) - toNumber(a.runsTotal, 0) ||
        toNumber(b.lastSeenMs, 0) - toNumber(a.lastSeenMs, 0),
    )
}

function formatCompletedAt(rawValue) {
  const raw = String(rawValue || "").trim()
  const parsed = raw ? new Date(raw) : null
  if (!parsed || Number.isNaN(parsed.getTime())) return "recently"
  return parsed.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

function sentenceClamp(text, maxChars = 180) {
  const compact = String(text || "").replace(/\s+/g, " ").trim()
  if (!compact) return ""
  if (compact.length <= maxChars) return compact
  return `${compact.slice(0, Math.max(0, maxChars - 1)).trimEnd()}...`
}

function firstSentence(text) {
  const compact = String(text || "").replace(/\s+/g, " ").trim()
  if (!compact) return ""
  const match = compact.match(/^(.+?[.!?])(?:\s|$)/)
  return match?.[1] || compact
}

function workflowOneLiner(workflow) {
  const details = sentenceClamp(firstSentence(workflow?.details || ""), 180)
  if (details) return details
  const tools = Array.isArray(workflow?.tools) ? workflow.tools.map((tool) => titleCase(tool)).filter(Boolean) : []
  const toolsText = tools.length ? tools.slice(0, 3).join(", ") : "your core tools"
  const category = String(workflow?.category || workflow?.typeKey || "general").replace(/[_-]+/g, " ")
  return sentenceClamp(`Repeated ${category} workflow using ${toolsText} with predictable manual handoffs.`, 180)
}

function friendlyToolName(tool) {
  const key = String(tool || "").trim().toLowerCase()
  const map = {
    browser: "web browser",
    codex: "codex",
    claude: "claude",
    google_docs: "Google Docs",
    google_sheets: "Google Sheets",
    google_slides: "Google Slides",
    google_drive: "Google Drive",
    google_calendar: "Google Calendar",
    google_meet: "Google Meet",
    gemini: "Gemini",
    powerpoint: "PowerPoint",
    granola: "Granola",
    linkedin: "LinkedIn",
    salesforce: "Salesforce",
    hubspot: "HubSpot",
    mail: "email",
    gmail: "Gmail",
    sheet: "Google Sheets",
    sheets: "Google Sheets",
    terminal: "terminal",
  }
  return map[key] || titleCase(key || "tool")
}

function inferredIntentFromNarrative(narrativeText) {
  const text = String(narrativeText || "").trim()
  if (!text) return ""
  const matchA = text.match(/suggesting intent around ([^.]+)\.?/i)
  if (matchA?.[1]) return String(matchA[1]).trim()
  const matchB = text.match(/likely intent:\s*([^.]+)\.?/i)
  if (matchB?.[1]) return String(matchB[1]).trim()
  return ""
}

function automationInsightText(workflow, narrativeText) {
  const tools = Array.isArray(workflow?.tools) ? workflow.tools.slice(0, 2).map((tool) => friendlyToolName(tool)).filter(Boolean) : []
  const toolPair =
    tools.length >= 2 ? `${tools[0]} and ${tools[1]}` : tools.length === 1 ? tools[0] : "your core tools"
  const intent = inferredIntentFromNarrative(narrativeText)
  if (intent) {
    return `This workflow appears focused on ${intent}; automate the recurring handoff between ${toolPair} by capturing key outputs and writing them into a structured running log with next actions.`
  }
  return `Automate the recurring handoff between ${toolPair} by capturing key outputs and writing them into a structured running log with next actions.`
}

function formatClockTime(dateObj) {
  const d = dateObj instanceof Date ? dateObj : new Date()
  let hour = d.getHours()
  const minute = String(d.getMinutes()).padStart(2, "0")
  const suffix = hour >= 12 ? "PM" : "AM"
  hour = hour % 12 || 12
  return `${hour}:${minute} ${suffix}`
}

function parseLastSeen(workflow) {
  const raw = String(workflow?.frequency?.last_seen || "").trim()
  const parsed = raw ? new Date(raw) : new Date()
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed
}

function toolPatternForName(tool, typeKey) {
  const t = String(tool || "").toLowerCase()
  if (/(gmail|mail|slack|admin|outlook|google docs|google_docs|linkedin|salesforce|hubspot)/.test(t)) return "solid"
  if (/(sheet|excel|table|report|sql|python|deep|gemini|google sheets|google_sheets)/.test(t)) return "hatch"
  if (/(figma|canva|creative|design|draft|powerpoint|slides|granola)/.test(t)) return "dots"
  if (/(zoom|meet|calendar|meeting|teams)/.test(t)) return "wash"
  return CATEGORY_META[typeKey]?.pattern || "solid"
}

function sanitizeLogoDomain(value) {
  const raw = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .split(/[/?#\s]/)[0]
  if (!raw) return ""
  if (!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(raw)) return ""
  return raw
}

function logoCandidatesFromUrls(urls) {
  const unique = []
  const seen = new Set()
  for (const url of urls || []) {
    const value = String(url || "").trim()
    if (!value) continue
    if (seen.has(value)) continue
    seen.add(value)
    unique.push(value)
  }
  return unique
}

function googleFaviconUrl(domain) {
  const clean = sanitizeLogoDomain(domain)
  if (!clean) return ""
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(clean)}&sz=64`
}

function logoImageMarkup(logo) {
  if (!logo?.src) return ""
  const candidates = Array.isArray(logo?.candidates) ? logo.candidates : []
  const encodedCandidates = candidates.length ? encodeURIComponent(candidates.join("|")) : ""
  return `<img class="tool-logo" src="${escapeHtml(logo.src)}" alt="${escapeHtml(logo.label)} logo" loading="lazy" referrerpolicy="no-referrer"${encodedCandidates ? ` data-logo-candidates="${escapeHtml(encodedCandidates)}" data-logo-index="0"` : ""} onerror="window.__workflowLogoError && window.__workflowLogoError(this)" />`
}

function toolLogoMeta(toolName) {
  const raw = String(toolName || "").trim()
  const t = raw.toLowerCase()
  const browserDomain = sanitizeLogoDomain(t.replace(/^browser:\s*/i, ""))
  const compose = (label, urls) => {
    const candidates = logoCandidatesFromUrls(urls)
    return {
      src: candidates[0] || "",
      candidates,
      label,
      fallback: label.slice(0, 1).toUpperCase() || "?",
    }
  }
  const pickSimple = (slug, label = raw, domain = "") =>
    compose(label, [`https://cdn.simpleicons.org/${slug}/0A0A0A`, googleFaviconUrl(domain)])
  const pickDomain = (domain, label = raw) => compose(label, [googleFaviconUrl(domain)])

  if (browserDomain) return pickDomain(browserDomain, `Browser: ${browserDomain}`)
  if (sanitizeLogoDomain(t)) return pickDomain(t, raw)

  if (/zoom/.test(t)) return pickSimple("zoom", "Zoom", "zoom.us")
  if (/slack/.test(t)) return pickSimple("slack", "Slack", "slack.com")
  if (/gmail/.test(t)) return pickSimple("gmail", "Gmail", "mail.google.com")
  if (/outlook/.test(t)) return pickSimple("microsoftoutlook", "Outlook", "outlook.com")
  if (/mail/.test(t)) return pickSimple("gmail", "Mail", "mail.google.com")
  if (/(google docs|google_docs|\bdocs\b)/.test(t)) return pickSimple("googledocs", "Google Docs", "docs.google.com")
  if (/(sheet|sheets|google sheets)/.test(t)) return pickSimple("googlesheets", "Google Sheets", "docs.google.com")
  if (/(google slides|google_slides|slides)/.test(t)) return pickSimple("googleslides", "Google Slides", "slides.google.com")
  if (/(google drive|google_drive|drive)/.test(t)) return pickSimple("googledrive", "Google Drive", "drive.google.com")
  if (/(gemini)/.test(t)) return pickSimple("googlegemini", "Gemini", "gemini.google.com")
  if (/excel/.test(t)) return pickSimple("microsoftexcel", "Excel", "office.com")
  if (/powerpoint/.test(t)) return pickSimple("microsoftpowerpoint", "PowerPoint", "powerpoint.office.com")
  if (/granola/.test(t)) return pickSimple("granola", "Granola", "granola.ai")
  if (/linkedin/.test(t)) return pickSimple("linkedin", "LinkedIn", "linkedin.com")
  if (/salesforce/.test(t)) return pickSimple("salesforce", "Salesforce", "salesforce.com")
  if (/hubspot/.test(t)) return pickSimple("hubspot", "HubSpot", "hubspot.com")
  if (/notion/.test(t)) return pickSimple("notion", "Notion", "notion.so")
  if (/figma/.test(t)) return pickSimple("figma", "Figma", "figma.com")
  if (/canva/.test(t)) return pickSimple("canva", "Canva", "canva.com")
  if (/teams/.test(t)) return pickSimple("microsoftteams", "Teams", "teams.microsoft.com")
  if (/calendar/.test(t)) return pickSimple("googlecalendar", "Calendar", "calendar.google.com")
  if (/airtable/.test(t)) return pickSimple("airtable", "Airtable", "airtable.com")
  if (/chrome|browser|web/.test(t)) return pickSimple("googlechrome", "Chrome", "google.com")
  if (/safari/.test(t)) return pickSimple("safari", "Safari", "apple.com")
  if (/arc/.test(t)) return pickSimple("arc", "Arc", "arc.net")
  if (/claude|anthropic/.test(t)) return pickSimple("anthropic", "Claude", "anthropic.com")
  if (/openai|codex|chatgpt/.test(t)) return pickDomain("openai.com", "OpenAI")
  if (/github/.test(t)) return pickSimple("github", "GitHub", "github.com")
  if (/git/.test(t)) return pickSimple("git", "Git", "git-scm.com")
  if (/python/.test(t)) return pickSimple("python", "Python", "python.org")
  if (/terminal/.test(t)) return pickSimple("gnubash", "Terminal", "gnu.org")

  const token = String(t || "")
    .replace(/^browser:\s*/i, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .split(/\s+/)[0]
  const guessedDomains = token
    ? [`${token}.com`, `${token}.io`, `${token}.ai`, `${token}.app`]
    : []
  const guessedCandidates = guessedDomains.map((domain) => googleFaviconUrl(domain))
  return compose(raw || "Tool", guessedCandidates)
}

function deriveToolBreakdown(workflow) {
  const tools = Array.isArray(workflow?.tools) && workflow.tools.length ? workflow.tools : [workflow?.typeKey || "workflow"]
  const total = Math.max(5, workflow?.durationMinutes || 5)
  const weights = tools.map((_, idx) => Math.max(0.7, 1.45 - idx * 0.24))
  const weightTotal = weights.reduce((sum, row) => sum + row, 0)
  let remaining = total
  const rows = tools.map((tool, idx) => {
    let minutes = Math.round((weights[idx] / weightTotal) * total)
    if (idx === tools.length - 1) minutes = Math.max(1, remaining)
    remaining -= minutes
    return {
      tool: titleCase(tool),
      minutes,
      pattern: toolPatternForName(tool, workflow?.typeKey),
    }
  })

  const steps = Array.isArray(workflow?.steps) ? workflow.steps : []
  const siteCounts = new Map()
  for (const step of steps) {
    const action = String(step?.action || "").trim()
    const match = action.match(/^browser\s+visit\s+(.+)$/i)
    if (!match?.[1]) continue
    const rawSite = String(match[1]).trim()
    if (!rawSite) continue
    let site = rawSite
      .replace(/^https?:\/\//i, "")
      .replace(/^www\./i, "")
      .split(/[/?#\s]/)[0]
      .trim()
      .toLowerCase()
    if (!site) site = rawSite.toLowerCase()
    siteCounts.set(site, (siteCounts.get(site) || 0) + 1)
  }

  if (!siteCounts.size) return rows

  const browserRowIdx = rows.findIndex((row) => /(^browser$|web browser|chrome|safari|arc)/i.test(String(row.tool || "")))
  if (browserRowIdx < 0) return rows

  const browserRow = rows[browserRowIdx]
  const browserMinutes = Math.max(1, toNumber(browserRow.minutes, 0))
  const siteEntries = [...siteCounts.entries()].sort((a, b) => b[1] - a[1])
  const totalVisits = Math.max(1, siteEntries.reduce((sum, entry) => sum + toNumber(entry[1], 0), 0))
  let browserRemaining = browserMinutes

  const siteRows = siteEntries.map(([site, count], idx) => {
    const slotsLeft = siteEntries.length - idx
    let minutes =
      idx === siteEntries.length - 1
        ? browserRemaining
        : Math.round((browserMinutes * toNumber(count, 0)) / totalVisits)
    minutes = Math.max(1, Math.min(minutes, Math.max(1, browserRemaining - (slotsLeft - 1))))
    browserRemaining -= minutes
    return {
      tool: `Browser: ${site}`,
      minutes,
      pattern: browserRow.pattern || toolPatternForName("browser", workflow?.typeKey),
    }
  })

  return [...rows.slice(0, browserRowIdx), ...siteRows, ...rows.slice(browserRowIdx + 1)]
}

function estimateWorkflowTimeSavings(workflow) {
  const perWeek = toNumber(workflow?.frequency?.per_week, 0)
  const steps = Math.max(1, (workflow?.steps || []).length)
  const tools = Math.max(1, (workflow?.tools || []).length)
  const weeklyManualMinutes = perWeek * (steps * 3 + tools * 1.5)
  const reclaimMinutes = Math.max(0, weeklyManualMinutes * 0.65)
  return {
    hoursPerWeek: reclaimMinutes / 60,
    minutesPerDay: reclaimMinutes / 5,
  }
}

function parseStepPattern(action) {
  const raw = String(action || "").trim()
  if (!raw) {
    return { kind: "unknown", label: "Unknown step", activity: "No step detail available.", confidence: "low", raw: "" }
  }
  const lower = raw.toLowerCase()
  const parts = lower.split(/\s+/)
  const tool = parts[0] || ""
  const verb = parts[1] || ""

  if (lower.startsWith("browser visit ")) {
    const domain = raw.slice("browser visit ".length).trim()
    return {
      kind: "browser_visit",
      label: "Browser Visit",
      activity: domain ? `Visited ${domain} to gather context or evidence.` : "Visited a browser domain to gather context.",
      confidence: "medium",
      raw,
    }
  }
  if (tool === "browser" && verb === "active") {
    return {
      kind: "focus_switch",
      label: "Window Focus",
      activity: "Focused browser window; exact in-page activity is not captured.",
      confidence: "low",
      raw,
    }
  }
  if (tool === "code" && verb === "active") {
    return {
      kind: "focus_switch",
      label: "Window Focus",
      activity: "Focused code editor window; exact edit intent is not captured.",
      confidence: "low",
      raw,
    }
  }
  if (tool === "terminal" && verb === "active") {
    return {
      kind: "focus_switch",
      label: "Window Focus",
      activity: "Focused terminal window; exact command context is not captured.",
      confidence: "low",
      raw,
    }
  }
  if (["pkill", "kill", "killall"].includes(tool)) {
    return {
      kind: "process_stop",
      label: "Process Reset",
      activity: `Stopped a running process (${raw}).`,
      confidence: "high",
      raw,
    }
  }
  if (tool === "sleep") {
    return {
      kind: "wait_poll",
      label: "Wait/Poll",
      activity: `Inserted a wait/poll interval (${raw}).`,
      confidence: "high",
      raw,
    }
  }
  if (["curl", "wget"].includes(tool)) {
    return {
      kind: "endpoint_check",
      label: "Endpoint Check",
      activity: `Queried an endpoint or fetched data (${raw}).`,
      confidence: "high",
      raw,
    }
  }
  if (["python", "python3", "node"].includes(tool)) {
    return {
      kind: "service_run",
      label: "Script/Service Run",
      activity: `Ran local script or service (${raw}).`,
      confidence: "high",
      raw,
    }
  }
  if (["npm", "pnpm", "yarn", "bun"].includes(tool)) {
    if (["test", "lint", "check"].includes(verb)) {
      return {
        kind: "test_run",
        label: "Validation Run",
        activity: `Executed quality or test command (${raw}).`,
        confidence: "high",
        raw,
      }
    }
    return {
      kind: "build_run",
      label: "Build/Run",
      activity: `Executed package task (${raw}).`,
      confidence: "high",
      raw,
    }
  }
  if (tool === "git") {
    const verbMap = {
      status: "Checked repository status.",
      add: "Staged code changes.",
      commit: "Committed a change set.",
      push: "Pushed commits to remote.",
      pull: "Pulled updates from remote.",
      checkout: "Switched branch/context.",
      rebase: "Rebased branch history.",
      merge: "Merged branch changes.",
    }
    return {
      kind: "repo_sync",
      label: "Repository Ops",
      activity: `${verbMap[verb] || "Ran repository command."} (${raw})`,
      confidence: "high",
      raw,
    }
  }
  if (["rg", "grep", "fd", "find"].includes(tool)) {
    return {
      kind: "code_search",
      label: "Search Query",
      activity: `Searched files/content for patterns (${raw}).`,
      confidence: "high",
      raw,
    }
  }
  if (["cat", "less", "head", "tail", "sed", "awk"].includes(tool)) {
    return {
      kind: "file_inspect",
      label: "File Inspect",
      activity: `Inspected file/content output (${raw}).`,
      confidence: "high",
      raw,
    }
  }
  if (["mail", "gmail", "outlook", "slack", "teams"].includes(tool) && verb === "active") {
    return {
      kind: "comm_workspace",
      label: "Communication Workspace",
      activity: `Worked in communication app (${raw}).`,
      confidence: "low",
      raw,
    }
  }
  if (["notion", "sheet", "excel", "airtable"].includes(tool) && verb === "active") {
    return {
      kind: "tracking_workspace",
      label: "Tracker Workspace",
      activity: `Worked in tracker/document app (${raw}).`,
      confidence: "low",
      raw,
    }
  }

  return {
    kind: "generic_command",
    label: "Command Run",
    activity: `Executed command pattern (${raw}).`,
    confidence: "medium",
    raw,
  }
}

function likelyActivityFromPatterns(rows) {
  const kinds = new Set(rows.map((row) => row.kind))
  if (kinds.has("process_stop") && kinds.has("service_run") && kinds.has("endpoint_check")) {
    return "local service restart and endpoint validation loop"
  }
  if ((kinds.has("repo_sync") && kinds.has("test_run")) || (kinds.has("repo_sync") && kinds.has("build_run"))) {
    return "code iteration with repository updates and verification"
  }
  if (kinds.has("comm_workspace") && kinds.has("tracking_workspace")) {
    return "communication-to-tracker handoff activity"
  }
  if ((kinds.has("browser_visit") && kinds.has("code_search")) || (kinds.has("browser_visit") && kinds.has("file_inspect"))) {
    return "research and evidence collection activity"
  }
  if (kinds.size === 1 && kinds.has("focus_switch")) {
    return "window focus switching only; insufficient detail for deeper inference"
  }
  const labels = rows.map((row) => row.label).filter(Boolean)
  return labels.length ? labels.slice(0, 2).join(" + ").toLowerCase() : "repeated command execution"
}

function deriveTimelineEntries(workflow) {
  const steps = Array.isArray(workflow?.steps) ? workflow.steps : []
  const rawActions = steps.map((step) => String(step?.action || "").trim()).filter(Boolean)
  const parsed = rawActions.map((action) => parseStepPattern(action))
  const meaningful = parsed.filter((row) => row.kind !== "focus_switch")
  const rows = (meaningful.length >= 2 ? meaningful : parsed).slice(0, 8)

  if (!rows.length) {
    const seed = parseLastSeen(workflow)
    return {
      entries: [
        {
          time: formatClockTime(seed),
          action: "Not enough detailed step data to infer activity pattern.",
          tag: "Pattern | Insufficient Data",
          note: "Evidence: no normalized workflow steps available.",
        },
      ],
      likelyActivity: "insufficient evidence",
    }
  }

  const total = Math.max(10, workflow?.durationMinutes || 10)
  const seed = parseLastSeen(workflow)
  const start = new Date(seed.getTime() - total * 60_000)
  const interval = Math.max(6, Math.round(total / Math.max(1, rows.length)))
  const likelyActivity = likelyActivityFromPatterns(rows)
  const evidence = rows.slice(0, 4).map((row) => row.raw).join(" -> ")

  const entries = rows.map((row, idx) => {
    const at = new Date(start.getTime() + idx * interval * 60_000)
    return {
      time: formatClockTime(at),
      action: row.activity,
      tag: `Pattern | ${row.label}`,
      note: idx === 0 ? `Evidence: ${evidence}` : idx === 1 ? `Likely activity: ${likelyActivity}` : "",
    }
  })

  return { entries, likelyActivity }
}

function renderTabs() {
  for (const [tab, panel] of Object.entries(els.panels)) {
    if (!panel) continue
    panel.classList.toggle("is-visible", tab === state.activeTab)
  }
  for (const btn of els.tabButtons) {
    btn.classList.toggle("is-active", btn.dataset.tab === state.activeTab)
  }
}

function renderMonthFilter(weekly) {
  if (!els.monthSelect) return
  const monthMode = toNumber(state.days, 7) >= 30 && toNumber(state.days, 7) < 90
  if (!monthMode) {
    els.monthSelect.classList.remove("is-visible")
    els.monthSelect.disabled = true
    els.monthSelect.innerHTML = `<option value="">Select month</option>`
    return
  }
  const currentRows = Array.isArray(weekly?.current_week) ? weekly.current_week : []
  const previousRows = Array.isArray(weekly?.previous_week) ? weekly.previous_week : []
  const monthOptions = monthOptionsFromRows([...currentRows, ...previousRows])
  const selectedMonthKey = ensureSelectedMonthKey(monthOptions)
  if (!monthOptions.length) {
    els.monthSelect.classList.add("is-visible")
    els.monthSelect.disabled = true
    els.monthSelect.innerHTML = `<option value="">No month data</option>`
    return
  }
  els.monthSelect.classList.add("is-visible")
  els.monthSelect.disabled = false
  els.monthSelect.innerHTML = monthOptions
    .map((option) => `<option value="${escapeHtml(option.key)}">${escapeHtml(option.label)}</option>`)
    .join("")
  els.monthSelect.value = selectedMonthKey
}

function renderDaySelector(weekly) {
  const { currentRows: rows, quarterView } = rowsForSelectedTimeline(weekly)
  if (!rows.length) {
    els.daySelector.innerHTML = ""
    return
  }
  const selected = Math.max(0, Math.min(rows.length - 1, state.selectedDayIndex))
  if (selected !== state.selectedDayIndex) state.selectedDayIndex = selected
  if (rows.length <= 10) {
    els.daySelector.style.gridTemplateColumns = `repeat(${rows.length}, minmax(0, 1fr))`
    els.daySelector.style.overflowX = "visible"
  } else {
    els.daySelector.style.gridTemplateColumns = `repeat(${rows.length}, minmax(74px, 74px))`
    els.daySelector.style.overflowX = "auto"
  }
  els.daySelector.innerHTML = rows
    .map(
      (row, idx) => `
      <button class="day-chip ${idx === selected ? "is-selected" : ""}" data-day-index="${idx}" type="button">
        ${escapeHtml(quarterView ? `${String(row.day || "")} (${String(row.period_label || "")})` : row.day)}
      </button>`,
    )
    .join("")
}

function chartFrame() {
  return { left: 52, right: 944, top: 48, bottom: 286 }
}

function dayCenterX(idx, totalSlots = 7) {
  const frame = chartFrame()
  const slot = (frame.right - frame.left) / Math.max(1, totalSlots)
  return frame.left + slot * idx + slot / 2
}

function chartY(maxValue, value) {
  const frame = chartFrame()
  const safeMax = Math.max(1, maxValue)
  return frame.bottom - (value / safeMax) * (frame.bottom - frame.top)
}

function formatDateMMDD(isoDate) {
  const raw = String(isoDate || "").trim()
  if (!raw || !raw.includes("-")) return "--/--"
  const parts = raw.split("-")
  if (parts.length < 3) return "--/--"
  return `${parts[1]}/${parts[2]}`
}

function parseISODateSafe(value) {
  const raw = String(value || "").trim()
  if (!raw) return null
  const parsed = new Date(raw)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const MONTH_LABELS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
const QUARTER_PERIOD_LABELS = ["Jan-Mar", "Apr-Jun", "Jul-Sep", "Oct-Dec"]

function monthKeyFromDate(dateObj) {
  if (!(dateObj instanceof Date) || Number.isNaN(dateObj.getTime())) return ""
  const year = dateObj.getFullYear()
  const month = String(dateObj.getMonth() + 1).padStart(2, "0")
  return `${year}-${month}`
}

function shiftMonthKey(monthKey, delta) {
  const raw = String(monthKey || "").trim()
  const match = raw.match(/^(\d{4})-(\d{2})$/)
  if (!match) return ""
  const year = Number(match[1])
  const month = Number(match[2])
  const base = new Date(year, month - 1 + toNumber(delta, 0), 1)
  return monthKeyFromDate(base)
}

function monthLabelFromKey(monthKey) {
  const raw = String(monthKey || "").trim()
  const match = raw.match(/^(\d{4})-(\d{2})$/)
  if (!match) return "Unknown Month"
  const year = Number(match[1])
  const month = Number(match[2])
  if (!Number.isFinite(year) || !Number.isFinite(month) || month < 1 || month > 12) return "Unknown Month"
  return `${MONTH_LABELS[month - 1]} ${year}`
}

function monthOptionsFromRows(rows) {
  const source = Array.isArray(rows) ? rows : []
  const keys = new Set()
  for (const row of source) {
    const dateObj = parseISODateSafe(row?.date)
    if (!dateObj) continue
    const key = monthKeyFromDate(dateObj)
    if (key) keys.add(key)
  }
  return [...keys]
    .sort((a, b) => b.localeCompare(a))
    .map((key) => ({ key, label: monthLabelFromKey(key) }))
}

function ensureSelectedMonthKey(monthOptions) {
  const options = Array.isArray(monthOptions) ? monthOptions : []
  const validKeys = new Set(options.map((option) => String(option?.key || "")))
  const currentKey = String(state.selectedMonthKey || "").trim()
  if (currentKey && validKeys.has(currentKey)) return currentKey
  state.selectedMonthKey = options[0]?.key || ""
  return state.selectedMonthKey
}

function emptyMonthWeekRow(idx, monthKey) {
  return {
    day: `Week ${idx + 1}`,
    period_label: monthLabelFromKey(monthKey),
    date: "",
    admin: 0,
    deep: 0,
    creative: 0,
    meetings: 0,
    total: 0,
    friction_score: 0,
  }
}

function emptyQuarterRow(idx) {
  return {
    day: `Q${idx + 1}`,
    period_label: QUARTER_PERIOD_LABELS[idx] || "",
    date: "",
    admin: 0,
    deep: 0,
    creative: 0,
    meetings: 0,
    total: 0,
    friction_score: 0,
  }
}

function rowsToQuarterBuckets(rows) {
  const source = Array.isArray(rows) ? rows : []
  const buckets = Array.from({ length: 4 }, (_, idx) => emptyQuarterRow(idx))
  const frictionWeighted = [0, 0, 0, 0]
  const frictionWeightTotal = [0, 0, 0, 0]

  for (const row of source) {
    const dateObj = parseISODateSafe(row?.date)
    const quarterIdx = dateObj ? Math.floor(dateObj.getMonth() / 3) : null
    if (quarterIdx === null || quarterIdx < 0 || quarterIdx > 3) continue
    const bucket = buckets[quarterIdx]
    const admin = toNumber(row?.admin, 0)
    const deep = toNumber(row?.deep, 0)
    const creative = toNumber(row?.creative, 0)
    const meetings = toNumber(row?.meetings, 0)
    const derivedTotal = admin + deep + creative + meetings
    const total = Math.max(0, toNumber(row?.total, derivedTotal))
    const friction = Math.max(0, Math.min(100, toNumber(row?.friction_score, 0)))
    bucket.admin += admin
    bucket.deep += deep
    bucket.creative += creative
    bucket.meetings += meetings
    bucket.total += total
    frictionWeighted[quarterIdx] += friction * Math.max(1, total)
    frictionWeightTotal[quarterIdx] += Math.max(1, total)
  }

  for (let idx = 0; idx < buckets.length; idx += 1) {
    const weight = frictionWeightTotal[idx]
    const bucket = buckets[idx]
    bucket.admin = Math.round(bucket.admin)
    bucket.deep = Math.round(bucket.deep)
    bucket.creative = Math.round(bucket.creative)
    bucket.meetings = Math.round(bucket.meetings)
    bucket.total = Math.round(bucket.total)
    bucket.friction_score = weight > 0 ? Math.round(frictionWeighted[idx] / weight) : 0
  }

  return buckets
}

function rowsToMonthWeekBuckets(rows, monthKey) {
  const source = Array.isArray(rows) ? rows : []
  const buckets = Array.from({ length: 4 }, (_, idx) => emptyMonthWeekRow(idx, monthKey))
  const frictionWeighted = [0, 0, 0, 0]
  const frictionWeightTotal = [0, 0, 0, 0]

  for (const row of source) {
    const dateObj = parseISODateSafe(row?.date)
    if (!dateObj) continue
    if (monthKeyFromDate(dateObj) !== monthKey) continue
    const weekIdx = Math.max(0, Math.min(3, Math.floor((dateObj.getDate() - 1) / 7)))
    const bucket = buckets[weekIdx]
    const admin = toNumber(row?.admin, 0)
    const deep = toNumber(row?.deep, 0)
    const creative = toNumber(row?.creative, 0)
    const meetings = toNumber(row?.meetings, 0)
    const derivedTotal = admin + deep + creative + meetings
    const total = Math.max(0, toNumber(row?.total, derivedTotal))
    const friction = Math.max(0, Math.min(100, toNumber(row?.friction_score, 0)))
    bucket.admin += admin
    bucket.deep += deep
    bucket.creative += creative
    bucket.meetings += meetings
    bucket.total += total
    frictionWeighted[weekIdx] += friction * Math.max(1, total)
    frictionWeightTotal[weekIdx] += Math.max(1, total)
  }

  for (let idx = 0; idx < buckets.length; idx += 1) {
    const bucket = buckets[idx]
    const weight = frictionWeightTotal[idx]
    bucket.admin = Math.round(bucket.admin)
    bucket.deep = Math.round(bucket.deep)
    bucket.creative = Math.round(bucket.creative)
    bucket.meetings = Math.round(bucket.meetings)
    bucket.total = Math.round(bucket.total)
    bucket.friction_score = weight > 0 ? Math.round(frictionWeighted[idx] / weight) : 0
  }

  return buckets
}

function rowsForSelectedTimeline(weekly) {
  const currentRows = Array.isArray(weekly?.current_week) ? weekly.current_week : []
  const previousRows = Array.isArray(weekly?.previous_week) ? weekly.previous_week : []
  const days = toNumber(state.days, 7)
  const quarterView = days >= 90
  if (quarterView) {
    return {
      currentRows: rowsToQuarterBuckets(currentRows),
      previousRows: rowsToQuarterBuckets(previousRows),
      quarterView: true,
      monthView: false,
      monthOptions: [],
    }
  }
  const monthView = days >= 30
  if (!monthView) return { currentRows, previousRows, quarterView: false, monthView: false, monthOptions: [] }
  const monthOptions = monthOptionsFromRows([...currentRows, ...previousRows])
  const selectedMonthKey = ensureSelectedMonthKey(monthOptions)
  const previousMonthKey = shiftMonthKey(selectedMonthKey, -1)
  const previousMonthAvailable = monthOptions.some((option) => String(option.key || "") === previousMonthKey)
  const previousGhostMonth = previousMonthAvailable ? previousMonthKey : selectedMonthKey
  return {
    currentRows: rowsToMonthWeekBuckets(currentRows, selectedMonthKey),
    previousRows: rowsToMonthWeekBuckets(previousRows, previousGhostMonth),
    quarterView: false,
    monthView: true,
    monthOptions,
  }
}

function svgNode(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag)
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, String(value))
  }
  return node
}

function ensureChartPatterns(svg) {
  const defs = svgNode("defs")
  const hatch = svgNode("pattern", { id: "bar-hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" })
  hatch.appendChild(svgNode("rect", { x: 0, y: 0, width: 6, height: 6, fill: "#FDECB2" }))
  hatch.appendChild(svgNode("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: "#5E4A10", "stroke-width": 1 }))
  defs.appendChild(hatch)

  const dots = svgNode("pattern", { id: "bar-dots", width: 6, height: 6, patternUnits: "userSpaceOnUse" })
  dots.appendChild(svgNode("rect", { x: 0, y: 0, width: 6, height: 6, fill: "#FFD7E6" }))
  dots.appendChild(svgNode("circle", { cx: 2, cy: 2, r: 1, fill: "#8A2E5A" }))
  defs.appendChild(dots)
  svg.appendChild(defs)
}

function barFill(pattern) {
  if (pattern === "hatch") return "url(#bar-hatch)"
  if (pattern === "dots") return "url(#bar-dots)"
  if (pattern === "wash") return "#CBE0F8"
  return "#F7C7A3"
}

function drawChartAxis(svg, totalSlots) {
  const frame = chartFrame()
  svg.appendChild(svgNode("line", { x1: frame.left, y1: frame.bottom, x2: frame.right, y2: frame.bottom, stroke: "#0A0A0A", "stroke-width": 1 }))

  for (let idx = 0; idx < totalSlots; idx += 1) {
    const x = dayCenterX(idx, totalSlots)
    svg.appendChild(svgNode("line", { x1: x, y1: frame.bottom, x2: x, y2: frame.bottom + 6, stroke: "#0A0A0A", "stroke-width": 1 }))
  }
}

function drawTargetLine(svg, maxValue, targetMinutes) {
  const frame = chartFrame()
  const y = chartY(maxValue, targetMinutes)
  svg.appendChild(
    svgNode("line", {
      x1: frame.left,
      y1: y,
      x2: frame.right,
      y2: y,
      stroke: "#9E9E9E",
      "stroke-width": 1,
      "stroke-dasharray": "5 5",
    }),
  )
  const label = svgNode("text", {
    x: frame.left + 6,
    y: y - 4,
    fill: "#7D7D7D",
    "font-size": 10,
    "font-family": "IBM Plex Mono, monospace",
  })
  label.textContent = "Target focus hours"
  svg.appendChild(label)
}

function drawSelectedDayMarker(svg, idx, totalSlots) {
  const frame = chartFrame()
  const slots = Math.max(1, totalSlots)
  const safeIdx = Math.max(0, Math.min(slots - 1, idx))
  const x = dayCenterX(safeIdx, slots)
  const slotWidth = (frame.right - frame.left) / slots
  const rx = Math.max(8, Math.min(24, slotWidth * 0.3))
  svg.appendChild(
    svgNode("ellipse", {
      cx: x,
      cy: frame.bottom + 3,
      rx,
      ry: 10,
      fill: "none",
      stroke: "#0A0A0A",
      "stroke-width": 2,
      transform: `rotate(-4 ${x} ${frame.bottom + 3})`,
    }),
  )
}

function drawDayLabels(svg, currentRows, totalSlots, viewMode = "default") {
  const frame = chartFrame()
  const slots = Math.max(1, totalSlots)
  const quarterView = viewMode === "quarter"
  const monthView = viewMode === "month"
  const dayFontSize = quarterView ? 32 : monthView ? 20 : slots > 24 ? 12 : slots > 14 ? 14 : 24
  const dateFontSize = quarterView ? 12 : monthView ? 0 : slots > 24 ? 9 : 11
  const labelStep = quarterView || monthView ? 1 : slots > 24 ? 5 : slots > 16 ? 3 : slots > 10 ? 2 : 1
  for (let idx = 0; idx < currentRows.length; idx += 1) {
    const shouldDraw = idx % labelStep === 0 || idx === currentRows.length - 1 || idx === state.selectedDayIndex
    if (!shouldDraw) continue
    const row = currentRows[idx]
    const x = dayCenterX(idx, slots)
    const dayText = svgNode("text", {
      x,
      y: 30,
      fill: "#0A0A0A",
      "font-size": dayFontSize,
      "text-anchor": "middle",
      "font-family": "Autography, cursive",
    })
    dayText.textContent = String(row.day || "")
    svg.appendChild(dayText)

    if (monthView) continue

    const dateText = svgNode("text", {
      x,
      y: frame.bottom + 32,
      fill: "#0A0A0A",
      "font-size": dateFontSize,
      "text-anchor": "middle",
      "font-family": "IBM Plex Mono, monospace",
    })
    dateText.textContent = quarterView ? String(row.period_label || "") : formatDateMMDD(row.date)
    svg.appendChild(dateText)
  }
}

function drawFrictionMarker(svg, x, y, isStar, opacity = 1) {
  if (isStar) {
    const star = svgNode("polygon", {
      points: `${x},${y - 8} ${x + 2.8},${y - 2.6} ${x + 8.8},${y - 2.2} ${x + 4.2},${y + 1.8} ${x + 5.8},${y + 7.8} ${x},${y + 4.4} ${x - 5.8},${y + 7.8} ${x - 4.2},${y + 1.8} ${x - 8.8},${y - 2.2} ${x - 2.8},${y - 2.6}`,
      fill: "#0A0A0A",
      opacity,
    })
    svg.appendChild(star)
    return
  }
  const mark = svgNode("text", {
    x,
    y,
    fill: "#0A0A0A",
    "font-size": 16,
    "text-anchor": "middle",
    "font-family": "IBM Plex Mono, monospace",
    opacity,
  })
  mark.textContent = "!"
  svg.appendChild(mark)
}

function drawSelectedAnnotation(svg, selectedIdx, currentRows, barWidth, maxValue, totalSlots) {
  if (selectedIdx < 0 || selectedIdx >= currentRows.length) return
  const frame = chartFrame()
  const row = currentRows[selectedIdx] || {}
  const totalMinutes = toNumber(row.total, 0)
  const totalHours = totalMinutes / 60
  const x = dayCenterX(selectedIdx, totalSlots)
  const yTop = chartY(maxValue, totalMinutes)
  const rightEdge = x + barWidth / 2
  const leftEdge = x - barWidth / 2
  const annotateRight = rightEdge + 10 < frame.right - 130
  const bracketX = annotateRight ? rightEdge + 9 : leftEdge - 9
  const sign = annotateRight ? 1 : -1

  const path = svgNode("path", {
    d: `M ${bracketX} ${yTop} L ${bracketX + sign * 8} ${yTop} L ${bracketX + sign * 8} ${frame.bottom} L ${bracketX} ${frame.bottom}`,
    fill: "none",
    stroke: "#0A0A0A",
    "stroke-width": 2,
  })
  svg.appendChild(path)

  const label = svgNode("text", {
    x: bracketX + sign * 14,
    y: yTop + 16,
    fill: "#0A0A0A",
    "font-size": 24,
    "text-anchor": annotateRight ? "start" : "end",
    "font-family": "Autography, cursive",
  })
  label.textContent = `${fmtOne(totalHours)} hrs total`
  svg.appendChild(label)
}

function periodMixRatios(weekly, categories) {
  const totals = {}
  let sum = 0
  for (const key of categories) {
    const current = toNumber(weekly?.totals?.current_week?.[key], 0)
    const previous = toNumber(weekly?.totals?.previous_week?.[key], 0)
    totals[key] = Math.max(0, current + previous)
    sum += totals[key]
  }
  if (sum <= 0) {
    return { admin: 0.28, deep: 0.42, creative: 0.2, meetings: 0.1 }
  }
  const ratios = {}
  for (const key of categories) {
    ratios[key] = totals[key] / sum
  }
  return ratios
}

function stackedValuesForRow(row, categories, mix) {
  const raw = {}
  let rawSum = 0
  let nonZero = 0
  for (const key of categories) {
    const value = Math.max(0, Math.round(toNumber(row?.[key], 0)))
    raw[key] = value
    rawSum += value
    if (value > 0) nonZero += 1
  }
  const total = Math.max(0, Math.round(toNumber(row?.total, rawSum)))
  if (total <= 0 || nonZero >= 2) return raw

  const values = {}
  let assigned = 0
  const byWeight = [...categories].sort((a, b) => toNumber(mix[b], 0) - toNumber(mix[a], 0))
  for (const key of categories) {
    const base = Math.max(0, Math.floor(total * toNumber(mix[key], 0)))
    values[key] = base
    assigned += base
  }
  let remainder = total - assigned
  let ptr = 0
  while (remainder > 0) {
    values[byWeight[ptr % byWeight.length]] += 1
    remainder -= 1
    ptr += 1
  }

  const dominant = categories.find((key) => raw[key] > 0) || byWeight[0]
  const minDominant = Math.max(raw[dominant] || 0, Math.round(total * 0.4))
  if (values[dominant] < minDominant) {
    let need = minDominant - values[dominant]
    for (const key of byWeight) {
      if (!need) break
      if (key === dominant) continue
      const canMove = Math.max(0, values[key] - (key === byWeight[0] ? 1 : 0))
      if (!canMove) continue
      const move = Math.min(canMove, need)
      values[key] -= move
      values[dominant] += move
      need -= move
    }
  }
  return values
}

function renderLedgerChart(weekly) {
  const { currentRows: current, previousRows: previous, quarterView, monthView } = rowsForSelectedTimeline(weekly)
  const svg = els.ledgerChart
  svg.innerHTML = ""
  if (!current.length || !previous.length) return
  const slots = Math.max(1, Math.min(current.length, previous.length))
  const selectedIdx = Math.max(0, Math.min(slots - 1, state.selectedDayIndex))
  if (selectedIdx !== state.selectedDayIndex) state.selectedDayIndex = selectedIdx

  ensureChartPatterns(svg)

  const categories = ["admin", "deep", "creative", "meetings"]
  const mix = periodMixRatios(weekly, categories)
  const maxValue = Math.max(
    1,
    ...current.map((row) => toNumber(row.total, 0)),
    ...previous.map((row) => toNumber(row.total, 0)),
    toNumber(weekly?.target_focus_minutes, 0),
  )

  const frame = chartFrame()
  const slotWidth = (frame.right - frame.left) / slots
  const barWidth = Math.min(74, slotWidth * 0.7)

  drawChartAxis(svg, slots)
  const viewMode = quarterView ? "quarter" : monthView ? "month" : "default"
  drawDayLabels(svg, current, slots, viewMode)

  for (let dayIdx = 0; dayIdx < slots; dayIdx += 1) {
    const barLeft = dayCenterX(dayIdx, slots) - barWidth / 2
    const currentRow = current[dayIdx] || {}
    const previousRow = previous[dayIdx] || {}
    const currentValues = stackedValuesForRow(currentRow, categories, mix)
    const previousValues = stackedValuesForRow(previousRow, categories, mix)
    let prevCursor = frame.bottom
    let currCursor = frame.bottom
    const currentOpacity = dayIdx === selectedIdx ? 1 : 0.3

    for (const key of categories) {
      const meta = CATEGORY_META[key]
      const prevValue = toNumber(previousValues[key], 0)
      const currValue = toNumber(currentValues[key], 0)
      const prevHeight = Math.max(0, frame.bottom - chartY(maxValue, prevValue))
      const currHeight = Math.max(0, frame.bottom - chartY(maxValue, currValue))

      if (prevHeight > 0) {
        prevCursor -= prevHeight
        svg.appendChild(
          svgNode("rect", {
            x: barLeft,
            y: prevCursor,
            width: barWidth,
            height: prevHeight,
            fill: "none",
            stroke: "#D1D1D1",
            "stroke-width": 1,
            "stroke-dasharray": "4 3",
          }),
        )
      }

      if (currHeight > 0) {
        currCursor -= currHeight
        svg.appendChild(
          svgNode("rect", {
            x: barLeft,
            y: currCursor,
            width: barWidth,
            height: currHeight,
            fill: barFill(meta.pattern),
            stroke: "#0A0A0A",
            "stroke-width": 1,
            opacity: currentOpacity,
          }),
        )
      }
    }

    const adjustedTotal = categories.reduce((sum, key) => sum + toNumber(currentValues[key], 0), 0)
    const frictionScore =
      toNumber(currentRow.friction_score, 0) ||
      Math.min(100, Math.round((toNumber(currentValues.admin, 0) / Math.max(1, adjustedTotal)) * 100))
    if (frictionScore >= 55) {
      const totalTop = chartY(maxValue, toNumber(currentRow.total, 0))
      drawFrictionMarker(svg, dayCenterX(dayIdx, slots), totalTop - 10, frictionScore >= 72, dayIdx === selectedIdx ? 1 : 0.45)
    }
  }

  if (slots <= 16) {
    drawSelectedAnnotation(svg, selectedIdx, current, barWidth, maxValue, slots)
  }
  drawSelectedDayMarker(svg, selectedIdx, slots)
}

function deriveToolUsageRows(workflows, payloadToolUsage = []) {
  let tools = []
  if (Array.isArray(payloadToolUsage) && payloadToolUsage.length) {
    tools = payloadToolUsage
      .map((row) => {
        const toolName = String(row?.tool || "").trim() || "Unknown Tool"
        const minutes = Math.max(0, toNumber(row?.minutes, 0))
        const workflowsCount = Math.max(0, toNumber(row?.workflows_count ?? row?.workflowsCount, 0))
        return {
          tool: toolName,
          minutes,
          workflowsCount,
          pattern: toolPatternForName(toolName, ""),
        }
      })
      .sort((a, b) => b.minutes - a.minutes)
  } else {
    const toolMap = new Map()
    for (const workflow of workflows) {
      const chunks = deriveToolBreakdown(workflow)
      for (const chunk of chunks) {
        const toolName = String(chunk.tool || "").trim() || "Unknown Tool"
        const key = toolName.toLowerCase()
        const minutes = Math.max(0, toNumber(chunk.minutes, 0))
        const existing = toolMap.get(key)
        if (!existing) {
          toolMap.set(key, {
            tool: toolName,
            minutes,
            workflows: new Set([String(workflow.id || "")]),
            pattern: chunk.pattern || "solid",
          })
          continue
        }
        existing.minutes += minutes
        existing.workflows.add(String(workflow.id || ""))
      }
    }
    tools = [...toolMap.values()]
      .map((row) => ({
        tool: row.tool,
        minutes: row.minutes,
        workflowsCount: [...row.workflows].filter(Boolean).length,
        pattern: row.pattern || "solid",
      }))
      .sort((a, b) => b.minutes - a.minutes)
  }
  return tools
}

function renderToolUsageCards(container, tools, emptyText = "No tool-level usage found for this timeline.") {
  if (!container) return
  if (!Array.isArray(tools) || !tools.length) {
    container.classList.remove("is-ghost-scroll")
    container.innerHTML = `<article class="workflow-card"><p class="detail-copy">${escapeHtml(emptyText)}</p></article>`
    return
  }

  const totalMinutes = tools.reduce((sum, row) => sum + row.minutes, 0)
  const maxMinutes = Math.max(1, ...tools.map((row) => row.minutes))

  container.innerHTML = tools
    .map((row) => {
      const logo = toolLogoMeta(row.tool)
      const widthPct = Math.max(0, Math.min(100, (row.minutes / maxMinutes) * 100))
      const sharePct = totalMinutes > 0 ? (row.minutes / totalMinutes) * 100 : 0
      return `
      <article class="workflow-card">
        <div class="workflow-head">
          <p class="workflow-name">
            <span class="tool-brand">
              ${
                logo.src
                  ? logoImageMarkup(logo)
                  : ""
              }
              <span class="tool-logo-fallback"${logo.src ? ' style="display:none"' : ""}>${escapeHtml(logo.fallback)}</span>
              <span>${escapeHtml(row.tool)}</span>
            </span>
          </p>
          <span class="pattern-chip pattern-${escapeHtml(row.pattern)}"></span>
        </div>
        <p class="metric"><span>Time tracked</span><span>${fmtInt(row.minutes)} min</span></p>
        <div class="bar"><span style="width:${widthPct}%"></span></div>
        <p class="metric"><span>Share of timeline</span><span>${fmtInt(sharePct)}%</span></p>
        <div class="bar"><span style="width:${Math.max(0, Math.min(100, sharePct))}%"></span></div>
        <p class="metric"><span>Workflows using tool</span><span>${fmtInt(row.workflowsCount)}</span></p>
      </article>`
    })
    .join("")
}

function renderWorkflowCards(workflows, payloadToolUsage = []) {
  const tools = deriveToolUsageRows(workflows, payloadToolUsage)
  state.toolUsageRows = tools
  renderToolUsageCards(els.workflowCards, tools)
  applyToolAnalysisGhostScroll()
  renderToolAnalysisPopup()
}

function applyGhostScroll(container) {
  if (!container) return
  const hasCards = Boolean(container.querySelector(".workflow-card"))
  if (!hasCards) {
    container.classList.remove("is-ghost-scroll")
    return
  }
  const overflow = container.scrollHeight - container.clientHeight > 2
  container.classList.toggle("is-ghost-scroll", overflow)
}

function applyToolAnalysisGhostScroll() {
  applyGhostScroll(els.workflowCards)
}

function isToolAnalysisPopupOpen() {
  return Boolean(state.toolAnalysisPopupOpen && els.toolAnalysisPopupOverlay && !els.toolAnalysisPopupOverlay.hidden)
}

function renderToolAnalysisPopup() {
  if (!els.toolPopupCards) return
  renderToolUsageCards(els.toolPopupCards, state.toolUsageRows)
  applyGhostScroll(els.toolPopupCards)
}

function openToolAnalysisPopup() {
  if (!els.toolAnalysisPopupOverlay || !els.toolAnalysisPopup) return
  state.toolAnalysisPopupOpen = true
  els.toolAnalysisPopupOverlay.hidden = false
  els.toolAnalysisPopupOverlay.classList.add("is-open")
  document.body.classList.add("has-modal-open")
  renderToolAnalysisPopup()
}

function closeToolAnalysisPopup(returnFocus = false) {
  if (!els.toolAnalysisPopupOverlay) return
  state.toolAnalysisPopupOpen = false
  els.toolAnalysisPopupOverlay.classList.remove("is-open")
  els.toolAnalysisPopupOverlay.hidden = true
  document.body.classList.remove("has-modal-open")
  if (returnFocus && els.distributionHeading) {
    els.distributionHeading.focus()
  }
}

function syncTopRowModuleHeights() {
  if (!els.performanceModule || !els.toolAnalysisModule) return
  const overviewVisible = Boolean(els.panels?.overview?.classList.contains("is-visible"))
  const desktopLayout = window.matchMedia("(min-width: 1181px)").matches
  if (!overviewVisible || !desktopLayout) {
    els.toolAnalysisModule.style.height = ""
    applyToolAnalysisGhostScroll()
    if (isToolAnalysisPopupOpen()) renderToolAnalysisPopup()
    return
  }
  const previousHeight = els.toolAnalysisModule.style.height
  els.toolAnalysisModule.style.height = ""
  const targetHeight = Math.ceil(els.performanceModule.offsetHeight || els.performanceModule.getBoundingClientRect().height || 0)
  if (targetHeight > 0) {
    els.toolAnalysisModule.style.height = `${targetHeight}px`
  } else {
    els.toolAnalysisModule.style.height = previousHeight
  }
  applyToolAnalysisGhostScroll()
  if (isToolAnalysisPopupOpen()) renderToolAnalysisPopup()
}

function renderWorkflowTable(workflows) {
  if (!workflows.length) {
    els.workflowRows.innerHTML = els.emptyWorkflowRow.innerHTML
    return
  }
  els.workflowRows.innerHTML = workflows
    .map(
      (workflow) => {
        const workflowId = String(workflow.id || "")
        const editingName = state.editingWorkflowNameId === workflowId
        const nameValue = editingName ? sanitizeWorkflowDisplayName(state.workflowNameDraft || workflow.name) : workflow.name
        return `
      <tr data-workflow-id="${escapeHtml(workflow.id)}" class="${
        state.detailOpen && workflow.id === state.selectedWorkflowId ? "is-selected" : ""
      }">
        <td>
          <div class="row-title-wrap">
            ${
              editingName
                ? `
              <input
                class="row-title-input"
                type="text"
                maxlength="120"
                value="${escapeHtml(nameValue)}"
                data-workflow-name-input="${escapeHtml(workflowId)}"
                aria-label="Edit workflow name"
              />
              <div class="row-title-actions">
                <button class="mini-btn" type="button" data-workflow-name-save="${escapeHtml(workflowId)}">Save</button>
                <button class="mini-btn" type="button" data-workflow-name-cancel="${escapeHtml(workflowId)}">Cancel</button>
                <button class="mini-btn" type="button" data-workflow-name-reset="${escapeHtml(workflowId)}">Reset</button>
              </div>
            `
                : `
              <p class="row-title">${escapeHtml(workflow.name)}</p>
              <button class="mini-btn row-title-edit-btn" type="button" data-workflow-name-edit="${escapeHtml(workflowId)}">Edit</button>
            `
            }
          </div>
          <p class="row-sub">${escapeHtml(workflow.details || "")}</p>
        </td>
        <td>${escapeHtml(CATEGORY_META[workflow.typeKey]?.label || "Deep Work")}</td>
        <td>${fmtInt(workflow.frictionScore)}</td>
        <td>${escapeHtml(workflow.actionFrequency)}</td>
        <td>${fmtInt(workflow.durationMinutes)} min</td>
      </tr>`
      },
    )
    .join("")
}

function renderDetailPanel(workflow) {
  if (!workflow || !state.detailOpen) {
    els.detailPanel.innerHTML = `
      <div class="detail-empty">
        <p class="script-note">What You Did</p>
        <p class="detail-copy">Select a workflow row to open the ledger breakdown.</p>
      </div>`
    return
  }
  const seen = parseLastSeen(workflow)
  const whenLabel = seen.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
  const typeLabel = CATEGORY_META[workflow.typeKey]?.label || "Deep Work"
  const tools = deriveToolBreakdown(workflow)
  const timelineData = deriveTimelineEntries(workflow)
  const timeline = Array.isArray(timelineData?.entries) ? timelineData.entries : []
  const timelineLikelyActivity = String(timelineData?.likelyActivity || "pattern activity")
  const focusIdx = Math.max(0, Math.min(timeline.length - 1, timeline.length > 3 ? 2 : 1))
  const narrativeLoading = Boolean(state.loadingNarratives[workflow.id])
  const narrative = state.workflowNarratives[workflow.id]
  const narrativeSource = state.narrativeSources[workflow.id] || ""
  const narrativeConfidence = String(state.workflowNarrativeConfidence[workflow.id] || "").trim()
  const narrativeEvidence = Array.isArray(state.workflowNarrativeEvidence[workflow.id])
    ? state.workflowNarrativeEvidence[workflow.id].map((row) => String(row || "").trim()).filter(Boolean).slice(0, 4)
    : []
  const narrativeOverride = String(state.narrativeOverrides[workflow.id] || "").trim()
  const narrativeEffective = narrativeOverride || narrative || workflow.details || "No summary draft available yet."
  const editingNarrative = state.editingNarrativeWorkflowId === workflow.id
  const narrativeDraftValue = editingNarrative ? state.narrativeDraftText || narrativeEffective : ""
  const insightText = automationInsightText(workflow, narrativeEffective)
  const maxToolMinutes = Math.max(1, ...tools.map((row) => row.minutes))
  const annotationTop = 56 + focusIdx * 72
  const savings = estimateWorkflowTimeSavings(workflow)
  const lowEvidence = /insufficient detail|insufficient evidence|focus switching only/i.test(timelineLikelyActivity)
  const marginaliaText = "Limited evidence in this sequence"
  const showMarginalia = timeline.length > 1 && lowEvidence

  els.detailPanel.innerHTML = `
    <article class="ledger-detail-sheet">
      <header class="ledger-detail-header">
        <div>
          <h3 class="ledger-title-sans">${escapeHtml(workflow.name)}</h3>
          <div class="ledger-meta-inline">
            <span class="clock-ink" aria-hidden="true"></span>
            <span>${escapeHtml(whenLabel)}</span>
            <span class="ledger-type-pill">${escapeHtml(typeLabel)}</span>
            <span>${fmtInt(workflow.durationMinutes)} min</span>
          </div>
        </div>
        <button class="ink-close-btn" data-detail-close="1" type="button" aria-label="Close detail">
          <span></span><span></span>
        </button>
      </header>

      <div class="rough-divider"></div>

      <section>
        <p class="script-note">What You Did</p>
        ${
          editingNarrative
            ? `<textarea class="narrative-editor" data-narrative-input="1" rows="5">${escapeHtml(narrativeDraftValue)}</textarea>`
            : `<p class="ledger-description-sans">${escapeHtml(
                narrativeLoading ? "Generating an intent draft from tool patterns..." : narrativeEffective,
              )}</p>`
        }
        <div class="narrative-controls">
          ${
            editingNarrative
              ? `
            <button class="mini-btn" data-narrative-save="${escapeHtml(workflow.id)}" type="button">Save Draft</button>
            <button class="mini-btn" data-narrative-cancel="${escapeHtml(workflow.id)}" type="button">Cancel</button>
          `
              : `
            <button class="mini-btn" data-narrative-edit="${escapeHtml(workflow.id)}" type="button">Edit What You Did</button>
            ${
              narrativeOverride
                ? `<button class="mini-btn" data-narrative-reset="${escapeHtml(workflow.id)}" type="button">Use Auto Draft</button>`
                : ""
            }
          `
          }
        </div>
        ${
          !editingNarrative && !narrativeLoading
            ? `<p class="narrative-source">Insight source: ${escapeHtml(
                narrativeOverride ? "USER EDITED" : narrativeSource ? narrativeSource.toUpperCase() : "DRAFT",
              )}</p>`
            : ""
        }
        ${
          !editingNarrative && !narrativeLoading && (narrativeConfidence || narrativeEvidence.length)
            ? `<div class="narrative-meta">
            ${
              narrativeConfidence
                ? `<span class="narrative-confidence-pill">${escapeHtml(narrativeConfidence)} confidence</span>`
                : ""
            }
            ${
              narrativeEvidence.length
                ? `<div class="narrative-evidence-list">${narrativeEvidence
                    .map((row) => `<span class="narrative-evidence-chip">${escapeHtml(row)}</span>`)
                    .join("")}</div>`
                : ""
            }
          </div>`
            : ""
        }
      </section>

      <section>
        <p class="ledger-section-title">Tools & Time Breakdown</p>
        <div class="tool-breakdown-list">
          ${tools
            .map((row) => {
              const pct = Math.max(8, Math.round((row.minutes / maxToolMinutes) * 100))
              const logo = toolLogoMeta(row.tool)
              return `
              <div class="tool-breakdown-row">
                <p class="tool-breakdown-text">
                  <span class="tool-breakdown-line">
                    <span class="tool-brand">
                      ${
                        logo.src
                          ? logoImageMarkup(logo)
                          : ""
                      }
                      <span class="tool-logo-fallback"${logo.src ? ' style="display:none"' : ""}>${escapeHtml(logo.fallback)}</span>
                      <span>${escapeHtml(row.tool)}</span>
                    </span>
                    <span class="tool-time">${fmtInt(row.minutes)} min</span>
                  </span>
                </p>
                <div class="tool-breakdown-track">
                  <span class="tool-breakdown-fill pattern-${escapeHtml(row.pattern)}" style="width:${pct}%"></span>
                </div>
              </div>`
            })
            .join("")}
        </div>
      </section>

      <section class="ledger-timeline-section">
        <p class="ledger-section-title">Pattern Timeline</p>
        <div class="timeline-ledger">
          <div class="timeline-spine"></div>
          ${timeline
            .map(
              (entry) => `
            <article class="timeline-entry">
              <p class="timeline-time">${escapeHtml(entry.time)}</p>
              <div class="timeline-body">
                <p class="timeline-action">${escapeHtml(entry.action)}</p>
                <div class="timeline-tag-row">
                  <span class="timeline-tool-tag">${escapeHtml(entry.tag || timelineLikelyActivity)}</span>
                </div>
                ${entry.note ? `<p class="timeline-note">${escapeHtml(entry.note)}</p>` : ""}
              </div>
            </article>`,
            )
            .join("")}
          ${
            showMarginalia
              ? `<div class="marginalia-note" style="top:${annotationTop}px">
            ${escapeHtml(marginaliaText)}
            <span class="marginalia-arrow"></span>
          </div>`
              : ""
          }
        </div>
      </section>

      <section>
        <p class="script-note">Automation Insight</p>
        <p class="detail-copy">${escapeHtml(insightText)}</p>
        <p class="detail-copy detail-timesaving">Potential time savings: ${fmtOne(savings.hoursPerWeek)} h/week (~${fmtInt(
          savings.minutesPerDay,
        )} min/day).</p>
      </section>
    </article>
  `
}

function renderSources(payload) {
  if (!els.sourceRows) return
  const sources = Array.isArray(payload?.scan?.sources) ? payload.scan.sources : []
  els.sourceRows.innerHTML = sources.length
    ? sources
        .map((source) => {
          const status = source.available === false ? "unavailable" : source.disabled ? "disabled" : "active"
          const bits = [`kind=${source.kind || "source"}`, `events=${fmtInt(source.events || 0)}`, `status=${status}`]
          if (source.error) bits.push(`error=${source.error}`)
          return `<div class="source-row">${escapeHtml(String(source.source || "source"))}<br>${escapeHtml(bits.join(" | "))}</div>`
        })
        .join("")
    : `<div class="source-row">No source data.</div>`
}

function renderAutomationIdeas(payload) {
  if (!els.automationIdeas) return
  const workflows = derivedWorkflows(payload)
  const workflowByIdMap = new Map(workflows.map((workflow) => [String(workflow.id || ""), workflow]))
  const groups = groupAutomationCandidates(payload)
  const activeGroups = groups.filter((group) => !state.completedAutomations[group.key])

  if (!activeGroups.length) {
    els.automationIdeas.innerHTML = `<div class="idea-row">All current automations are marked done.</div>`
    return
  }

  els.automationIdeas.innerHTML = activeGroups
    .slice(0, 12)
    .map((group) => {
      const workflowId = String(group.workflowIds.find((id) => workflowByIdMap.has(id)) || group.workflowIds[0] || "")
      const workflow = workflowByIdMap.get(workflowId) || null
      const summary = workflowOneLiner(workflow || group)
      const openDisabled = workflowId ? "" : " disabled"
      return `
      <article class="automation-workflow-row">
        <h3 class="automation-workflow-name">${escapeHtml(group.name)}</h3>
        <p class="automation-workflow-desc">${escapeHtml(summary)}</p>
        <button class="open-postit-btn automation-open-btn" type="button" data-open-workflow-id="${escapeHtml(
          workflowId,
        )}"${openDisabled}>Open Automation Suggested</button>
      </article>`
    })
    .join("")
}

function renderCompletedAutomations(payload) {
  if (!els.completedAutomations) return
  const grouped = groupAutomationCandidates(payload)
  const groupedByKey = new Map(grouped.map((group) => [group.key, group]))
  const entries = Object.values(state.completedAutomations || {})
    .filter((entry) => entry && typeof entry === "object")
    .sort((a, b) => String(b.completed_at || "").localeCompare(String(a.completed_at || "")))

  if (!entries.length) {
    els.completedAutomations.innerHTML = `<div class="idea-row">No completed automations yet.</div>`
    return
  }

  els.completedAutomations.innerHTML = entries
    .map((entry) => {
      const key = String(entry.key || "")
      const liveGroup = groupedByKey.get(key)
      const name = String(liveGroup?.name || entry.name || "Workflow")
      const when = formatCompletedAt(entry.completed_at)
      const hours = toNumber(liveGroup?.hoursSavedPerWeek, toNumber(entry.hours_saved_per_week, 0))
      return `<div class="idea-row">${escapeHtml(name)} | completed ${escapeHtml(when)} | ${fmtOne(hours)} h/week</div>`
    })
    .join("")
}

function workflowById(workflowId) {
  if (!state.payload || !workflowId) return null
  const all = derivedWorkflows(state.payload)
  return all.find((row) => row.id === workflowId) || null
}

function startWorkflowNameEdit(workflowId) {
  const workflow = workflowById(workflowId)
  if (!workflow) return
  state.editingWorkflowNameId = String(workflowId || "")
  state.workflowNameDraft = String(workflow.name || "")
  if (state.payload) renderOverview(state.payload)
}

function cancelWorkflowNameEdit() {
  state.editingWorkflowNameId = ""
  state.workflowNameDraft = ""
  if (state.payload) renderOverview(state.payload)
}

function saveWorkflowNameEdit(workflowId) {
  const workflow = workflowById(workflowId)
  if (!workflow) return
  const key = String(workflowId || "")
  const baseName = sanitizeWorkflowDisplayName(workflow._baseName || workflow.name || "Workflow")
  const nextName = sanitizeWorkflowDisplayName(state.workflowNameDraft || workflow.name || "")
  if (!key) return
  if (!nextName || nextName.toLowerCase() === baseName.toLowerCase()) {
    delete state.workflowNameOverrides[key]
  } else {
    state.workflowNameOverrides[key] = nextName
  }
  persistWorkflowNameOverrides(state.workflowNameOverrides)
  state.editingWorkflowNameId = ""
  state.workflowNameDraft = ""
  if (state.payload) renderAll()
}

function markAutomationDone(workflow) {
  const workflowId = String(workflow?.id || "").trim()
  if (!workflowId) {
    setStatus("Select a workflow before marking automation as done.", true)
    return
  }
  const key = automationGroupKey(workflow)
  if (state.completedAutomations[key]) {
    closePostit()
    if (state.payload) renderAll()
    setStatus(`"${workflow.name}" is already in Completed Automations.`)
    return
  }

  const draft = state.automationDrafts[workflowId]
  const estimated = toNumber(draft?.estimated_hours_saved_per_week, estimateWorkflowTimeSavings(workflow).hoursPerWeek)
  state.completedAutomations[key] = {
    key,
    workflow_id: workflowId,
    name: String(workflow?.name || "Workflow"),
    completed_at: new Date().toISOString(),
    hours_saved_per_week: Number(estimated.toFixed(2)),
  }
  persistCompletedAutomations(state.completedAutomations)
  state.signedAutomationIds[workflowId] = true
  state.approvedWorkflowIds[workflowId] = true

  closePostit()
  if (state.payload) renderAll()
  setStatus(`Marked "${workflow.name}" as done and moved it to Completed Automations.`)
}

function uniquePromptRows(rows, fallback, limit = 12) {
  const out = []
  const seen = new Set()
  for (const row of Array.isArray(rows) ? rows : []) {
    const text = String(row || "").replace(/\s+/g, " ").trim()
    const key = text.toLowerCase()
    if (!text || seen.has(key)) continue
    seen.add(key)
    out.push(text)
    if (out.length >= Math.max(1, toNumber(limit, 12))) break
  }
  if (out.length) return out
  return [String(fallback || "").trim() || "No data provided."]
}

function markdownBulletLines(rows, fallback, limit = 12) {
  return uniquePromptRows(rows, fallback, limit)
    .map((row) => `- ${row}`)
    .join("\n")
}

function workflowBrowserSites(workflow) {
  const rows = []
  const seen = new Set()
  const steps = Array.isArray(workflow?.steps) ? workflow.steps : []
  for (const step of steps) {
    const action = String(step?.action || "").trim()
    const match = action.match(/^browser\s+visit\s+(.+)$/i)
    if (!match?.[1]) continue
    const normalized = String(match[1] || "")
      .toLowerCase()
      .replace(/^https?:\/\//, "")
      .replace(/^www\./, "")
      .split(/[/?#\s]/)[0]
      .replace(/\.+$/, "")
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    rows.push(normalized)
    if (rows.length >= 4) break
  }
  return rows
}

function inferWorkflowIntentForPrompt(workflow) {
  const text = [
    String(workflow?.name || ""),
    String(workflow?.details || ""),
    String(workflow?.category || ""),
    ...(Array.isArray(workflow?.tools) ? workflow.tools : []),
    ...(Array.isArray(workflow?.steps) ? workflow.steps.map((step) => String(step?.action || "")) : []),
  ]
    .join(" ")
    .toLowerCase()
  const jobFlow = /(job|jobs|application|hiring|resume|recruiter|career)/.test(text) || /linkedin/.test(text)
  if (jobFlow) {
    return {
      jobFlow: true,
      label: "researching open roles and preparing job applications",
      role:
        "You are an Automation Systems Architect focused on reliable workflow agents, job-search automation, structured data capture, and company intelligence research.",
      discoverySurface: "LinkedIn",
    }
  }
  return {
    jobFlow: false,
    label: "intent-aware workflow automation and decision support",
    role:
      "You are an Automation Systems Architect focused on reliable workflow agents, intent-aware workflow automation, structured data capture, and company intelligence research.",
    discoverySurface: "the observed workflow tools",
  }
}

function formatPromptToolRows(workflow, requiredTools) {
  const sites = workflowBrowserSites(workflow)
  const rows = []
  const tools = Array.isArray(requiredTools) ? requiredTools : []
  for (const raw of tools) {
    const tool = String(raw || "").trim()
    if (!tool) continue
    if (tool.toLowerCase() === "web browser" && sites.length) {
      rows.push(`Web Browser (observed sites: ${sites.join(", ")})`)
    } else {
      rows.push(friendlyToolName(tool))
    }
  }
  if (!rows.length && sites.length) rows.push(`Web Browser (observed sites: ${sites.join(", ")})`)
  return uniquePromptRows(rows, "Observed workflow tools only (no external tools inferred).", 12)
}

function buildComprehensivePromptTemplate({ workflow, days, title, goal, processSteps, requiredTools }) {
  const intent = inferWorkflowIntentForPrompt(workflow)
  const jobFlow = Boolean(intent.jobFlow)
  const discoverySurface = intent.discoverySurface
  const objectiveRows = jobFlow
    ? [
        `find relevant jobs from ${discoverySurface},`,
        "add them to a tracker in a structured and deduplicated way,",
        "conduct deep research on each company,",
        "produce useful summaries that help me evaluate whether to apply.",
      ]
    : [
        `find relevant qualifying work items from ${discoverySurface},`,
        "add them to a tracker in a structured and deduplicated way,",
        "conduct deep context research on each selected item or organization,",
        "produce useful summaries that help me decide what action to take next.",
      ]
  const successRows = jobFlow
    ? [
        `${discoverySurface} jobs are consistently identified using clear qualification rules,`,
        "jobs are added to a tracker with validated fields and no duplicate entries,",
        "each company is researched in depth using public web sources,",
        "outputs are logged clearly with completion status, confidence, and failure reasons,",
        "exceptions such as auth/session expiry, broken pages, missing fields, or research gaps are surfaced for review rather than silently ignored,",
        "the workflow is idempotent, auditable, and practical to run repeatedly.",
      ]
    : [
        "qualifying workflow items are identified using explicit relevance thresholds,",
        "records are written with validated fields and deduplication safeguards,",
        "supporting context research is generated from observed tools and public sources,",
        "outputs include completion status, confidence notes, and clear failure reasons,",
        "exceptions such as auth/session expiry, missing fields, and source inconsistencies are surfaced for review rather than silently ignored,",
        "the workflow is idempotent, auditable, and practical to run repeatedly.",
      ]

  const stageBlocks = jobFlow
    ? [
        {
          title: "Stage 1: Job Discovery",
          rows: [
            `visit ${discoverySurface} job search pages`,
            "detect job posts that match predefined relevance criteria",
            "extract core job details",
            "identify whether the job is new or already tracked",
            "decide whether to save, skip, or flag for review",
          ],
        },
        {
          title: "Stage 2: Structured Tracking",
          rows: [
            "write the selected job into a tracker",
            "ensure deduplication through a strong idempotency key",
            "validate required fields before writing",
            "log status of write success or failure",
            "preserve prior data rather than destructively overwriting it",
          ],
        },
        {
          title: "Stage 3: Deep Company Research",
          rows: [
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
        },
        {
          title: "Stage 4: Candidate Decision Support",
          rows: [
            "Is this company worth my time?",
            "Is this role aligned with my goals?",
            "What is differentiated or risky about this opportunity?",
            "What should I investigate further before applying?",
          ],
        },
      ]
    : [
        {
          title: "Stage 1: Signal Discovery",
          rows: [
            `visit ${discoverySurface} and related observed workflow surfaces`,
            "detect items that match predefined relevance criteria",
            "extract core details needed for downstream decisions",
            "identify whether the item is new or already tracked",
            "decide whether to save, skip, or flag for review",
          ],
        },
        {
          title: "Stage 2: Structured Tracking",
          rows: [
            "write selected items into a tracker",
            "ensure deduplication through a strong idempotency key",
            "validate required fields before writing",
            "log status of write success or failure",
            "preserve prior data rather than destructively overwriting it",
          ],
        },
        {
          title: "Stage 3: Context Research",
          rows: [
            "subject/company overview",
            "core product, process, or initiative context",
            "business or operational significance",
            "stage and traction signals where relevant",
            "recent updates and noteworthy developments",
            "competitive or comparative positioning",
            "risks or red flags",
            "why the opportunity may or may not be attractive",
          ],
        },
        {
          title: "Stage 4: Decision Support",
          rows: [
            "Is this worth deeper follow-up?",
            "Is this aligned with my goals and priorities?",
            "What is differentiated or risky here?",
            "What should I investigate further before acting?",
          ],
        },
      ]

  const stageText = stageBlocks
    .map((stage) => `### ${stage.title}\n${markdownBulletLines(stage.rows, "No stage details provided.", 14)}`)
    .join("\n\n")

  const processLines = markdownBulletLines(processSteps, "No process steps provided.", 12)
  const toolLines = markdownBulletLines(formatPromptToolRows(workflow, requiredTools), "No explicit tools provided.", 12)
  const watchLines = markdownBulletLines(
    [
      "Duplicate events and retries can create duplicate outputs unless idempotency keys are enforced.",
      "Auth/session expiry or permission issues can silently fail runs unless surfaced in alerts.",
      "Source pages may have inconsistent structure, incomplete fields, or pagination issues.",
      "Entity names may require normalization before writing and research.",
      "Deep research can become noisy unless bounded by templates and stopping conditions.",
    ],
    "No specific risks detected.",
    8,
  )
  const avoidLines = markdownBulletLines(
    [
      "Avoid destructive writes (delete/overwrite) without an explicit confirmation checkpoint.",
      "Avoid running end-to-end actions on every noisy trigger; require qualifying conditions first.",
      "Avoid swallowing errors; always emit failure context and retry guidance.",
      "Avoid generic summaries with little decision value.",
      "Avoid collecting data that is not actionable.",
    ],
    "No avoid-list provided.",
    8,
  )
  const constraintLines = markdownBulletLines(
    [
      "Only add or process items that pass relevance thresholds.",
      "Avoid duplicate entries caused by retries, repeated visits, or duplicate listing surfaces.",
      "Avoid destructive writes, deletions, or overwrites without an explicit confirmation checkpoint.",
      "Avoid running full deep research on every noisy trigger; require qualification first.",
      "Avoid silent failures; always emit failure context, likely cause, and retry guidance.",
      "Surface auth/session issues explicitly.",
      "Preserve logs for auditability.",
      "Prefer modular architecture so discovery, tracking, and research can run independently if needed.",
    ],
    "Apply explicit guardrails for reliability and auditability.",
    12,
  )

  return [
    "## Role to Assume",
    intent.role,
    "",
    "## Core Objective",
    "Design an automation system that helps me:",
    markdownBulletLines(objectiveRows, "design a reliable automation around this workflow.", 8),
    "",
    "The system should reduce manual browsing, copying, and context switching while maintaining high reliability and clear human oversight.",
    `Operational target: ${goal}`,
    "",
    "## Success Criteria",
    "Success means:",
    markdownBulletLines(successRows, "the workflow runs reliably with validated outputs and visible failure handling.", 10),
    "",
    "## Instructions for How to Think",
    "Reason carefully and systematically before answering, but do not reveal hidden internal reasoning.",
    "Instead, provide a structured and transparent analysis that shows:",
    "- assumptions,",
    "- workflow diagnosis,",
    "- system design,",
    "- agent responsibilities,",
    "- qualifying logic,",
    "- data schema,",
    "- error handling,",
    "- prioritization,",
    "- risks and tradeoffs.",
    "",
    "Be practical, not theoretical.",
    "Be critical about where full automation is appropriate versus where human review should remain.",
    "Do not assume every item should be captured or every company/topic should be researched equally deeply.",
    "Design for signal over noise.",
    "",
    "## Workflow to Design",
    `The target workflow should support this inferred intent: ${intent.label}.`,
    "",
    stageText,
    "",
    "## Existing Process Map",
    processLines,
    "",
    "## Tools Required",
    toolLines,
    "",
    "## Key Design Constraints",
    constraintLines,
    "",
    "## What to Look Out For",
    watchLines,
    "",
    "## What to Avoid",
    avoidLines,
    "",
    "## Context",
    `- Workflow Title: ${title}`,
    `- Window: last ${Math.max(1, toNumber(days, 7))} days`,
    "",
    "## What I Want You to Produce",
    "Please structure your response exactly as follows:",
    "",
    "### 1. Context Summary",
    "Summarize the workflow and operating objective.",
    "",
    "### 2. Assumptions",
    "List the assumptions you are making about the process, tracker, and decision goals.",
    "",
    "### 3. Workflow Diagnosis",
    "Explain where the current friction likely exists between discovery, data capture, research, and decision-making.",
    "",
    "### 4. Recommended Automation Design",
    "Design the automation end-to-end.",
    "Include:",
    "- triggers,",
    "- qualifying conditions,",
    "- extraction logic,",
    "- deduplication logic,",
    "- tracker write logic,",
    "- research workflow,",
    "- review checkpoints,",
    "- completion logging.",
    "",
    "### 5. Recommended Agents",
    "Define the agents that should exist in the system.",
    "For each agent, include:",
    "- name,",
    "- mission,",
    "- trigger,",
    "- inputs,",
    "- outputs,",
    "- boundaries,",
    "- escalation rules,",
    "- human-in-the-loop requirements,",
    "- key failure modes.",
    "",
    "### 6. Qualification Framework",
    "Define how the system should decide whether an item is relevant enough to save.",
    "Include:",
    "- hard filters,",
    "- soft scoring criteria,",
    "- reasons to skip,",
    "- reasons to flag for review.",
    "",
    "### 7. Tracker Schema",
    "Propose the ideal tracker structure and fields.",
    "Include:",
    "- item-level fields,",
    "- organization/company-level fields,",
    "- research-level fields,",
    "- workflow status fields,",
    "- timestamps,",
    "- idempotency key design.",
    "",
    "### 8. Research Framework",
    "Design the deep research output template.",
    "It should capture:",
    "- summary,",
    "- product/service context,",
    "- business model,",
    "- market,",
    "- team,",
    "- traction,",
    "- funding when available,",
    "- news,",
    "- competitors,",
    "- risks,",
    "- decision thesis,",
    "- open questions.",
    "",
    "### 9. Prioritization Logic",
    "Explain when the system should:",
    "- only save an item,",
    "- save plus light research,",
    "- save plus deep research,",
    "- escalate to me for manual review.",
    "",
    "### 10. Reliability and Error Handling",
    "Describe:",
    "- retry strategy,",
    "- duplicate prevention,",
    "- logging,",
    "- failure alerts,",
    "- fallback behavior,",
    "- safe handling of partial completion.",
    "",
    "### 11. What Should Stay Human-Led",
    "Identify which parts of the process should remain human-owned and why.",
    "",
    "### 12. Implementation Roadmap",
    "Break this into phases:",
    "- Phase 1: basic capture and tracking,",
    "- Phase 2: qualification and deduplication,",
    "- Phase 3: research agent,",
    "- Phase 4: decision-support layer.",
    "",
    "### 13. Final Recommendation",
    "End with:",
    "- the best minimal viable automation,",
    "- the best longer-term agent system,",
    "- the biggest risk to avoid,",
    "- the most important design principle.",
    "",
    "## Quality Bar",
    "The answer should be detailed, operational, and implementation-aware.",
    "Do not give generic suggestions like 'build an agent'.",
    "Specify exactly how the workflow should work, what each component does, and where human judgment should remain.",
    "Optimize for usefulness, reliability, and decision quality.",
  ].join("\n")
}

function localAutomationDraft(workflow) {
  const observedTools = Array.isArray(workflow?.tools)
    ? workflow.tools.map((tool) => titleCase(tool)).filter(Boolean)
    : []
  const stepDerivedTools = Array.isArray(workflow?.steps)
    ? workflow.steps
        .map((step) => String(step?.action || "").trim().split(/\s+/)[0] || "")
        .map((tool) => titleCase(tool))
        .filter(Boolean)
    : []
  const tools = [...new Set([...observedTools, ...stepDerivedTools])].filter(Boolean)
  const workflowTools = tools.length ? tools : ["Workflow Tool"]
  const sourceTool = tools[0] || "Source App"
  const targetTool = tools[1] || tools[0] || "Destination App"
  const steps = Array.isArray(workflow?.steps)
    ? workflow.steps.map((step) => String(step?.action || "").trim()).filter(Boolean)
    : []
  const process = (steps.length
    ? steps
    : [
        `Watch for a trigger in ${sourceTool}`,
        `Extract key fields from ${sourceTool}`,
        `Normalize and format records`,
        `Write structured updates to ${targetTool}`,
        "Post a completion summary and exceptions",
      ]
  ).slice(0, 8)
  const processMap = process.map((step, idx) => `${idx + 1}. ${step}`)
  const instructions = [
    `Monitor: Watch for new events in ${sourceTool} for this workflow type.`,
    "Extract: Pull sender/context, key fields, and action metadata.",
    `Action: Standardize and append validated rows to ${targetTool}.`,
    `Verification: Write completion status and errors to ${targetTool} run logs.`,
  ]
  const requiredTools = workflowTools.slice(0, 6)
  const title = `${workflow?.name || "Workflow"} Automation`
  const goal = `Reclaim ${fmtOne(workflow?.durationMinutes ? (workflow.durationMinutes * 0.65) / 60 : 1.5)} hours/week by automating the transition between ${sourceTool} and ${targetTool}.`
  return {
    ok: true,
    workflow_id: workflow?.id || "",
    workflow_name: workflow?.name || "Workflow",
    source: "fallback",
    process_map: processMap,
    technical_stack: requiredTools.map((tool) => ({
      tool,
      mcp_server: String(tool).toLowerCase().replaceAll(/[^a-z0-9]+/g, "_"),
      purpose: `Support ${workflow?.name || "workflow"} automation steps in ${tool}.`,
    })),
    skill_draft: {
      title,
      goal,
      instructions,
      required_tools: requiredTools,
    },
    llm_prompt: buildComprehensivePromptTemplate({
      workflow,
      days: state.days,
      title,
      goal,
      processSteps: process,
      requiredTools,
    }),
    estimated_hours_saved_per_week: Math.max(0.5, Number((workflow?.durationMinutes || 90) / 60) * 0.65),
  }
}

function normalizeProcessStepLabel(value) {
  return String(value || "")
    .replace(/^\s*\d+\s*[\).:\-]\s*/, "")
    .trim()
}

function draftProcessSteps(draft) {
  const raw = Array.isArray(draft?.process_map) ? draft.process_map : []
  const cleaned = raw.map((step) => normalizeProcessStepLabel(step)).filter(Boolean)
  if (cleaned.length) return cleaned.slice(0, 10)
  const fromInstructions = Array.isArray(draft?.skill_draft?.instructions) ? draft.skill_draft.instructions : []
  return fromInstructions.map((line) => normalizeProcessStepLabel(line)).filter(Boolean).slice(0, 8)
}

function trimFlowLine(value, maxLen = 54) {
  const text = String(value || "").replace(/\s+/g, " ").trim()
  if (!text) return ""
  if (text.length <= maxLen) return text
  return `${text.slice(0, Math.max(0, maxLen - 1)).trimEnd()}...`
}

function formatDetectionSignals(steps) {
  const rows = []
  for (const step of steps) {
    const text = String(step || "").trim()
    if (!text) continue
    const lower = text.toLowerCase()
    const browserVisit = lower.match(/^browser\s+visit\s+(.+)$/)
    if (browserVisit?.[1]) {
      rows.push(`Browser visit: ${trimFlowLine(browserVisit[1], 34)}`)
      continue
    }
    if (lower.endsWith(" active")) {
      rows.push(`Window focus: ${trimFlowLine(text.replace(/\s+active$/i, ""), 34)}`)
      continue
    }
    if (/\brun\b|\bpython\b|\bcurl\b|\bpkill\b|\bkill\b/.test(lower)) {
      rows.push(`Command activity: ${trimFlowLine(text, 34)}`)
      continue
    }
    rows.push(trimFlowLine(text, 44))
  }
  const unique = []
  const seen = new Set()
  for (const row of rows) {
    const key = row.toLowerCase()
    if (!key || seen.has(key)) continue
    seen.add(key)
    unique.push(row)
  }
  return unique.slice(0, 4)
}

function formatActionOutputs(draft) {
  const raw = Array.isArray(draft?.skill_draft?.instructions) ? draft.skill_draft.instructions : []
  const cleaned = raw
    .map((line) => String(line || "").replace(/^[a-z\s]+:\s*/i, "").trim())
    .filter(Boolean)
    .map((line) => trimFlowLine(line, 46))
  if (cleaned.length) return cleaned.slice(0, 4)
  return ["Monitor trigger events", "Extract required fields", "Apply workflow action", "Write verification summary"]
}

function renderProcessMapFlowTile(draft, loading, emptyText = "No process map returned.") {
  if (!els.processMapTile) return
  if (loading) {
    els.processMapTile.innerHTML = `<p class="flow-empty">Drafting your instructions...</p>`
    return
  }
  const steps = draftProcessSteps(draft)
  if (!steps.length) {
    els.processMapTile.innerHTML = `<p class="flow-empty">${escapeHtml(emptyText)}</p>`
    return
  }

  const title = trimFlowLine(draft?.workflow_name || "Workflow", 38)
  const detectionSignals = formatDetectionSignals(steps)
  const actionOutputs = formatActionOutputs(draft)
  const requiredTools = Array.isArray(draft?.skill_draft?.required_tools)
    ? draft.skill_draft.required_tools.map((tool) => trimFlowLine(tool, 24)).filter(Boolean)
    : []
  const processSnippet = steps.slice(0, 4).map((step) => trimFlowLine(step, 34))
  const stageRows = steps.slice(0, 6).map((step, index) => `${index + 1}. ${trimFlowLine(step, 44)}`)
  const hookRows = [
    `Workflow: ${title}`,
    `Entry: ${trimFlowLine(steps[0] || "Detected user activity", 34)}`,
    `Exit: ${trimFlowLine(steps[steps.length - 1] || "Run summary complete", 34)}`,
  ]
  const detectionRows = detectionSignals.length
    ? detectionSignals
    : processSnippet.map((step) => `Signal: ${step}`)
  const actionRows = actionOutputs.length
    ? actionOutputs
    : ["Monitor trigger events", "Extract key fields", "Apply workflow action", "Log run summary"]
  const toolRows = requiredTools.length ? requiredTools.slice(0, 6) : ["Workflow evidence only"]

  els.processMapTile.innerHTML = `
    <section class="flow-ledger">
      <svg class="flow-ledger-lines" viewBox="0 0 1000 580" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <marker id="flowArrowHead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" />
          </marker>
        </defs>
        <path d="M140 84 L262 84" marker-end="url(#flowArrowHead)" />
        <path d="M140 252 L262 252" marker-end="url(#flowArrowHead)" />
        <path d="M450 142 L450 184" marker-end="url(#flowArrowHead)" />
        <path d="M566 84 C720 84 865 84 882 84 C920 84 934 98 934 132 L934 154" marker-end="url(#flowArrowHead)" />
        <path d="M604 252 L722 252" marker-end="url(#flowArrowHead)" />
        <path d="M450 386 L450 430" marker-end="url(#flowArrowHead)" />
        <path d="M934 332 L934 498 C934 516 918 532 902 532 L624 532" marker-end="url(#flowArrowHead)" />
        <path d="M346 532 L112 532 C95 532 78 516 78 500 L78 318" marker-end="url(#flowArrowHead)" />
      </svg>

      <div class="flow-badge flow-user">
        <div class="flow-person-icon" aria-hidden="true"></div>
        <p class="flow-badge-title">User Inputs</p>
      </div>

      <article class="flow-box flow-box-hooks">
        <p class="flow-box-kicker">Hooks</p>
        <h4>Workflow Intake</h4>
        <ul>
          ${hookRows.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
        </ul>
      </article>

      <div class="flow-badge flow-events">
        <div class="flow-event-icon" aria-hidden="true">
          <span></span><span></span><span></span><span></span>
        </div>
        <p class="flow-badge-title">Event Stream</p>
      </div>

      <article class="flow-box flow-box-detect">
        <p class="flow-box-kicker">Analysis</p>
        <h4>Event Detection</h4>
        <ul>
          ${detectionRows.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
        </ul>
      </article>

      <article class="flow-box flow-box-actions">
        <p class="flow-box-kicker">Execution</p>
        <h4>Automated Actions</h4>
        <ul>
          ${actionRows.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
        </ul>
      </article>

      <article class="flow-box flow-box-trigger">
        <p class="flow-box-kicker">Control</p>
        <h4>Trigger Engine</h4>
        <ol class="flow-stage-list">
          ${stageRows.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
        </ol>
        <div class="flow-tool-chip-row">
          ${toolRows.map((tool) => `<span class="flow-tool-chip">${escapeHtml(tool)}</span>`).join("")}
        </div>
      </article>

      <p class="flow-feedback-note">Feedback Loop</p>
    </section>
  `
}

function localEditedAutomationDraft(baseDraft, workflow, instructionText) {
  const instruction = String(instructionText || "").trim()
  const sourceDraft =
    baseDraft && typeof baseDraft === "object" ? JSON.parse(JSON.stringify(baseDraft)) : localAutomationDraft(workflow)
  const steps = draftProcessSteps(sourceDraft)
  const updatedSteps = steps.length ? [...steps] : ["Capture trigger", "Extract data", "Apply action", "Verify outcome"]
  if (instruction) {
    updatedSteps.push(`Apply user edit: ${instruction}`)
  }
  sourceDraft.process_map = updatedSteps.slice(0, 10)
  const tools = Array.isArray(sourceDraft?.skill_draft?.required_tools) ? sourceDraft.skill_draft.required_tools : []
  sourceDraft.llm_prompt = buildComprehensivePromptTemplate({
    workflow,
    days: state.days,
    title: String(sourceDraft?.skill_draft?.title || sourceDraft.workflow_name || workflow?.name || "Workflow"),
    goal: String(sourceDraft?.skill_draft?.goal || "Automate this workflow."),
    processSteps: sourceDraft.process_map.map((step) => normalizeProcessStepLabel(step)).filter(Boolean),
    requiredTools: tools,
  })
  sourceDraft.source = "fallback-edit"
  return sourceDraft
}

function renderPostitTiles(workflow) {
  if (!workflow) return
  const workflowId = String(workflow.id || "")
  const completed = isWorkflowCompleted(workflow)
  const loading = Boolean(state.loadingAutomationDrafts[workflowId])
  const updating = Boolean(state.processMapUpdating && state.currentAutomationWorkflowId === workflowId)
  const draft = state.automationDrafts[workflowId]
  const source = state.automationDraftSources[workflowId] || draft?.source || "heuristic"
  const signed = Boolean(state.signedAutomationIds[workflowId])
  const editing = Boolean(state.processMapEditing && state.currentAutomationWorkflowId === workflowId)
  const promptEditing = Boolean(state.promptEditing && state.currentAutomationWorkflowId === workflowId)

  els.draftingState.classList.toggle("is-visible", loading || updating)

  if (els.processMapEditWrap) {
    els.processMapEditWrap.classList.toggle("is-open", editing)
  }
  if (els.processMapEditInput && editing) {
    els.processMapEditInput.value = state.processMapEditText || ""
    els.processMapEditInput.disabled = loading || updating
  }
  if (els.editProcessMapBtn) {
    els.editProcessMapBtn.disabled = loading || updating || !draft
    els.editProcessMapBtn.textContent = editing ? "Editing..." : "Edit"
  }
  if (els.applyProcessMapEditBtn) {
    els.applyProcessMapEditBtn.disabled = loading || updating || !editing
  }
  if (els.cancelProcessMapEditBtn) {
    els.cancelProcessMapEditBtn.disabled = loading || updating || !editing
  }
  if (els.promptEditWrap) {
    els.promptEditWrap.classList.toggle("is-open", promptEditing)
  }
  if (els.promptEditInput && promptEditing) {
    els.promptEditInput.value = state.promptEditText || String(draft?.llm_prompt || "")
    els.promptEditInput.disabled = loading || updating
  }
  if (els.editPromptBtn) {
    els.editPromptBtn.disabled = loading || updating || !draft
    els.editPromptBtn.textContent = promptEditing ? "Editing..." : "Edit"
  }
  if (els.copyPromptBtn) {
    const promptForCopy = currentPromptForCopy(workflow)
    const canCopy = Boolean(promptForCopy) && !loading && !updating
    els.copyPromptBtn.disabled = !canCopy
  }
  if (els.savePromptEditBtn) {
    els.savePromptEditBtn.disabled = loading || updating || !promptEditing
  }
  if (els.cancelPromptEditBtn) {
    els.cancelPromptEditBtn.disabled = loading || updating || !promptEditing
  }
  if (els.llmPromptTile) {
    els.llmPromptTile.style.display = promptEditing ? "none" : "block"
  }

  if (loading || updating) {
    renderProcessMapFlowTile(draft, true)
    els.llmPromptTile.textContent = "Drafting your instructions..."
    els.postitMeta.innerHTML = `<div class="meta-row">${updating ? "Updating flow diagram and prompt..." : "Drafting automation package..."}</div>`
  } else if (draft) {
    renderProcessMapFlowTile(draft, false)
    els.llmPromptTile.textContent = String(draft.llm_prompt || "No prompt payload returned.")
    els.postitMeta.innerHTML = `
      <div class="meta-row">Draft source: ${escapeHtml(String(source).toUpperCase())}</div>
      <div class="meta-row">Estimated time reclamation: ${fmtOne(draft.estimated_hours_saved_per_week || 0)} h/week</div>
      <div class="meta-row">Workflow: ${escapeHtml(draft.workflow_name || workflow.name)}</div>
      ${completed ? `<div class="meta-row">Status: COMPLETED</div>` : ""}
    `
  } else {
    renderProcessMapFlowTile(null, false, "Select a workflow and click automation suggested.")
    els.llmPromptTile.textContent = "Prompt payload will appear here."
    els.postitMeta.innerHTML = `<div class="meta-row">No workflow draft generated.</div>`
  }

  if (els.reviewSignBtn) {
    els.reviewSignBtn.disabled = loading || updating || completed
  }
  if (els.executeBtn) {
    els.executeBtn.disabled = loading || updating || completed
    els.executeBtn.textContent = completed ? "Automation Completed" : "Mark Automation Done"
  }
  els.postitSignature.textContent = completed ? "Completed" : signed ? "Approved for Claude" : ""
  els.postitSignature.classList.toggle("is-visible", completed || signed)
}

async function fetchAutomationDraft(workflow) {
  const workflowId = String(workflow?.id || "").trim()
  if (!workflowId) return
  if (state.automationDrafts[workflowId]) return
  if (state.loadingAutomationDrafts[workflowId]) return

  state.loadingAutomationDrafts[workflowId] = true
  if (state.currentAutomationWorkflowId === workflowId) renderPostitTiles(workflow)
  try {
    const resp = await fetch(
      `/api/workflows/automation-draft?workflow_id=${encodeURIComponent(workflowId)}&days=${encodeURIComponent(state.days)}`,
      {
        headers: { Accept: "application/json" },
        cache: "no-store",
      },
    )
    const payload = await resp.json()
    if (!payload?.ok) {
      throw new Error(payload?.error || `HTTP ${resp.status}`)
    }
    state.automationDrafts[workflowId] = payload
    state.automationDraftSources[workflowId] = String(payload.source || "heuristic")
  } catch (error) {
    state.automationDrafts[workflowId] = localAutomationDraft(workflow)
    state.automationDraftSources[workflowId] = "fallback"
  } finally {
    delete state.loadingAutomationDrafts[workflowId]
    if (state.currentAutomationWorkflowId === workflowId) {
      const live = workflowById(workflowId) || workflow
      renderPostitTiles(live)
    }
  }
}

async function applyProcessMapEdit(workflow, instructionText) {
  const workflowId = String(workflow?.id || "").trim()
  if (!workflowId) return
  const instruction = String(instructionText || "").trim()
  if (!instruction) {
    setStatus("Add an edit instruction before updating the flow.", true)
    return
  }
  const baseDraft = state.automationDrafts[workflowId]
  if (!baseDraft) {
    setStatus("Generate an automation draft before editing the process map.", true)
    return
  }

  state.processMapUpdating = true
  if (state.currentAutomationWorkflowId === workflowId) renderPostitTiles(workflow)
  try {
    const resp = await fetch("/api/workflows/automation-draft/edit", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        workflow_id: workflowId,
        days: state.days,
        instruction,
        draft: baseDraft,
      }),
      cache: "no-store",
    })
    const payload = await resp.json()
    if (!resp.ok || !payload?.ok) {
      throw new Error(payload?.error || `HTTP ${resp.status}`)
    }
    state.automationDrafts[workflowId] = payload
    state.automationDraftSources[workflowId] = String(payload.source || "llm-edit")
    state.processMapEditing = false
    state.processMapEditText = ""
    if (state.currentAutomationWorkflowId === workflowId) renderPostitTiles(workflow)
    setStatus("Flow diagram and LLM prompt updated from your instruction.")
  } catch (error) {
    state.automationDrafts[workflowId] = localEditedAutomationDraft(baseDraft, workflow, instruction)
    state.automationDraftSources[workflowId] = "fallback-edit"
    state.processMapEditing = false
    state.processMapEditText = ""
    if (state.currentAutomationWorkflowId === workflowId) renderPostitTiles(workflow)
    setStatus(`LLM edit unavailable, applied local edit fallback: ${error instanceof Error ? error.message : "unknown error"}`, true)
  } finally {
    state.processMapUpdating = false
    if (state.currentAutomationWorkflowId === workflowId) renderPostitTiles(workflow)
  }
}

function startPromptEdit(workflow) {
  const workflowId = String(workflow?.id || "").trim()
  if (!workflowId) return
  const draft = state.automationDrafts[workflowId]
  if (!draft) return
  state.promptEditing = true
  state.promptEditText = String(draft.llm_prompt || "")
  renderPostitTiles(workflow)
  if (els.promptEditInput) els.promptEditInput.focus()
}

function cancelPromptEdit(workflow) {
  state.promptEditing = false
  state.promptEditText = ""
  if (workflow) renderPostitTiles(workflow)
}

function savePromptEdit(workflow) {
  const workflowId = String(workflow?.id || "").trim()
  if (!workflowId) return
  const draft = state.automationDrafts[workflowId]
  if (!draft) return
  const nextText = String(els.promptEditInput?.value || state.promptEditText || "").trim()
  if (!nextText) {
    setStatus("Prompt cannot be empty.", true)
    return
  }
  draft.llm_prompt = nextText
  state.automationDrafts[workflowId] = draft
  state.automationDraftSources[workflowId] = "user-edit"
  state.promptEditing = false
  state.promptEditText = ""
  renderPostitTiles(workflow)
  setStatus("Suggested prompt updated.")
}

function currentPromptForCopy(workflow) {
  const workflowId = String(workflow?.id || "").trim()
  if (!workflowId) return ""
  if (state.promptEditing && state.currentAutomationWorkflowId === workflowId) {
    return String(els.promptEditInput?.value || state.promptEditText || "").trim()
  }
  const draft = state.automationDrafts[workflowId]
  return String(draft?.llm_prompt || "").trim()
}

function openPostit(workflow) {
  if (!state.payload) return
  const allWorkflows = derivedWorkflows(state.payload || {})
  const fallback = allWorkflows.find((row) => !isWorkflowCompleted(row)) || allWorkflows[0] || null
  const selected = workflow || fallback
  if (!selected) return
  state.currentAutomationWorkflowId = String(selected.id || "")
  state.processMapEditing = false
  state.processMapEditText = ""
  state.promptEditing = false
  state.promptEditText = ""
  renderPostitTiles(selected)
  fetchAutomationDraft(selected)
  els.postitPanel.classList.add("is-open")
}

function closePostit() {
  state.processMapEditing = false
  state.processMapEditText = ""
  state.promptEditing = false
  state.promptEditText = ""
  els.postitPanel.classList.remove("is-open")
}

async function reviewAndSign() {
  const workflowId = String(state.currentAutomationWorkflowId || "").trim()
  if (!workflowId) {
    setStatus("Select a workflow before signing automation instructions.", true)
    return
  }
  const workflow = workflowById(workflowId)
  if (!workflow) {
    setStatus("Workflow not found in current ledger snapshot.", true)
    return
  }
  if (!state.automationDrafts[workflowId]) {
    await fetchAutomationDraft(workflow)
  }

  const draft = state.automationDrafts[workflowId]
  if (!draft) {
    setStatus("Automation draft generation failed. Try again.", true)
    return
  }

  const promptText = String(draft.llm_prompt || "").trim()
  let copied = false
  if (promptText && navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(promptText)
      copied = true
    } catch (error) {
      copied = false
    }
  }
  state.signedAutomationIds[workflowId] = true
  state.approvedWorkflowIds[workflowId] = true
  if (state.payload) renderOverview(state.payload)
  renderPostitTiles(workflow)
  if (copied) {
    setStatus("Automation draft reviewed, signed, and copied to clipboard.")
  } else {
    setStatus("Automation draft reviewed and signed. Clipboard copy unavailable on this browser.")
  }
}

async function fetchWorkflowNarrative(workflow) {
  const workflowId = String(workflow?.id || "").trim()
  if (!workflowId) return
  if (state.workflowNarratives[workflowId]) return
  if (state.loadingNarratives[workflowId]) return

  state.loadingNarratives[workflowId] = true
  if (state.payload) renderOverview(state.payload)
  try {
    const resp = await fetch(
      `/api/workflows/explain?workflow_id=${encodeURIComponent(workflowId)}&days=${encodeURIComponent(state.days)}`,
      {
        headers: { Accept: "application/json" },
        cache: "no-store",
      },
    )
    const payload = await resp.json()
    if (!payload?.ok || !payload?.summary) {
      throw new Error(payload?.error || `HTTP ${resp.status}`)
    }
    state.workflowNarratives[workflowId] = String(payload.summary)
    state.narrativeSources[workflowId] = String(payload.source || "heuristic")
    state.workflowNarrativeConfidence[workflowId] = String(payload.confidence || "")
    state.workflowNarrativeEvidence[workflowId] = Array.isArray(payload.evidence)
      ? payload.evidence.map((row) => String(row || "").trim()).filter(Boolean).slice(0, 4)
      : []
    if (state.selectedWorkflowId === workflowId && state.payload) renderOverview(state.payload)
  } catch (error) {
    state.workflowNarratives[workflowId] = String(workflow?.details || "")
    state.narrativeSources[workflowId] = "fallback"
    state.workflowNarrativeConfidence[workflowId] = ""
    state.workflowNarrativeEvidence[workflowId] = []
  } finally {
    delete state.loadingNarratives[workflowId]
    if (state.selectedWorkflowId === workflowId && state.payload) renderOverview(state.payload)
  }
}

function renderOverview(payload) {
  updateTimeframeHeadings()
  renderPerformanceLegend()
  const derived = derivedWorkflows(payload)
  const visible = filteredWorkflows(derived)
  if (state.detailOpen && (!state.selectedWorkflowId || !visible.find((row) => row.id === state.selectedWorkflowId))) {
    state.detailOpen = false
    state.selectedWorkflowId = ""
  }
  const selected = state.detailOpen ? visible.find((row) => row.id === state.selectedWorkflowId) || null : null
  const weekly = payload?.weekly_horizon || {}
  renderMonthFilter(weekly)
  renderDaySelector(weekly)
  renderLedgerChart(weekly)
  renderWorkflowCards(derived, payload?.tool_usage || [])
  renderWorkflowTable(visible)
  renderDetailPanel(selected)
  syncTopRowModuleHeights()
  if (selected) fetchWorkflowNarrative(selected)
}

function renderAll() {
  if (!state.payload) return
  renderTabs()
  renderOverview(state.payload)
  renderSources(state.payload)
  renderAutomationIdeas(state.payload)
  renderCompletedAutomations(state.payload)
  if (els.postitPanel.classList.contains("is-open")) {
    const allWorkflows = derivedWorkflows(state.payload)
    const current =
      workflowById(state.currentAutomationWorkflowId) || allWorkflows.find((row) => !isWorkflowCompleted(row)) || allWorkflows[0] || null
    if (current) {
      state.currentAutomationWorkflowId = current.id
      renderPostitTiles(current)
      if (!state.automationDrafts[current.id] && !state.loadingAutomationDrafts[current.id]) {
        fetchAutomationDraft(current)
      }
    }
  }
  if (isToolAnalysisPopupOpen()) {
    renderToolAnalysisPopup()
  }
}

async function loadInsights() {
  if (state.loading) {
    state.pendingReload = true
    return
  }
  const requestDays = Math.max(1, Math.min(90, toNumber(state.days, 7)))
  const requestMeta = timeframeMeta(requestDays)
  state.loading = true
  state.pendingReload = false
  els.refreshBtn.disabled = true
  setStatus(`Building ${requestMeta.periodWord} ledger and workflow intelligence...`)
  try {
    const resp = await fetch(`/api/workflows/insights?days=${encodeURIComponent(requestDays)}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const payload = await resp.json()
    if (state.days !== requestDays) {
      state.pendingReload = true
      return
    }
    state.payload = payload
    state.workflowNarratives = {}
    state.narrativeSources = {}
    state.loadingNarratives = {}
    state.automationDrafts = {}
    state.automationDraftSources = {}
    state.loadingAutomationDrafts = {}
    state.signedAutomationIds = {}
    state.currentAutomationWorkflowId = ""
    state.editingWorkflowNameId = ""
    state.workflowNameDraft = ""
    state.detailOpen = false
    state.selectedWorkflowId = ""
    state.selectedMonthKey = ""
    const horizonRows = Array.isArray(state.payload?.weekly_horizon?.current_week) ? state.payload.weekly_horizon.current_week : []
    state.selectedDayIndex = Math.max(0, horizonRows.length - 1)
    renderAll()
    const aw = (state.payload.scan?.sources || []).find((row) => row.kind === "activitywatch")
    if (aw?.available === false) {
      setStatus(`ActivityWatch unavailable: ${aw.error || "unknown error"}`, true)
    } else {
      setStatus(`${requestMeta.performanceHeading} updated. Events analyzed: ${fmtInt(state.payload.scan?.events_analyzed || 0)}.`)
    }
  } catch (error) {
    setStatus(`Failed to load insights: ${error instanceof Error ? error.message : "unknown error"}`, true)
  } finally {
    state.loading = false
    els.refreshBtn.disabled = false
    if (state.pendingReload) {
      state.pendingReload = false
      loadInsights()
    }
  }
}

els.tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    state.activeTab = btn.dataset.tab || "overview"
    renderTabs()
    if (state.activeTab !== "overview" && isToolAnalysisPopupOpen()) {
      closeToolAnalysisPopup()
    }
    if (state.activeTab === "overview") {
      requestAnimationFrame(() => {
        syncTopRowModuleHeights()
      })
    }
  })
})

if (els.distributionHeading) {
  els.distributionHeading.addEventListener("click", () => {
    openToolAnalysisPopup()
  })
  els.distributionHeading.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      openToolAnalysisPopup()
    }
  })
}

if (els.closeToolAnalysisPopupBtn) {
  els.closeToolAnalysisPopupBtn.addEventListener("click", () => {
    closeToolAnalysisPopup(true)
  })
}

if (els.toolAnalysisPopupOverlay) {
  els.toolAnalysisPopupOverlay.addEventListener("click", (event) => {
    if (event.target === els.toolAnalysisPopupOverlay) {
      closeToolAnalysisPopup(true)
    }
  })
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return
  if (isToolAnalysisPopupOpen()) {
    closeToolAnalysisPopup(true)
  }
})

els.searchInput.addEventListener("input", () => {
  state.search = els.searchInput.value || ""
  if (state.payload) renderOverview(state.payload)
})

els.daysSelect.addEventListener("change", () => {
  state.days = toNumber(els.daysSelect.value, 7)
  loadInsights()
})

if (els.monthSelect) {
  els.monthSelect.addEventListener("change", () => {
    state.selectedMonthKey = String(els.monthSelect.value || "")
    state.selectedDayIndex = 0
    if (state.payload) {
      renderDaySelector(state.payload.weekly_horizon)
      renderLedgerChart(state.payload.weekly_horizon)
    }
  })
}

els.refreshBtn.addEventListener("click", () => {
  loadInsights()
})

els.daySelector.addEventListener("click", (event) => {
  const btn = event.target.closest("button.day-chip")
  if (!btn) return
  state.selectedDayIndex = toNumber(btn.dataset.dayIndex, state.selectedDayIndex)
  if (state.payload) {
    renderDaySelector(state.payload.weekly_horizon)
    renderLedgerChart(state.payload.weekly_horizon)
  }
})

els.workflowRows.addEventListener("click", (event) => {
  const editBtn = event.target.closest("button[data-workflow-name-edit]")
  if (editBtn) {
    const workflowId = String(editBtn.dataset.workflowNameEdit || "")
    if (!workflowId) return
    startWorkflowNameEdit(workflowId)
    return
  }
  const saveBtn = event.target.closest("button[data-workflow-name-save]")
  if (saveBtn) {
    const workflowId = String(saveBtn.dataset.workflowNameSave || "")
    if (!workflowId) return
    const input = [...els.workflowRows.querySelectorAll("input[data-workflow-name-input]")].find(
      (node) => String(node.dataset.workflowNameInput || "") === workflowId,
    )
    state.workflowNameDraft = sanitizeWorkflowDisplayName(String(input?.value || state.workflowNameDraft || ""))
    saveWorkflowNameEdit(workflowId)
    return
  }
  const cancelBtn = event.target.closest("button[data-workflow-name-cancel]")
  if (cancelBtn) {
    cancelWorkflowNameEdit()
    return
  }
  const resetBtn = event.target.closest("button[data-workflow-name-reset]")
  if (resetBtn) {
    const workflowId = String(resetBtn.dataset.workflowNameReset || "")
    if (!workflowId) return
    delete state.workflowNameOverrides[workflowId]
    persistWorkflowNameOverrides(state.workflowNameOverrides)
    cancelWorkflowNameEdit()
    return
  }
  if (event.target.closest("input[data-workflow-name-input]")) {
    return
  }
  const row = event.target.closest("tr[data-workflow-id]")
  if (!row) return
  state.selectedWorkflowId = String(row.dataset.workflowId || "")
  state.detailOpen = true
  if (state.payload) renderOverview(state.payload)
})

els.workflowRows.addEventListener("input", (event) => {
  const input = event.target.closest("input[data-workflow-name-input]")
  if (!input) return
  state.workflowNameDraft = sanitizeWorkflowDisplayName(String(input.value || ""))
})

els.workflowRows.addEventListener("keydown", (event) => {
  const input = event.target.closest("input[data-workflow-name-input]")
  if (!input) return
  if (event.key === "Enter") {
    event.preventDefault()
    const workflowId = String(input.dataset.workflowNameInput || "")
    if (!workflowId) return
    state.workflowNameDraft = sanitizeWorkflowDisplayName(String(input.value || ""))
    saveWorkflowNameEdit(workflowId)
    return
  }
  if (event.key === "Escape") {
    event.preventDefault()
    cancelWorkflowNameEdit()
  }
})

els.detailPanel.addEventListener("click", (event) => {
  const closeBtn = event.target.closest("button[data-detail-close]")
  if (closeBtn) {
    state.detailOpen = false
    state.selectedWorkflowId = ""
    state.editingNarrativeWorkflowId = ""
    state.narrativeDraftText = ""
    if (state.payload) renderOverview(state.payload)
    return
  }
  const editBtn = event.target.closest("button[data-narrative-edit]")
  if (editBtn) {
    const workflowId = String(editBtn.dataset.narrativeEdit || "")
    if (!workflowId) return
    const workflow = workflowById(workflowId)
    if (!workflow) return
    const baseline =
      String(state.narrativeOverrides[workflowId] || "").trim() ||
      String(state.workflowNarratives[workflowId] || "").trim() ||
      String(workflow.details || "").trim()
    state.editingNarrativeWorkflowId = workflowId
    state.narrativeDraftText = baseline
    if (state.payload) renderOverview(state.payload)
    return
  }
  const saveBtn = event.target.closest("button[data-narrative-save]")
  if (saveBtn) {
    const workflowId = String(saveBtn.dataset.narrativeSave || "")
    if (!workflowId) return
    const editor = els.detailPanel.querySelector("textarea[data-narrative-input]")
    const text = String(editor?.value || state.narrativeDraftText || "").trim()
    if (text) {
      state.narrativeOverrides[workflowId] = text
    } else {
      delete state.narrativeOverrides[workflowId]
    }
    persistNarrativeOverrides(state.narrativeOverrides)
    state.editingNarrativeWorkflowId = ""
    state.narrativeDraftText = ""
    if (state.payload) renderOverview(state.payload)
    return
  }
  const cancelBtn = event.target.closest("button[data-narrative-cancel]")
  if (cancelBtn) {
    state.editingNarrativeWorkflowId = ""
    state.narrativeDraftText = ""
    if (state.payload) renderOverview(state.payload)
    return
  }
  const resetBtn = event.target.closest("button[data-narrative-reset]")
  if (resetBtn) {
    const workflowId = String(resetBtn.dataset.narrativeReset || "")
    if (!workflowId) return
    delete state.narrativeOverrides[workflowId]
    persistNarrativeOverrides(state.narrativeOverrides)
    if (state.payload) renderOverview(state.payload)
    return
  }
})

els.detailPanel.addEventListener("input", (event) => {
  const editor = event.target.closest("textarea[data-narrative-input]")
  if (!editor) return
  state.narrativeDraftText = String(editor.value || "")
})

if (els.automationIdeas) {
  els.automationIdeas.addEventListener("click", (event) => {
    const btn = event.target.closest("button[data-open-workflow-id]")
    if (!btn) return
    const workflowId = String(btn.dataset.openWorkflowId || "").trim()
    if (!workflowId) return
    const workflow = workflowById(workflowId)
    if (!workflow) {
      setStatus("Workflow not found for automation suggestion.", true)
      return
    }
    openPostit(workflow)
  })
}

els.closePostitBtn.addEventListener("click", () => {
  closePostit()
})

if (els.editProcessMapBtn) {
  els.editProcessMapBtn.addEventListener("click", () => {
    const workflowId = String(state.currentAutomationWorkflowId || "").trim()
    const workflow = workflowById(workflowId)
    if (!workflow) return
    const draft = state.automationDrafts[workflowId]
    if (!draft) return
    state.processMapEditing = true
    state.processMapEditText = state.processMapEditText || ""
    renderPostitTiles(workflow)
    if (els.processMapEditInput) els.processMapEditInput.focus()
  })
}

if (els.cancelProcessMapEditBtn) {
  els.cancelProcessMapEditBtn.addEventListener("click", () => {
    const workflowId = String(state.currentAutomationWorkflowId || "").trim()
    const workflow = workflowById(workflowId)
    state.processMapEditing = false
    state.processMapEditText = ""
    if (workflow) renderPostitTiles(workflow)
  })
}

if (els.applyProcessMapEditBtn) {
  els.applyProcessMapEditBtn.addEventListener("click", async () => {
    const workflowId = String(state.currentAutomationWorkflowId || "").trim()
    const workflow = workflowById(workflowId)
    if (!workflow) return
    const instruction = String(els.processMapEditInput?.value || state.processMapEditText || "").trim()
    await applyProcessMapEdit(workflow, instruction)
  })
}

if (els.processMapEditInput) {
  els.processMapEditInput.addEventListener("input", () => {
    state.processMapEditText = String(els.processMapEditInput?.value || "")
  })
}

if (els.editPromptBtn) {
  els.editPromptBtn.addEventListener("click", () => {
    const workflowId = String(state.currentAutomationWorkflowId || "").trim()
    const workflow = workflowById(workflowId)
    if (!workflow) return
    startPromptEdit(workflow)
  })
}

if (els.copyPromptBtn) {
  els.copyPromptBtn.addEventListener("click", async () => {
    const workflowId = String(state.currentAutomationWorkflowId || "").trim()
    const workflow = workflowById(workflowId)
    if (!workflow) {
      setStatus("Open an automation suggestion first.", true)
      return
    }
    const promptText = currentPromptForCopy(workflow)
    if (!promptText) {
      setStatus("No prompt available to copy yet.", true)
      return
    }
    const copied = await copyTextToClipboard(promptText)
    if (copied) {
      setStatus("LLM prompt copied to clipboard.")
    } else {
      setStatus("Could not copy prompt on this browser.", true)
    }
  })
}

if (els.cancelPromptEditBtn) {
  els.cancelPromptEditBtn.addEventListener("click", () => {
    const workflowId = String(state.currentAutomationWorkflowId || "").trim()
    const workflow = workflowById(workflowId)
    cancelPromptEdit(workflow)
  })
}

if (els.savePromptEditBtn) {
  els.savePromptEditBtn.addEventListener("click", () => {
    const workflowId = String(state.currentAutomationWorkflowId || "").trim()
    const workflow = workflowById(workflowId)
    if (!workflow) return
    savePromptEdit(workflow)
  })
}

if (els.promptEditInput) {
  els.promptEditInput.addEventListener("input", () => {
    state.promptEditText = String(els.promptEditInput?.value || "")
  })
}

if (els.reviewSignBtn) {
  els.reviewSignBtn.addEventListener("click", () => {
    reviewAndSign()
  })
}

els.executeBtn.addEventListener("click", () => {
  const workflowId = String(state.currentAutomationWorkflowId || state.selectedWorkflowId || "").trim()
  if (!workflowId) {
    setStatus("Select a workflow before marking automation as done.", true)
    return
  }
  const workflow = workflowById(workflowId)
  if (!workflow) {
    setStatus("Workflow not found in current view.", true)
    return
  }
  markAutomationDone(workflow)
})

window.addEventListener("resize", () => {
  if (!state.payload) return
  syncTopRowModuleHeights()
})

window.addEventListener("load", () => {
  if (!state.payload) return
  syncTopRowModuleHeights()
  window.setTimeout(() => {
    syncTopRowModuleHeights()
  }, 140)
})

loadInsights()
