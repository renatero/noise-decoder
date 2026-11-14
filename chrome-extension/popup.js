import { extractVisibleEvents } from "./extractor.js";

const DEFAULT_ENDPOINT = "http://localhost:8000/analyze";
const extractionStatus = document.querySelector("#extraction-status");
const review = document.querySelector("#review");
const eventCount = document.querySelector("#event-count");
const payload = document.querySelector("#payload");
const analysis = document.querySelector("#analysis");
const analysisMode = document.querySelector("#analysis-mode");
const analysisResult = document.querySelector("#analysis-result");

let collected = [];

function format(value) {
  return JSON.stringify(value, null, 2);
}

function mockAnalysis(events, reason) {
  return {
    status: events.length < 2 ? "insufficient_data" : "inconclusive",
    nodes: [...new Map(events.map((event) => [event.actor_id, { id: event.actor_id, platform: event.platform }])).values()],
    edges: [],
    clusters: [],
    evidence: [],
    statistics: { events_analyzed: events.length, actors_analyzed: new Set(events.map((event) => event.actor_id)).size },
    limitations: [
      "Mock response: the detector API is not available yet.",
      "Visible-page extraction is incomplete and should be reviewed before drawing conclusions.",
      reason
    ]
  };
}

function renderCollected() {
  review.hidden = collected.length === 0;
  eventCount.textContent = `${collected.length} event${collected.length === 1 ? "" : "s"}`;
  payload.textContent = format({ events: collected });
}

document.querySelector("#extract").addEventListener("click", async () => {
  extractionStatus.textContent = "Extracting visible posts…";
  analysis.hidden = true;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab.id || !tab.url?.startsWith("http")) throw new Error("Open a public website in the active tab first.");
    const [result] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractVisibleEvents });
    collected = result.result.events;
    extractionStatus.textContent = collected.length
      ? `Collected ${collected.length} visible posts from ${result.result.platform}. Review the payload before sending.`
      : "No supported visible posts were found on this page.";
    renderCollected();
  } catch (error) {
    collected = [];
    renderCollected();
    extractionStatus.textContent = `Could not extract posts: ${error.message}`;
  }
});

document.querySelector("#clear").addEventListener("click", () => {
  collected = [];
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
      body: JSON.stringify({ events: collected })
    });
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const report = await response.json();
    analysisMode.textContent = `Detector response from ${endpoint}`;
    analysisResult.textContent = format(report);
  } catch (error) {
    analysisMode.textContent = "Showing a mock detector response — the API could not be reached.";
    analysisResult.textContent = format(mockAnalysis(collected, error.message));
  }
});
