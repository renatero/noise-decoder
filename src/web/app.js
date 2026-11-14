const source = document.querySelector("#source");
const form = document.querySelector("#investigation-form");
const investigation = document.querySelector("#investigation");
const limit = document.querySelector("#limit");
const limitField = document.querySelector("#limit-field");
const importField = document.querySelector("#import-field");
const importFile = document.querySelector("#import-file");
const sourceHelp = document.querySelector("#source-help");
const requestStatus = document.querySelector("#request-status");
const reportSection = document.querySelector("#report-section");
const syntheticBanner = document.querySelector("#synthetic-banner");
const handoffNotice = document.querySelector("#handoff-notice");
const clusterFilter = document.querySelector("#cluster-filter");

let currentEvents = [];
let currentReport = null;
let graph = null;

const sourceDescriptions = {
  synthetic_coordinated: "336 reproducible fictional posts with recurring synchronized bursts across 12 demonstration accounts.",
  synthetic_benign: "336 reproducible fictional posts with an ordinary breaking-news reaction and coincidental timing.",
  live_bluesky: "A bounded unauthenticated query of public Bluesky search results. Coverage is incomplete and rate limits may apply.",
  offline_bluesky: "A saved, labelled public Bluesky search snapshot. It works without internet access.",
  json_import: "Upload an object containing an events array, or an array of normalized events from another source.",
};

function setSourceHelp() {
  const selected = source.value;
  sourceHelp.textContent = sourceDescriptions[selected];
  limitField.hidden = selected !== "live_bluesky";
  importField.hidden = selected !== "json_import";
}

function apiError(payload, fallback) {
  return payload?.detail || payload?.error || fallback;
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(apiError(payload, `Request failed (${response.status})`));
  return payload;
}

async function eventsForSource() {
  if (source.value.startsWith("synthetic_")) {
    const dataset = await request(`/api/datasets/${source.value}`);
    return { events: dataset.events, synthetic: true, label: dataset.scenario };
  }
  if (source.value === "live_bluesky") {
    const query = investigation.value.trim();
    if (!query) throw new Error("Enter a search phrase before using live public data.");
    const payload = await request(`/api/collect/bluesky?query=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit.value)}`);
    return { events: payload.events, synthetic: false, label: "live public Bluesky search", limitations: payload.limitations };
  }
  if (source.value === "offline_bluesky") {
    const payload = await request("/api/snapshots/bluesky");
    return { events: payload.events, synthetic: false, label: "offline public Bluesky snapshot", limitations: [payload.notice, ...(payload.limitations || [])] };
  }
  if (!importFile.files?.[0]) throw new Error("Choose a normalized JSON file to import.");
  const text = await importFile.files[0].text();
  let parsed;
  try { parsed = JSON.parse(text); } catch { throw new Error("The import file is not valid JSON."); }
  const events = Array.isArray(parsed) ? parsed : parsed.events;
  if (!Array.isArray(events)) throw new Error("The import JSON must be an events array or an object with an events array.");
  const payload = await request("/api/import", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ events }),
  });
  return { events: payload.events, synthetic: false, label: "normalized JSON import", limitations: payload.limitations };
}

function itemList(container, values, emptyText, formatter = (value) => String(value)) {
  container.replaceChildren();
  if (!values?.length) { container.textContent = emptyText; return; }
  const list = document.createElement("ul");
  for (const value of values) {
    const item = document.createElement("li");
    const content = formatter(value);
    if (content instanceof Node) item.append(content); else item.textContent = content;
    list.append(item);
  }
  container.append(list);
}

function renderReport(report, metadata) {
  currentReport = report;
  reportSection.hidden = false;
  syntheticBanner.hidden = !metadata.synthetic;
  document.querySelector("#report-title").textContent = metadata.label;
  document.querySelector("#report-summary").textContent = report.summary || "No additional summary was returned.";
  const status = document.querySelector("#report-status");
  status.textContent = report.status.replaceAll("_", " ");
  status.className = `badge ${report.status}`;

  const statistics = document.querySelector("#statistics");
  statistics.replaceChildren();
  for (const [key, value] of Object.entries(report.statistics || {})) {
    const term = document.createElement("dt"); term.textContent = key.replaceAll("_", " ");
    const detail = document.createElement("dd"); detail.textContent = value === null ? "not available" : String(value);
    statistics.append(term, detail);
  }

  const clusterContainer = document.querySelector("#clusters");
  itemList(clusterContainer, report.clusters, "No repeated actor cluster was identified.", (cluster) => {
    const block = document.createElement("div");
    block.className = "cluster";
    const title = document.createElement("strong");
    title.textContent = cluster.id || "relationship group";
    const detail = document.createElement("p");
    detail.textContent = cluster.explanation || `${cluster.actor_ids?.length || 0} actors; ${cluster.repeated_coordination_events || 0} repeated evidence contexts.`;
    block.append(title, detail);
    return block;
  });
  itemList(document.querySelector("#limitations"), [...(metadata.limitations || []), ...(report.limitations || [])], "No limitations supplied.");
  itemList(document.querySelector("#evidence"), report.evidence, "No relationship evidence was identified.", (entry) => {
    const block = document.createElement("div");
    block.className = "evidence";
    block.textContent = `${entry.assessment || "evidence"}: ${(entry.shared_urls || []).join(", ") || "no shared URL"} · ${entry.event_ids?.length || 0} events`;
    return block;
  });
  populateClusterFilter(report.clusters || []);
  renderGraph();
}

