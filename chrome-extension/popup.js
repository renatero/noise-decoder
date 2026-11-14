import { extractVisibleEvents } from "./extractor.js";
import { buildClusters, detectTimeBursts, enrichEvents } from "./features.mjs";

const DEFAULT_ENDPOINT = "http://localhost:8000/analyze";
const extractionStatus = document.querySelector("#extraction-status");
const review = document.querySelector("#review");
const eventCount = document.querySelector("#event-count");
const payload = document.querySelector("#payload");
const analysis = document.querySelector("#analysis");
const analysisMode = document.querySelector("#analysis-mode");
const analysisResult = document.querySelector("#analysis-result");

let collected = [];
let clusters = [];
let timeWindowAnalysis = {
  config: { window_minutes: 60, minimum_accounts: 2 },
  bursts: [],
  statistics: { events_with_valid_timestamps: 0, excluded_invalid_timestamps: 0, posts_without_account_id: 0 }
};

function format(value) {
  return JSON.stringify(value, null, 2);
}

function mockAnalysis(events, clusters, timeAnalysis, reason) {
  return {
    status: events.length < 2 ? "insufficient_data" : "inconclusive",
    nodes: [...new Map(events.map((event) => [event.actor_id, { id: event.actor_id, platform: event.platform }])).values()],
    edges: [],
    clusters,
    time_window_analysis: timeAnalysis,
    evidence: [],
    statistics: {
      events_analyzed: events.length,
      actors_analyzed: new Set(events.map((event) => event.actor_id)).size,
      groups_found: clusters.length,
      time_bursts_found: timeAnalysis.bursts.length,
      excluded_invalid_timestamps: timeAnalysis.statistics.excluded_invalid_timestamps
    },
    limitations: [
      "Mock response: the detector API is not available yet.",
      "Groups are based only on shared canonical URLs or similar text; they are not evidence of coordination by themselves.",
      "Time-window bursts describe observed timing and account patterns; they do not establish coordination or intent.",
      "Account identifiers may be derived from visible display names and may not uniquely identify accounts.",
      "Visible-page extraction is incomplete and should be reviewed before drawing conclusions.",
      reason
    ]
  };
}

function renderCollected() {
  review.hidden = collected.length === 0;
  eventCount.textContent = `${collected.length} event${collected.length === 1 ? "" : "s"}`;
  payload.textContent = format({ events: collected, clusters, time_window_analysis: timeWindowAnalysis });
}

document.querySelector("#extract").addEventListener("click", async () => {
  extractionStatus.textContent = "Extracting visible posts…";
  analysis.hidden = true;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab.id || !tab.url?.startsWith("http")) throw new Error("Open a public website in the active tab first.");
    const [result] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractVisibleEvents });
    collected = enrichEvents(result.result.events);
    clusters = buildClusters(collected);
    const { windowMinutes = 60, minimumAccounts = 2 } = await chrome.storage.sync.get({ windowMinutes: 60, minimumAccounts: 2 });
    timeWindowAnalysis = detectTimeBursts(collected, clusters, { windowMinutes, minimumAccounts });
    extractionStatus.textContent = collected.length
      ? `Collected ${collected.length} visible posts from ${result.result.platform}; found ${clusters.length} related group${clusters.length === 1 ? "" : "s"} and ${timeWindowAnalysis.bursts.length} time-window burst${timeWindowAnalysis.bursts.length === 1 ? "" : "s"}. Review the payload before sending.`
      : "No supported visible posts were found on this page.";
    renderCollected();
  } catch (error) {
    collected = [];
    clusters = [];
    timeWindowAnalysis = detectTimeBursts([], [], {});
    renderCollected();
    extractionStatus.textContent = `Could not extract posts: ${error.message}`;
  }
});

document.querySelector("#clear").addEventListener("click", () => {
  collected = [];
  clusters = [];
  timeWindowAnalysis = detectTimeBursts([], [], {});
  analysis.hidden = true;
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
      body: JSON.stringify({ events: collected, clusters, time_window_analysis: timeWindowAnalysis })
    });
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const report = await response.json();
    analysisMode.textContent = `Detector response from ${endpoint}`;
    analysisResult.textContent = format(report);
  } catch (error) {
    analysisMode.textContent = "Showing a mock detector response — the API could not be reached.";
    analysisResult.textContent = format(mockAnalysis(collected, clusters, timeWindowAnalysis, error.message));
  }
});
