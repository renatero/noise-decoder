import { extractVisibleEvents } from "./extractor.js";
import { buildClusters, buildWeightedActorGraph, canonicalizeUrl, detectTimeBursts, enrichEvents, recordCoActivity, runPermutationNullModel } from "./features.mjs";
import { getApiEndpoint } from "./settings.js";
const extractionStatus = document.querySelector("#extraction-status");
const review = document.querySelector("#review");
const eventCount = document.querySelector("#event-count");
const payload = document.querySelector("#payload");
const analysis = document.querySelector("#analysis");
const analysisMode = document.querySelector("#analysis-mode");
const analysisResult = document.querySelector("#analysis-result");

let collected = [];
let visiblePostCount = 0;
let blueskyPostCount = 0;
let clusters = [];
let timeWindowAnalysis = {
  config: { window_minutes: 60, minimum_accounts: 2 },
  bursts: [],
  statistics: { events_with_valid_timestamps: 0, excluded_invalid_timestamps: 0, posts_without_account_id: 0 }
};
let coActivity = { account_pairs: [], repeated_pairs: [], statistics: { account_pairs_seen: 0, repeated_pairs_found: 0 } };
let actorGraph = buildWeightedActorGraph([], [], { bursts: [] }, coActivity);
let permutationAnalysis = emptyPermutationAnalysis();

function format(value) {
  return JSON.stringify(value, null, 2);
}

function emptyPermutationAnalysis() {
  return {
    method: "stratified_actor_assignment_max_cluster_permutation",
    permutations: 199,
    seed: null,
    strongest_cluster: null,
    heuristic_suspicion_score: null,
    permutation_p_value: null,
    null_max_cluster_score: { mean: 0, standard_deviation: 0, percentile_95: 0, exceedances: null },
    strata: {},
    statistics: { observed_actor_clusters: 0, strongest_cluster_testable: false, minimum_p_value: 0.005, p_value_resolution: 0.005 },
    limitations: []
  };
}

function mockAnalysis(events, clusters, timeAnalysis, coActivityAnalysis, actorGraphResult, permutationResult, reason) {
  return {
    status: events.length < 2 ? "insufficient_data" : "inconclusive",
    nodes: actorGraphResult.nodes,
    edges: actorGraphResult.edges,
    clusters,
    time_window_analysis: timeAnalysis,
    co_activity: coActivityAnalysis,
    actor_graph: actorGraphResult,
    permutation_analysis: permutationResult,
    evidence: [],
    statistics: {
      events_analyzed: events.length,
      actors_analyzed: new Set(events.map((event) => event.actor_id)).size,
      groups_found: clusters.length,
      time_bursts_found: timeAnalysis.bursts.length,
      repeated_co_activity_pairs: coActivityAnalysis.statistics.repeated_pairs_found,
      weighted_actor_edges: actorGraphResult.statistics.weighted_edges,
      observed_actor_clusters: permutationResult.statistics.observed_actor_clusters,
      excluded_invalid_timestamps: timeAnalysis.statistics.excluded_invalid_timestamps
    },
    limitations: [
      "Mock response: the detector API is not available yet.",
      "Groups are based only on shared canonical URLs or similar text; they are not evidence of coordination by themselves.",
      "Time-window bursts describe observed timing and account patterns; they do not establish coordination or intent.",
      "Repeated co-activity is an observed recurrence across content groups or publication bursts; it does not establish coordination or intent.",
      "A single simultaneous response may reflect breaking news or another shared cause and is treated as limited evidence.",
      "Account identifiers may be derived from visible display names and may not uniquely identify accounts.",
      ...permutationResult.limitations,
      "Visible-page extraction is incomplete and should be reviewed before drawing conclusions.",
      reason
    ]
  };
}

function renderCollected() {
  review.hidden = collected.length === 0;
  eventCount.textContent = `${collected.length} event${collected.length === 1 ? "" : "s"}`;
  payload.textContent = format({ events: collected, clusters, time_window_analysis: timeWindowAnalysis, co_activity: coActivity, actor_graph: actorGraph, permutation_analysis: permutationAnalysis });
}

