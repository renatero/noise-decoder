import { extractVisibleEvents } from "./extractor.js";
import { buildClusters, enrichEvents } from "./features.mjs";
import { sourceForUrl } from "./sources.js";

const DEFAULT_ENDPOINT = "http://127.0.0.1:8000/analyze";
const extractionStatus = document.querySelector("#extraction-status");
const inspectionStatus = document.querySelector("#inspection-status");
const review = document.querySelector("#review");
const eventCount = document.querySelector("#event-count");
const payload = document.querySelector("#payload");
const analysis = document.querySelector("#analysis");
const analysisMode = document.querySelector("#analysis-mode");
const analysisResult = document.querySelector("#analysis-result");

let collected = [];
let clusters = [];

function format(value) {
  return JSON.stringify(value, null, 2);
}

function mockAnalysis(events, candidateClusters, reason) {
  const identifiedActors = events.filter((event) => event.actor_id);
  return {
    status: events.length < 2 ? "insufficient_data" : "inconclusive",
    nodes: [...new Map(identifiedActors.map((event) => [event.actor_id, { id: event.actor_id, platform: event.platform }])).values()],
    edges: [],
    clusters: candidateClusters,
    evidence: [],
    statistics: {
      events_analyzed: events.length,
      actors_analyzed: new Set(identifiedActors.map((event) => event.actor_id)).size,
      groups_found: candidateClusters.length
    },
    limitations: [
      "Mock response: the detector API is not available yet.",
      "Groups are based only on shared canonical URLs or similar text; they are not evidence of coordination by themselves.",
      "Visible-page extraction is incomplete and should be reviewed before drawing conclusions.",
      reason
    ]
  };
}

function updateDerivedData(events) {
  collected = enrichEvents(events);
  clusters = buildClusters(collected);
}

function renderCollected() {
  review.hidden = collected.length === 0;
  eventCount.textContent = `${collected.length} event${collected.length === 1 ? "" : "s"}`;
  payload.textContent = format({ events: collected, clusters });
}

async function loadPendingInspection() {
  const { pendingInspection } = await chrome.storage.local.get("pendingInspection");
  if (!pendingInspection?.event) return;
  updateDerivedData([pendingInspection.event]);
  const source = pendingInspection.source?.source_name || pendingInspection.event.platform;
  inspectionStatus.textContent = `Right-click ${pendingInspection.kind} inspection loaded from ${source}. Review it, then send it for analysis.`;
  extractionStatus.textContent = "A context-menu inspection is ready.";
  renderCollected();
}

document.querySelector("#extract").addEventListener("click", async () => {
  extractionStatus.textContent = "Extracting visible posts…";
  analysis.hidden = true;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab.id || !tab.url?.startsWith("http")) throw new Error("Open a public website in the active tab first.");
    const [result] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractVisibleEvents });
    updateDerivedData(result.result.events);
    const source = sourceForUrl(tab.url);
    inspectionStatus.textContent = source?.source_name ? `Recognized source: ${source.source_name}.` : "";
    extractionStatus.textContent = collected.length
      ? `Collected ${collected.length} visible posts from ${result.result.platform}; found ${clusters.length} candidate group${clusters.length === 1 ? "" : "s"}. Review the payload before sending.${result.result.limitations?.length ? ` ${result.result.limitations[0]}` : ""}`
      : "No supported visible posts were found on this page.";
    renderCollected();
  } catch (error) {
    collected = [];
    clusters = [];
    renderCollected();
    extractionStatus.textContent = `Could not extract posts: ${error.message}`;
  }
});

document.querySelector("#clear").addEventListener("click", () => {
  collected = [];
  clusters = [];
  analysis.hidden = true;
  inspectionStatus.textContent = "";
  chrome.storage.local.remove("pendingInspection");
  extractionStatus.textContent = "Collected events cleared.";
  renderCollected();
});

document.querySelector("#analyze").addEventListener("click", async () => {
  const { endpoint = DEFAULT_ENDPOINT } = await chrome.storage.sync.get({ endpoint: DEFAULT_ENDPOINT });
  analysis.hidden = false;
  analysisMode.textContent = "Sending events to the configured detector…";
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: collected, clusters })
    });
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const report = await response.json();
    analysisMode.textContent = `Detector response from ${endpoint}`;
    analysisResult.textContent = format(report);
  } catch (error) {
    analysisMode.textContent = "Showing a mock detector response — the API could not be reached.";
    analysisResult.textContent = format(mockAnalysis(collected, clusters, error.message));
  }
});

loadPendingInspection();
