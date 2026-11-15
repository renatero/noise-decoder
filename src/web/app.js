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
  all: "Searches Bluesky, Hacker News, Reddit and current BBC, Guardian and Al Jazeera headlines. Results are limited in total; unavailable sources are reported.",
  hackernews: "Searches Hacker News story submissions by date. Actors are submitting usernames, not article authors.",
  bbc: "BBC World headlines and summaries. Leave the phrase empty for recent items, or filter current headlines by all words. Actors represent the publisher.",
  guardian: "The Guardian World headlines and summaries. Leave the phrase empty for recent items, or filter by all words. Actors represent the publisher.",
  aljazeera: "Al Jazeera headlines and summaries. Leave the phrase empty for recent items, or filter by all words. Actors represent the publisher.",
  bluesky: "Uses a bounded public Bluesky search. Availability and coverage depend on the public endpoint.",
  context: "Search recent English news across publishers. Up to 10 results per search, normally 1 credit; repeated searches are cached for 10 minutes. Articles provide background context for your investigation.",
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
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status})`);
    error.collection = data.collection;
    throw error;
  }
  return data;
}

function updateSourceFields() {
  const isLive = ["all", "bluesky", "hackernews", "bbc", "guardian", "aljazeera", "context"].includes(source.value);
  const isImport = source.value === "import";
  const isContext = source.value === "context";
  $("#context-days-field").classList.toggle("hidden", !isContext);
  $("#limit").max = isContext ? "10" : "100";
  if (isContext) $("#limit").value = String(Math.min(10, Number($("#limit").value) || 10));
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
    case "all":
    case "hackernews":
    case "bbc":
    case "guardian":
    case "aljazeera":
    case "bluesky": {
      const query = investigation.value.trim();
      if (!query && ["all", "bluesky", "hackernews"].includes(source.value)) throw new Error("Enter a phrase or URL for the public search.");
      const limit = Math.min(100, Math.max(1, Number($("#limit").value) || 50));
      return api(`/api/collect/${source.value}?query=${encodeURIComponent(query)}&limit=${limit}`);
    }
    case "snapshot":
      return api("/api/snapshots/bluesky");
    case "import":
      return importedEvents();
    case "context": {
      const query = investigation.value.trim();
      if (!query) throw new Error("Enter a topic or question to search the news.");
      return api("/api/collect/context", {
        method: "POST", headers: { "Content-Type": "application/json", "X-NoiseDecoder-Request": "1" },
        body: JSON.stringify({ query, limit: Math.min(10, Math.max(1, Number($("#limit").value) || 10)), days: Number($("#context-days").value) }),
      });
    }
    default:
      throw new Error("Choose a data source.");
  }
}

function verdictCopy(status) {
  if (status === "search_failed") return {
    title: "Search could not be completed", description: "Review each source's status below and try again.", icon: "error",
  };
  if (status === "news_context") return {
    title: "Related news collected", description: "Publisher coverage provides background context for your investigation.", icon: "newspaper",
  };
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

function renderVerdict(report, sourceData) {
  const copy = verdictCopy(report.status);
  $("#verdict-title").textContent = copy.title;
  let summary = report.summary || copy.description;
  if (report.status === "insufficient_data") {
    const count = latestEvents.length;
    const sources = sourceData.sources || [];
    const failed = sources.filter((item) => item.status === "error").length;
    summary = sources.length
      ? `${count} usable record${count === 1 ? "" : "s"} collected. ${failed ? `${failed} of ${sources.length} sources could not complete the search. ` : ""}There is not enough data to assess recurring relationships. See the sources searched below.`
      : `${count} record${count === 1 ? "" : "s"} loaded. There is not enough data to assess recurring relationships. No live search was performed.`;
  }
  $("#verdict-summary").textContent = summary;
  $("#verdict-icon").textContent = copy.icon;
  $("#verdict-badge").textContent = formatLabel(report.status);
  $("#report-status").textContent = formatLabel(report.status);
}

function renderSearchCoverage(sourceData) {
  const rows = Array.isArray(sourceData.sources) ? sourceData.sources : [];
  const section = $("#search-coverage");
  section.classList.remove("hidden");
  $("#search-coverage-title").textContent = rows.length ? "Sources searched" : "Data source";
  const details = [];
  if (rows.length) {
    details.push(sourceData.query ? `Query: “${sourceData.query}”` : "Current headlines · no keyword filter");
    if (sourceData.requested_limit) details.push(`Result limit: ${sourceData.requested_limit}`);
    if (sourceData.search_completed_at) details.push(`Completed: ${new Date(sourceData.search_completed_at).toLocaleString()}`);
    if (sourceData.cached) details.push("Cached results · no new provider request");
    if (sourceData.source === "all_public_sources" || sourceData.source === "all") details.push("Context.dev is searched separately when selected");
  } else {
    details.push("No live search was performed. Results use the selected dataset, snapshot, or imported file.");
  }
  $("#search-query-summary").textContent = details.join(" · ");
  const target = $("#search-source-list");
  clear(target);
  for (const item of rows) {
    const card = element("li", "rounded-xl bg-surface-container-lowest p-3");
    const heading = element("div", "flex flex-wrap items-center justify-between gap-2");
    const name = element("a", "font-label text-label-md font-bold text-primary underline", item.name || formatLabel(item.id));
    if (/^https?:\/\//i.test(item.url || "")) {
      name.href = item.url;
      name.target = "_blank";
      name.rel = "noopener noreferrer";
    }
    const failed = item.status === "error";
    const count = item.available_events ?? 0;
    const status = failed ? "Unavailable · search not completed" : count ? `${count} usable record${count === 1 ? "" : "s"}` : "No usable matches";
    heading.append(name, element("span", `text-body-sm ${failed ? "text-error" : "text-on-surface-variant"}`, status));
    card.append(heading);
    if (item.scope) card.append(element("p", "mt-1 text-body-sm text-outline", item.scope));
    if (failed) card.append(element("p", "mt-1 text-body-sm text-error", item.error || "This source was unavailable. Its results are unknown."));
    else if (count > 0 && item.returned_events < count) card.append(element("p", "mt-1 text-body-sm text-outline", `${item.returned_events} included after the combined result limit.`));
    target.append(card);
  }
}

function renderKpis(report) {
  const stats = report.statistics || {};
  const isNews = report.status === "news_context";
  $("#kpi-posts-label").textContent = isNews ? "News articles" : "Analyzed posts";
  $("#kpi-posts").textContent = String((isNews ? stats.news_articles : stats.events_observed) ?? latestEvents.length ?? 0);
  $("#kpi-posts-note").textContent = isNews ? `Across ${stats.news_publishers ?? 0} publishers` : `Across ${stats.actors_observed ?? 0} observed actors`;
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
    [report.status === "news_context" ? "Articles" : "Posts", report.status === "news_context" ? stats.news_articles : stats.events_observed],
    [report.status === "news_context" ? "Publishers" : "Actors", report.status === "news_context" ? stats.news_publishers : stats.actors_observed],
    ["URL groups", stats.relationship_groups], ["Recurring", stats.repeated_relationships],
  ];
  const score = report.permutation_analysis || {};
  const techniqueScore = report.technique_analysis?.score_adjustment || score.propaganda_technique_adjustment;
  if (score.network_heuristic_suspicion_score !== undefined) entries.push(["Network score", score.network_heuristic_suspicion_score]);
  if (score.heuristic_suspicion_score !== undefined) entries.push(["Adjusted score", score.heuristic_suspicion_score]);
  if (techniqueScore?.score_delta !== undefined) entries.push(["Technique uplift", `+${techniqueScore.score_delta}`]);
  for (const [label, value] of entries) {
    list.append(element("dt", "text-body-sm text-outline", label), element("dd", "text-right font-label text-label-md text-on-surface", String(value ?? 0)));
  }
  target.append(list);
}

function renderTechniques(report) {
  const target = $("#techniques");
  clear(target);
  const analysis = report.technique_analysis || {};
  const background = report.news_context_technique_analysis;
  const techniques = Array.isArray(analysis.techniques) ? analysis.techniques : [];
  const adjustment = analysis.score_adjustment || report.permutation_analysis?.propaganda_technique_adjustment;
  if (adjustment) {
    target.append(element("p", "mb-2 text-body-sm text-on-surface-variant",
      `Network score ${adjustment.network_score ?? "—"} · technique uplift +${adjustment.score_delta ?? 0} · adjusted ${adjustment.adjusted_score ?? "—"}`));
  }
  if (!techniques.length) {
    target.append(element("p", "text-body-sm text-on-surface-variant", "No candidate technique cues found in the analyzed text."));
  } else {
    const list = element("ul", "space-y-2");
    techniques.forEach((technique) => {
      const item = element("li", "rounded-lg bg-surface-container-lowest p-2");
      item.append(element("div", "font-label text-label-md text-on-surface", technique.name || formatLabel(technique.id)));
      item.append(element("p", "mt-1 text-body-sm text-outline",
        `${technique.confidence || "low"} confidence · ${technique.supporting_post_count || 0} posts · ${technique.supporting_actor_count || 0} accounts`));
      const cues = (technique.evidence || []).slice(0, 2).map((evidence) => `“${evidence.matched_text}”`).join(" · ");
      if (cues) item.append(element("p", "mt-1 text-body-sm text-on-surface-variant", cues));
      list.append(item);
    });
    target.append(list);
  }
  if (analysis.method) target.append(element("p", "mt-2 text-body-sm text-outline", analysis.method));
  if (analysis.reference?.url) {
    const citation = element("a", "mt-2 inline-block text-body-sm text-primary underline", "PTC-18 taxonomy reference");
    citation.href = analysis.reference.url;
    citation.target = "_blank";
    citation.rel = "noopener noreferrer";
    target.append(citation);
  }
  if (background) {
    target.append(element("h3", "mb-1 mt-3 font-label text-label-md text-on-surface", "Background news · not scored as account evidence"));
    const contextTechniques = Array.isArray(background.techniques) ? background.techniques : [];
    if (!contextTechniques.length) {
      target.append(element("p", "text-body-sm text-on-surface-variant", "No candidate technique cues found in publisher articles."));
    } else {
      contextTechniques.forEach((technique) => {
        const item = element("div", "mb-2 rounded-lg bg-surface-container-lowest p-2");
        item.append(element("div", "font-label text-label-md text-on-surface", technique.name || formatLabel(technique.id)));
        item.append(element("p", "mt-1 text-body-sm text-outline", `Low confidence · ${technique.supporting_post_count || 0} articles`));
        const cue = technique.evidence?.[0]?.matched_text;
        if (cue) item.append(element("p", "mt-1 text-body-sm text-on-surface-variant", `“${cue}”`));
        target.append(item);
      });
    }
    if (background.reference?.url) {
      const citation = element("a", "mt-1 inline-block text-body-sm text-primary underline", "PTC-18 taxonomy reference");
      citation.href = background.reference.url;
      citation.target = "_blank";
      citation.rel = "noopener noreferrer";
      target.append(citation);
    }
  }
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
  const notes = [...(sourceData.limitations || []), ...(report.limitations || []), ...(report.technique_analysis?.limitations || [])];
  if (sourceData.source === "context_news") notes.unshift(sourceData.cached
    ? "This search used cached results and consumed no additional credits."
    : `This search consumed ${sourceData.credits_consumed ?? "an unreported number of"} Context.dev credits.`);
  const unique = [...new Set(notes)];
  if (!unique.length) unique.push("No additional coverage notes were supplied.");
  const list = element("ul", "space-y-2");
  unique.forEach((note) => list.append(element("li", "flex gap-2 text-body-sm text-on-surface-variant", note)));
  target.append(list);
}

function sourceLink(event) {
  if (!event?.source_url) return null;
  const link = element("a", "mt-2 inline-flex items-center gap-1 text-body-sm text-primary underline", ["news_rss", "news_context"].includes(event.platform) ? `Read at ${event.publisher || event.actor_id}` : "Open original public post");
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
    target.append(element("p", "rounded-xl bg-surface-container-lowest p-3 text-body-sm text-on-surface-variant", report.status === "news_context"
      ? "Related publisher coverage. Open an original article to assess its relevance."
      : latestEvents.length ? "No shared-relationship evidence was returned for this input."
      : "No usable records were returned. Review the source results above."));
    $("#evidence-count").textContent = `${latestEvents.length} source records`;
    latestEvents.slice(0, 16).forEach((event) => {
      const card = element("article", "rounded-xl bg-surface-container-lowest p-3");
      card.append(element("div", "font-label text-label-md font-bold text-on-surface", event.publisher || event.actor_id));
      card.append(element("div", "mt-1 font-label text-label-sm text-outline", `${formatLabel(event.platform)} · ${new Date(event.timestamp).toLocaleString()}`));
      card.append(element("p", "mt-1.5 text-body-sm text-on-surface-variant", event.text));
      const link = sourceLink(event);
      if (link) card.append(link);
      target.append(card);
    });
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
  latestReport = {
    ...report,
    synthetic: sourceData.dataset_type === "synthetic_demonstration",
    limitations: [...new Set([...(sourceData.limitations || []), ...(report.limitations || [])])],
    collection: { source: sourceData.source, query: sourceData.query, sources: sourceData.sources,
      requested_limit: sourceData.requested_limit, search_completed_at: sourceData.search_completed_at,
      cached: sourceData.cached, credits_consumed: sourceData.credits_consumed, collected_at: sourceData.collected_at },
  };
  renderVerdict(report, sourceData);
  renderSearchCoverage(sourceData);
  renderKpis(report);
  renderStatistics(report);
  renderTechniques(report);
  renderClusters(report);
  renderLimitations(report, sourceData);
  renderEvidence(report);
  renderGraph(report);
  syntheticBanner.classList.toggle("hidden", !latestReport.synthetic);
  exportButton.disabled = false;
  document.dispatchEvent(new Event("noise:report"));
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
    if (error.collection) {
      latestEvents = [];
      renderReport({status: "search_failed", summary: error.message, statistics: {}, nodes: [], edges: [], evidence: [], clusters: []}, error.collection);
      closeInvestigation();
    }
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

async function checkSources() {
  try {
    const catalog = await api("/api/sources");
    const context = catalog.sources.find((item) => item.id === "context");
    const reddit = catalog.sources.find((item) => item.id === "reddit");
    const option = source.querySelector('option[value="context"]');
    option.disabled = !context?.available;
    option.textContent = context?.available ? "News: Context.dev search" : "News: Context.dev (unavailable)";
    const redditOption = source.querySelector('option[value="reddit"]');
    redditOption.disabled = !reddit?.available;
    redditOption.textContent = reddit?.available ? "Discussion: Reddit search" : "Discussion: Reddit (configure OAuth)";
  } catch (_) { /* Keep the optional source disabled if configuration is unknown. */ }
}

function initialiseExtensionInput() {
  const params = new URLSearchParams(window.location.search);
  const query = params.get("investigate");
  if (!query) return;
  investigation.value = query;
  source.value = "all";
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
checkSources();
