"use strict";

const $ = (selector) => document.querySelector(selector);
const source = $("#source");
const form = $("#investigation-form");
const investigation = $("#investigation");
const requestStatus = $("#request-status");
const limitField = $("#limit-field");
const importField = $("#import-field");
const sourceHelp = $("#source-help");
const handoffNotice = $("#handoff-notice");
const submitButton = $("#investigate-button");
const syntheticBanner = $("#synthetic-banner");
const exportButton = $("#export-button");
let graph = null;
let latestReport = null;
let latestEvents = [];

function openInvestigation() {
  $("#investigation-overlay").classList.remove("hidden");
  $("#investigation-overlay").classList.add("flex");
  window.setTimeout(() => investigation.focus(), 0);
}

function closeInvestigation() {
  $("#investigation-overlay").classList.add("hidden");
  $("#investigation-overlay").classList.remove("flex");
}

const sourceMessages = {
  synthetic_coordinated: "Synthetic data is reproducible, labelled demonstration data and works offline.",
  synthetic_benign: "Synthetic data is reproducible, labelled demonstration data and works offline.",
  bluesky: "Uses a bounded public Bluesky search. Availability and coverage depend on the public endpoint.",
  snapshot: "Uses a stored public-data snapshot, so the demonstration can run without network access.",
  import: "Import normalized event JSON with id, platform, actor_id, timestamp, text, urls, and source_url fields.",
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function clear(node) {
  node.replaceChildren();
}

function formatLabel(value) {
  return String(value || "unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function setStatus(message, type = "info") {
  requestStatus.textContent = message;
  requestStatus.classList.remove("hidden", "text-error", "text-primary", "text-on-surface-variant");
  requestStatus.classList.add(type === "error" ? "text-error" : type === "success" ? "text-primary" : "text-on-surface-variant");
}

function setLoading(loading) {
  submitButton.disabled = loading;
  submitButton.classList.toggle("opacity-60", loading);
  submitButton.innerHTML = loading
    ? '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>Investigating'
    : '<span class="material-symbols-outlined text-[18px]">radar</span>Investigate';
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function updateSourceFields() {
  const isLive = source.value === "bluesky";
  const isImport = source.value === "import";
  limitField.classList.toggle("hidden", !isLive);
  importField.classList.toggle("hidden", !isImport);
  investigation.closest("label").classList.toggle("hidden", isImport);
  sourceHelp.textContent = sourceMessages[source.value];
}

async function importedEvents() {
  const file = $("#import-file").files[0];
  if (!file) throw new Error("Choose a normalized JSON file to import.");
  let payload;
  try {
    payload = JSON.parse(await file.text());
  } catch (_) {
    throw new Error("The selected file is not valid JSON.");
  }
  const events = Array.isArray(payload) ? payload : payload.events;
  if (!Array.isArray(events)) throw new Error("JSON import must be an events array or an object containing events.");
  return api("/api/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ events }) });
}

async function loadSource() {
  switch (source.value) {
    case "synthetic_coordinated":
    case "synthetic_benign":
      return api(`/api/datasets/${source.value}`);
    case "bluesky": {
      const query = investigation.value.trim();
      if (!query) throw new Error("Enter a phrase or URL for the public Bluesky search.");
      const limit = Math.min(100, Math.max(1, Number($("#limit").value) || 50));
      return api(`/api/collect/bluesky?query=${encodeURIComponent(query)}&limit=${limit}`);
    }
    case "snapshot":
      return api("/api/snapshots/bluesky");
    case "import":
      return importedEvents();
    default:
      throw new Error("Choose a data source.");
  }
}

function verdictCopy(status) {
  if (status === "suspicious") return {
    title: "Recurring relationship pattern identified",
    description: "The report contains recurring observed relationships that merit review. It does not establish bot identity, coordination intent, or propaganda intent.",
    icon: "visibility",
  };
  if (status === "insufficient_data") return {
    title: "Insufficient data for relationship analysis",
    description: "The available records are too limited to assess recurring relationships. Add more normalized events or choose another source.",
    icon: "data_alert",
  };
  return {
    title: "No recurring relationship pattern established",
    description: "This dataset did not meet the report's recurring-relationship threshold. That is not a conclusion about accounts or content.",
    icon: "fact_check",
  };
}

function eventMap() {
  return new Map(latestEvents.map((event) => [String(event.id), event]));
}

function renderVerdict(report) {
  const copy = verdictCopy(report.status);
  $("#verdict-title").textContent = copy.title;
  $("#verdict-summary").textContent = report.summary || copy.description;
  $("#verdict-icon").textContent = copy.icon;
  $("#verdict-badge").textContent = formatLabel(report.status);
  $("#report-status").textContent = formatLabel(report.status);
}

function renderKpis(report) {
  const stats = report.statistics || {};
  $("#kpi-posts").textContent = String(stats.events_observed ?? latestEvents.length ?? 0);
  $("#kpi-posts-note").textContent = `Across ${stats.actors_observed ?? 0} observed actors`;
  $("#kpi-relationships").textContent = String(stats.repeated_relationships ?? 0);
  $("#kpi-relationships-note").textContent = "Requires recurring shared-URL evidence";
  $("#kpi-urls").textContent = String(stats.relationship_groups ?? 0);
  $("#kpi-urls-note").textContent = "Groups with two or more actors";
}

function renderStatistics(report) {
  const target = $("#statistics");
  clear(target);
  const stats = report.statistics || {};
  const list = element("dl", "grid grid-cols-2 gap-x-3 gap-y-2");
  const entries = [
    ["Posts", stats.events_observed], ["Actors", stats.actors_observed],
    ["URL groups", stats.relationship_groups], ["Recurring", stats.repeated_relationships],
  ];
  for (const [label, value] of entries) {
    list.append(element("dt", "text-body-sm text-outline", label), element("dd", "text-right font-label text-label-md text-on-surface", String(value ?? 0)));
  }
  target.append(list);
}

function renderClusters(report) {
  const target = $("#clusters");
  const select = $("#cluster-filter");
  clear(target);
  select.replaceChildren(new Option("All observed actors", "all"));
  const clusters = Array.isArray(report.clusters) ? report.clusters : [];
  if (!clusters.length) {
    target.textContent = "No clusters were returned for this report.";
    return;
  }
  clusters.forEach((cluster, index) => {
    const actors = cluster.nodes || cluster.actor_ids || cluster.members || [];
    const label = `Group ${index + 1}`;
    const row = element("div", "rounded-lg bg-surface-container-lowest p-2");
    row.append(element("div", "font-label text-label-md text-on-surface", label));
    row.append(element("div", "mt-1 text-body-sm text-on-surface-variant", `${actors.length || cluster.post_ids?.length || 0} associated records`));
    target.append(row);
    if (actors.length) select.add(new Option(`${label} (${actors.length})`, `cluster-${index}`));
  });
}

function renderLimitations(report, sourceData) {
  const target = $("#limitations");
  clear(target);
  const notes = [...(sourceData.limitations || []), ...(report.limitations || [])];
  const unique = [...new Set(notes)];
  if (!unique.length) unique.push("No additional coverage notes were supplied.");
  const list = element("ul", "space-y-2");
  unique.slice(0, 6).forEach((note) => list.append(element("li", "flex gap-2 text-body-sm text-on-surface-variant", note)));
  target.append(list);
}

function sourceLink(event) {
  if (!event?.source_url) return null;
  const link = element("a", "mt-2 inline-flex items-center gap-1 text-body-sm text-primary underline", "Open original public post");
  link.href = event.source_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function renderEvidence(report) {
  const target = $("#evidence-feed");
  clear(target);
  const byId = eventMap();
  const evidence = Array.isArray(report.evidence) ? report.evidence : [];
  $("#evidence-count").textContent = `${evidence.length} relationship${evidence.length === 1 ? "" : "s"}`;
  if (!evidence.length) {
    target.append(element("p", "rounded-xl bg-surface-container-lowest p-3 text-body-sm text-on-surface-variant", "No shared-relationship evidence was returned for this input."));
    return;
  }
  evidence.slice(0, 16).forEach((item) => {
    const card = element("article", "rounded-xl border-l-2 border-primary bg-surface-container-lowest p-3");
    const ids = item.event_ids || [];
    const event = byId.get(String(ids[0]));
    const top = element("div", "flex items-center justify-between gap-2");
    top.append(element("span", "font-label text-label-md font-bold text-on-surface", event?.actor_id || item.edge_id || "Observed relationship"));
    top.append(element("span", "rounded bg-surface-container-high px-1.5 py-0.5 font-label text-label-sm text-primary", formatLabel(item.assessment)));
    card.append(top);
    if (event?.timestamp) card.append(element("div", "mt-1 font-label text-label-sm text-outline", new Date(event.timestamp).toLocaleString()));
    if (event?.text) card.append(element("p", "mt-1.5 text-body-sm text-on-surface-variant", event.text));
    if (item.shared_urls?.length) card.append(element("p", "mt-1 break-all text-body-sm text-primary", item.shared_urls.join(" · ")));
    card.append(sourceLink(event) || element("p", "mt-2 text-body-sm text-outline", `${ids.length} supporting event record${ids.length === 1 ? "" : "s"}`));
    target.append(card);
  });
}

function detailForNode(node) {
  const byId = eventMap();
  const events = (node.event_ids || []).map((id) => byId.get(String(id))).filter(Boolean);
  const panel = $("#graph-detail");
  clear(panel);
  panel.append(element("div", "font-label text-label-md text-on-surface", node.id));
  panel.append(element("p", "mt-1", `${events.length} normalized event record${events.length === 1 ? "" : "s"} connected to this actor.`));
  const link = sourceLink(events[0]);
  if (link) panel.append(link);
}

function detailForEdge(edge) {
  const panel = $("#graph-detail");
  clear(panel);
  panel.append(element("div", "font-label text-label-md text-on-surface", `${edge.source} ↔ ${edge.target}`));
  panel.append(element("p", "mt-1", `${edge.weight || 0} observed shared-URL group${Number(edge.weight) === 1 ? "" : "s"}; assessment: ${formatLabel(edge.evidence_assessment)}.`));
  const links = edge.content_groups?.flatMap((group) => group.evidence?.flatMap((evidence) => evidence.shared_urls || []) || []) || [];
  if (links.length) panel.append(element("p", "mt-1 break-all text-primary", [...new Set(links)].join(" · ")));
}

function renderGraph(report, selectedCluster = "all") {
  const container = $("#graph");
  if (graph) { graph.destroy(); graph = null; }
  clear(container);
  if (!window.cytoscape) {
    container.append(element("p", "grid h-full place-items-center px-8 text-center text-body-sm text-error", "The network graph library could not load. The report and evidence remain available."));
    return;
  }
  let nodes = Array.isArray(report.nodes) ? report.nodes : [];
  let edges = (Array.isArray(report.edges) ? report.edges : []).filter((edge) => edge.repeated);
  // The default view deliberately favors the evidence-backed, strongest edges.
  // Isolated accounts remain represented in the report statistics instead of
  // making a large graph unreadable.
  if (edges.length) {
    const connectedActors = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
    nodes = nodes.filter((node) => connectedActors.has(node.id));
  }
  if (selectedCluster !== "all") {
    const cluster = report.clusters?.[Number(selectedCluster.replace("cluster-", ""))];
    const actorSet = new Set(cluster?.nodes || cluster?.actor_ids || cluster?.members || []);
    nodes = nodes.filter((node) => actorSet.has(node.id));
    edges = edges.filter((edge) => actorSet.has(edge.source) && actorSet.has(edge.target));
  }
  if (!nodes.length) {
    container.append(element("p", "grid h-full place-items-center px-8 text-center text-body-sm text-outline", "This filter has no graphable actor records."));
    return;
  }
  graph = window.cytoscape({
    container,
    elements: { nodes: nodes.map((node) => ({ data: node })), edges: edges.map((edge) => ({ data: edge })) },
    style: [
      { selector: "node", style: { "background-color": "#869397", label: "data(id)", color: "#dee2f6", "font-family": "Inter", "font-size": 10, "text-valign": "bottom", "text-margin-y": 7, width: 22, height: 22 } },
      { selector: "edge", style: { width: "mapData(weight, 1, 8, 1.5, 5)", "line-color": "#06b6d4", "curve-style": "bezier", opacity: 0.9 } },
      { selector: ":selected", style: { "background-color": "#4cd7f6", "line-color": "#4cd7f6", "border-width": 2, "border-color": "#dee2f6" } },
    ],
    layout: { name: "cose", animate: false, padding: 36, nodeRepulsion: 7000, idealEdgeLength: 105 },
  });
  graph.on("tap", "node", (event) => detailForNode(event.target.data()));
  graph.on("tap", "edge", (event) => detailForEdge(event.target.data()));
}

function renderReport(report, sourceData) {
  latestReport = report;
  renderVerdict(report);
  renderKpis(report);
  renderStatistics(report);
  renderClusters(report);
  renderLimitations(report, sourceData);
  renderEvidence(report);
  renderGraph(report);
  syntheticBanner.classList.toggle("hidden", !String(source.value).startsWith("synthetic_"));
  exportButton.disabled = false;
}

async function runInvestigation(event) {
  event?.preventDefault();
  setLoading(true);
  setStatus("Loading normalized records…");
  try {
    const sourceData = await loadSource();
    latestEvents = Array.isArray(sourceData.events) ? sourceData.events : [];
    setStatus(`Analyzing ${latestEvents.length} normalized records…`);
    const report = await api("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ events: latestEvents }) });
    renderReport(report, sourceData);
    setStatus(`Report ready: ${formatLabel(report.status)}.`, "success");
    closeInvestigation();
  } catch (error) {
    setStatus(error.message || "Unable to run this investigation.", "error");
  } finally {
    setLoading(false);
  }
}

function exportReport() {
  if (!latestReport) return;
  const blob = new Blob([JSON.stringify({ report: latestReport, events: latestEvents }, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "coordination-radar-report.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

async function checkHealth() {
  try {
    await api("/healthz");
    $("#service-indicator").className = "h-2 w-2 rounded-full bg-primary animate-pulse";
    $("#service-label").textContent = "System active";
  } catch (_) {
    $("#service-indicator").className = "h-2 w-2 rounded-full bg-error";
    $("#service-label").textContent = "Service unavailable";
  }
}

function initialiseExtensionInput() {
  const params = new URLSearchParams(window.location.search);
  const query = params.get("investigate");
  if (!query) return;
  investigation.value = query;
  source.value = "bluesky";
  handoffNotice.textContent = "Extension handoff: this prefills an investigation only. It does not mean the selected page or post has been collected or analyzed.";
  handoffNotice.classList.remove("hidden");
  updateSourceFields();
  openInvestigation();
}

form.addEventListener("submit", runInvestigation);
source.addEventListener("change", updateSourceFields);
$("#cluster-filter").addEventListener("change", (event) => { if (latestReport) renderGraph(latestReport, event.target.value); });
$("#graph-zoom-in").addEventListener("click", () => graph?.zoom({ level: graph.zoom() * 1.2, renderedPosition: { x: graph.width() / 2, y: graph.height() / 2 } }));
$("#graph-zoom-out").addEventListener("click", () => graph?.zoom({ level: graph.zoom() / 1.2, renderedPosition: { x: graph.width() / 2, y: graph.height() / 2 } }));
$("#graph-reset").addEventListener("click", () => graph?.fit(undefined, 36));
exportButton.addEventListener("click", exportReport);
document.querySelectorAll("[data-scroll-target]").forEach((button) => button.addEventListener("click", () => document.getElementById(button.dataset.scrollTarget)?.scrollIntoView({ behavior: "smooth" })));
document.querySelectorAll("[data-investigation-toggle]").forEach((trigger) => trigger.addEventListener("click", (event) => { event.preventDefault(); openInvestigation(); }));
document.querySelectorAll("[data-investigation-close]").forEach((trigger) => trigger.addEventListener("click", closeInvestigation));
$("#investigation-overlay").addEventListener("click", (event) => { if (event.target === event.currentTarget) closeInvestigation(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeInvestigation(); });
updateSourceFields();
initialiseExtensionInput();
checkHealth();