document.querySelector("#extract").addEventListener("click", async () => {
  extractionStatus.textContent = "Extracting visible posts and searching public Bluesky posts…";
  analysis.hidden = true;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab.id || !tab.url?.startsWith("http")) throw new Error("Open a public website in the active tab first.");
    const [result] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractVisibleEvents });
    const visibleEvents = result.result.events;
    visiblePostCount = visibleEvents.length;
    blueskyPostCount = 0;
    const endpoint = await getApiEndpoint();
    const discoveryUrl = new URL(endpoint);
    discoveryUrl.pathname = discoveryUrl.pathname.replace(/\/analyze\/?$/, "/discover");
    let discoveryLimitations = [];
    try {
      const discoveryResponse = await fetch(discoveryUrl.href, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: visibleEvents })
      });
      if (!discoveryResponse.ok) throw new Error(`Public search returned ${discoveryResponse.status}`);
      const discovery = await discoveryResponse.json();
      const seedUrls = new Set(visibleEvents.map((event) => canonicalizeUrl(event.url)).filter(Boolean));
      const candidates = (Array.isArray(discovery.events) ? discovery.events : [])
        .filter((event) => !seedUrls.has(canonicalizeUrl(event.url)));
      const expanded = enrichEvents([...visibleEvents, ...candidates]);
      const seedIds = new Set(visibleEvents.map((event) => event.post_id));
      const relevantIds = new Set(seedIds);
      for (const cluster of buildClusters(expanded)) {
        if (cluster.post_ids.some((postId) => seedIds.has(postId))) {
          cluster.post_ids.forEach((postId) => relevantIds.add(postId));
        }
      }
      const seedIdSet = new Set(visibleEvents.map((event) => event.post_id));
      blueskyPostCount = [...relevantIds].filter((postId) => !seedIdSet.has(postId)).length;
      collected = enrichEvents(expanded.filter((event) => relevantIds.has(event.post_id)));
      discoveryLimitations = discovery.limitations || [];
    } catch (error) {
      collected = enrichEvents(visibleEvents);
      discoveryLimitations = [`Bluesky public search was unavailable: ${error.message}`];
    }
    clusters = buildClusters(collected);
    const { windowMinutes = 60, minimumAccounts = 2 } = await chrome.storage.sync.get({ windowMinutes: 60, minimumAccounts: 2 });
    timeWindowAnalysis = detectTimeBursts(collected, clusters, { windowMinutes, minimumAccounts });
    coActivity = recordCoActivity(collected, clusters, timeWindowAnalysis);
    actorGraph = buildWeightedActorGraph(collected, clusters, timeWindowAnalysis, coActivity);
    permutationAnalysis = runPermutationNullModel(collected, clusters, timeWindowAnalysis, coActivity, actorGraph);
    extractionStatus.textContent = collected.length
      ? `Collected ${visiblePostCount} visible posts from ${result.result.platform} and found ${blueskyPostCount} related public Bluesky posts. Found ${clusters.length} related group${clusters.length === 1 ? "" : "s"}, ${timeWindowAnalysis.bursts.length} time-window burst${timeWindowAnalysis.bursts.length === 1 ? "" : "s"}, and ${coActivity.statistics.repeated_pairs_found} repeated co-activity pair${coActivity.statistics.repeated_pairs_found === 1 ? "" : "s"}. Compared the strongest actor cluster against 199 permutations; p-value ${permutationAnalysis.permutation_p_value ?? "unavailable"}. Review the evidence before sending. ${discoveryLimitations.join(" ")}`
      : "No supported visible posts were found on this page.";
    renderCollected();
  } catch (error) {
    collected = [];
    visiblePostCount = 0;
    blueskyPostCount = 0;
    clusters = [];
    timeWindowAnalysis = detectTimeBursts([], [], {});
    coActivity = recordCoActivity([], [], timeWindowAnalysis);
    actorGraph = buildWeightedActorGraph([], [], timeWindowAnalysis, coActivity);
    permutationAnalysis = emptyPermutationAnalysis();
    renderCollected();
    extractionStatus.textContent = `Could not extract posts: ${error.message}`;
  }
});

document.querySelector("#clear").addEventListener("click", () => {
  collected = [];
  visiblePostCount = 0;
  blueskyPostCount = 0;
  clusters = [];
  timeWindowAnalysis = detectTimeBursts([], [], {});
  coActivity = recordCoActivity([], [], timeWindowAnalysis);
  actorGraph = buildWeightedActorGraph([], [], timeWindowAnalysis, coActivity);
  permutationAnalysis = emptyPermutationAnalysis();
  analysis.hidden = true;
  extractionStatus.textContent = "Collected events cleared.";
  renderCollected();
});

document.querySelector("#analyze").addEventListener("click", async () => {
  const endpoint = await getApiEndpoint();
  analysis.hidden = false;
  analysisMode.textContent = "Sending events to the configured detector…";
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: collected, clusters, time_window_analysis: timeWindowAnalysis, co_activity: coActivity, actor_graph: actorGraph, permutation_analysis: permutationAnalysis })
    });
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const report = await response.json();
    analysisMode.textContent = `Detector response from ${endpoint}`;
    analysisResult.textContent = format(report);
  } catch (error) {
    analysisMode.textContent = "Showing a mock detector response — the API could not be reached.";
    analysisResult.textContent = format(mockAnalysis(collected, clusters, timeWindowAnalysis, coActivity, actorGraph, permutationAnalysis, error.message));
  }
});