function populateClusterFilter(clusters) {
  clusterFilter.replaceChildren(new Option("All actors", "all"));
  for (const cluster of clusters) {
    if (!cluster.actor_ids?.length) continue;
    clusterFilter.add(new Option(`${cluster.id} (${cluster.actor_ids.length} actors)`, cluster.id));
  }
}

function showGraphDetail(content) {
  const detail = document.querySelector("#graph-detail");
  detail.replaceChildren();
  if (typeof content === "string") { detail.textContent = content; return; }
  detail.append(content);
}

function renderGraph() {
  const container = document.querySelector("#graph");
  container.replaceChildren();
  if (!window.cytoscape) {
    showGraphDetail("The graph library could not be loaded. Report evidence remains available above.");
    return;
  }
  const selectedCluster = (currentReport.clusters || []).find((cluster) => cluster.id === clusterFilter.value);
  const allowedActors = selectedCluster?.actor_ids ? new Set(selectedCluster.actor_ids) : null;
  const strongEdges = (currentReport.edges || []).filter((edge) => edge.repeated && (!allowedActors || (allowedActors.has(edge.source) && allowedActors.has(edge.target))));
  const nodeIds = new Set(strongEdges.flatMap((edge) => [edge.source, edge.target]));
  const nodes = (currentReport.nodes || []).filter((node) => nodeIds.has(node.id));
  if (!nodes.length) {
    showGraphDetail("No recurring relationship is available for the current filter. One-off shared reactions remain inconclusive.");
    return;
  }
  graph = cytoscape({
    container,
    elements: [
      ...nodes.map((node) => ({ data: { id: node.id, label: node.id, eventCount: node.event_count || 0 } })),
      ...strongEdges.map((edge) => ({ data: { id: edge.id, source: edge.source, target: edge.target, weight: edge.weight } })),
    ],
    style: [
      { selector: "node", style: { "background-color": "#42b8a8", label: "data(label)", color: "#eaf3ff", "font-size": 10, "text-wrap": "wrap", "text-max-width": 100 } },
      { selector: "edge", style: { width: "mapData(weight, 1, 6, 2, 8)", "line-color": "#f1b85b", "target-arrow-color": "#f1b85b", "curve-style": "bezier", label: "data(weight)", color: "#f8d99b" } },
    ],
    layout: { name: "cose", animate: false, padding: 30 },
  });
  graph.on("tap", "node", (tap) => {
    const actor = tap.target.id();
    const events = currentEvents.filter((event) => event.actor_id === actor).slice(0, 12);
    const block = document.createElement("div");
    block.append(Object.assign(document.createElement("strong"), { textContent: actor }));
    const eventList = document.createElement("ul");
    if (!events.length) eventList.append(Object.assign(document.createElement("li"), { textContent: "No events retained for this actor." }));
    for (const event of events) {
      const item = document.createElement("li");
      item.append(`${event.timestamp} — ${event.text} `);
      if (event.source_url) {
        const link = document.createElement("a");
        link.href = event.source_url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = "Open source";
        item.append(link);
      }
      eventList.append(item);
    }
    block.append(eventList);
    showGraphDetail(block);
  });
  graph.on("tap", "edge", (tap) => {
    const edge = (currentReport.edges || []).find((item) => item.id === tap.target.id());
    const evidence = (currentReport.evidence || []).find((item) => item.edge_id === edge.id);
    showGraphDetail(`Relationship ${edge.source} ↔ ${edge.target}; weight ${edge.weight}. Supporting URLs: ${(evidence?.shared_urls || []).join(", ") || "none"}. Supporting event IDs: ${(evidence?.event_ids || []).join(", ") || "none"}.`);
  });
  showGraphDetail("Select an actor to see its retained events, or a relationship to see supporting event IDs and URLs.");
}

source.addEventListener("change", setSourceHelp);
clusterFilter.addEventListener("change", renderGraph);
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  requestStatus.textContent = "Collecting selected source…";
  reportSection.hidden = true;
  try {
    const metadata = await eventsForSource();
    currentEvents = metadata.events;
    requestStatus.textContent = `Analyzing ${currentEvents.length} normalized events…`;
    const report = await request("/api/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ events: currentEvents }),
    });
    renderReport(report, metadata);
    requestStatus.textContent = `Analysis complete: ${report.status.replaceAll("_", " ")}.`;
  } catch (error) {
    currentEvents = [];
    syntheticBanner.hidden = true;
    requestStatus.textContent = `Could not investigate: ${error.message}`;
  }
});

const params = new URLSearchParams(location.search);
investigation.value = params.get("investigate") || "";
if (investigation.value) {
  handoffNotice.hidden = false;
  handoffNotice.textContent = `Prefilled from the extension (${params.get("input_type") || "page"}). This is a reference only; no post has been collected or analysed yet.`;
}
setSourceHelp();
