# Coordination Radar — Engineer A Implementation Plan

**Role:** Detection intelligence engineer  
**Time budget:** 24 hours  
**Objective:** Deliver a platform-independent, explainable coordination-detection engine that takes normalized public activity events and returns statistically supported candidate networks, their evidence, and explicit uncertainty.

## Responsibilities

Engineer A owns:
- Event validation and feature extraction for coordination analysis
- URL, text, and temporal similarity features
- Repeated co-activity detection and weighted actor graph construction
- Statistical testing against an appropriate null model
- Candidate cluster discovery and evidence-backed explanations
- Algorithm unit tests, benign controls, and integration of the engine with Engineer B's API

Engineer B separately owns ingestion, synthetic datasets, the FastAPI server, dashboard, network visualization, Chrome extension, and deployment. **Engineer A's engine must not depend on the source platform or the web UI.**

## Interface contract (agree during hour 0)

**Entry point:** Engineer B passes normalized events into one importable Python function:

```python
def analyze(events: list[dict]) -> dict:
    ...
```

Each event follows the same schema Engineer B uses:

```json
{
  "id": "post-001",
  "platform": "bluesky",
  "actor_id": "bluesky:actor-123",
  "timestamp": "2026-11-14T12:00:00Z",
  "text": "Example message",
  "urls": ["https://example.org/story"],
  "source_url": "https://bsky.app/..."
}
```

**Response:** Return a JSON-serializable dictionary with at least these top-level fields:

| Field | Meaning |
| --- | --- |
| `status` | `suspicious`, `inconclusive`, or `insufficient_data` |
| `nodes` | Actor records for graph visualization |
| `edges` | Actor pairs, evidence weights, and supporting event IDs |
| `clusters` | Groups of actors with repeated, unusually coordinated activity |
| `evidence` | Human-readable explanations with supporting event IDs |
| `statistics` | Observed counts, null-model reference values, and optional p-values |
| `limitations` | Dataset gaps, statistical caveats, and interpretation limits |

Agree with Engineer B on the **nested** shapes of `nodes`, `edges`, `clusters`, and `evidence` before either engineer builds against them. Keep actor IDs and event IDs stable; do not make the frontend reconstruct evidence from prose.

**Minimal output example:**

```json
{
  "status": "inconclusive",
  "nodes": [{"id": "bluesky:actor-123", "platform": "bluesky"}],
  "edges": [],
  "clusters": [],
  "evidence": [],
  "statistics": {"events_analyzed": 1, "actors_analyzed": 1},
  "limitations": ["Not enough repeated activity to assess coordination."]
}
```

A detected cluster must be labeled as **potential coordination**, not proven bot activity, deception, or propaganda. Do not present heuristic scores or p-values as calibrated probabilities that an account is a bot.

## Step-by-step schedule

### Step 1 — Hours 0–1: Establish the detector interface

1. Create `engine/analyzer.py` with `analyze(events: list[dict]) -> dict`.
2. Agree with Engineer B on the event input, graph node/edge, cluster, evidence, and statistics formats.
3. Implement a schema-valid placeholder response with stable keys and JSON-serializable values.
4. Add a smoke test confirming that an empty input returns `insufficient_data` rather than crashing.
5. Commit the contract and share the import path immediately, so Engineer B can build against it.

**Deliverable:** An importable detector stub and a frozen shared contract.

### Step 2 — Hours 1–4: Implement feature extraction

1. Parse UTC timestamps consistently; handle timezone offsets, invalid values, and missing fields safely.
2. Normalize text for comparison (Unicode handling, case normalization, whitespace, and basic punctuation). Retain the original text for evidence display.
3. Canonicalize shared URLs where safe (normalize hostnames, remove common tracking parameters, preserve meaningful query parameters).
4. Generate lightweight similarity features: exact canonical URL matches and near-duplicate text scores (e.g., token Jaccard or RapidFuzz).
5. Produce an efficient index from content signatures to events, so you avoid comparing every event against every other event.
6. Write unit tests for capitalization, reordered words, tracking-parameter variants, duplicate posts, and distinct-but-similar texts.

**Deliverable:** Tested functions that find shared content artifacts across normalized events, independently of platform.

### Step 3 — Hours 4–8: Detect repeated behavioral coordination

1. Group events by shared canonical URL and/or near-duplicate text signature.
2. For each group, order events by timestamp and find actor pairs that publish related content within a configurable window (start with **90 seconds** for demo exploration).
3. Count coordination occurrences across **distinct** content groups or separate temporal bursts—not simply repeated copies of one viral post.
4. Build a weighted actor graph: each edge stores the number of repeated co-activity occurrences, their timing, and supporting event IDs.
5. Exclude self-pairs, collapse duplicate events, and avoid double-counting multiple posts from the same actor in one burst.
6. Return preliminary edges and evidence even before statistical significance testing is added.

**Deliverable:** A reproducible coordination graph identifying accounts that repeatedly co-act around shared content.

### Step 4 — Hours 8–12: Add statistical evidence

1. Define a null hypothesis: actors publish independently **conditional on** the observed topic/time activity patterns and other properties you can preserve.
2. Implement constrained permutations—for example, shuffle actor assignments within topic/time strata while preserving event timestamps, content groups, and approximate actor activity counts where feasible.
3. Recompute the same network-discovery statistic for each permutation; do not compare an observed *best-of-many* cluster with an uncorrected single-pair test.
4. Use roughly **199 permutations** as a fast initial demo setting, with an option to increase the count if runtime permits.
5. Compute an empirical p-value with a finite-sample correction: `(1 + permutations_at_least_as_extreme) / (1 + total_permutations)`.
6. Document what the null model preserves and what it misses; the model may still produce false positives during major breaking-news events.
7. Keep the p-value distinct from a descriptive coordination score. If the null model cannot be estimated reliably, return `inconclusive` rather than a fabricated probability.

**Deliverable:** A basic, defensible statistical anomaly assessment and accompanying explanation.

### Step 5 — Hours 12–16: Discover and explain suspicious clusters

1. Use NetworkX to create a graph from evidence-weighted actor relationships.
2. Find connected components or a simple community partition; prefer interpretable results over a complicated graph-learning model.
3. Rank candidate clusters by repeated independent co-activity, strength of evidence, and persistence across content groups—not by political position or viewpoint.
4. Compute each cluster's actor count, event count, number of distinct content groups, cross-platform coverage, and representative synchronization intervals.
5. For each displayed edge and cluster, preserve supporting event IDs, timestamps, and source URLs where available.
6. Generate compact explanations such as: “Seven accounts shared four unrelated URLs within 90 seconds of one another on three separate occasions.”
7. Return `suspicious` only for clusters satisfying explicitly documented evidence criteria; otherwise use `inconclusive` or `insufficient_data`.

**Deliverable:** A frontend-ready report with candidate networks, graph data, statistical context, and auditable evidence.

### Step 6 — Hours 16–19: Validate against negative examples

1. Run the engine on Engineer B's **synthetic coordinated scenario** and confirm the repeated synchronized group appears as a candidate cluster.
2. Run it on the **synthetic benign viral-news scenario** and check that a one-time popularity spike is not automatically labeled inauthentic.
3. Add unit tests for empty inputs, one actor, duplicate events, malformed timestamps, events from different platforms, and no-content-overlap cases.
4. Check performance on several hundred to a few thousand events; optimize only the bottlenecks that affect the demo.
5. Review a small set of edge explanations by hand and confirm they link to the exact events that actually support them.
6. Write down known limitations, especially sampling bias, incomplete datasets, common external triggers, and the inability to prove automation or intent from coordination alone.

**Deliverable:** A detector that demonstrates a meaningful distinction between recurrent coordination and incidental similarity.

### Step 7 — Hours 19–21: Integrate with Engineer B's application

1. Confirm that `engine.analyzer.analyze(events)` works from Engineer B's FastAPI process without special environment assumptions.
2. Validate request and response schemas end to end; check all graph IDs and evidence/event references.
3. Run both synthetic scenarios through the real HTTP endpoint, not only through unit tests.
4. Ensure the browser graph shows the same relationships the engine reports and that clicking an edge reveals genuine supporting evidence.
5. Check that public-source data with too little coverage returns a useful `insufficient_data` or `inconclusive` result.
6. Help fix integration failures, but avoid redesigning the algorithm this late in the schedule.

**Deliverable:** The real engine connected to the dashboard with reproducible outputs.

### Step 8 — Hours 21–24: Freeze, stabilize, and prepare the explanation

1. Freeze new detection features and save a known-good version.
2. Re-run the complete smoke and unit test suite.
3. Verify the offline synthetic demonstration works even without external APIs or AI services.
4. Prepare a 30–60 second technical explanation covering repeated co-activity, baseline comparison, graph clustering, and uncertainty.
5. Explain clearly that statistical evidence of coordination **does not establish** that accounts are bots or that the content is propaganda.
6. Assist Engineer B with rehearsal and fix only bugs that could prevent the presentation.

**Deliverable:** A stable, explainable detector ready for the live demonstration.

## Acceptance checklist

- [ ] `analyze(events)` accepts the agreed normalized schema and returns a JSON-serializable report.
- [ ] Empty, invalid, and sparse inputs produce understandable non-crashing results.
- [ ] Shared URLs, near-duplicate text, and repeated near-synchronous activity are detected.
- [ ] Network edges and cluster explanations reference the actual supporting event IDs.
- [ ] The recurring synthetic coordination scenario produces an identifiable candidate cluster.
- [ ] The benign viral-news scenario is not automatically classified as deceptive coordination.
- [ ] Statistical evidence is reported accurately, with the null-model assumptions and uncertainty clearly stated.
- [ ] Unit tests pass and the detector works through Engineer B's HTTP endpoint.
- [ ] No result claims to prove bot identity, operator identity, deceptive intent, or propaganda solely from coordination signals.

## Scope guardrails

**Required:** contract, normalized feature extraction, repeated co-activity graph, interpretable candidate clusters, evidence references, positive and negative test scenarios.  
**Preferred:** constrained permutation test with empirical p-values and cluster-level comparisons.  
**Optional:** semantic embeddings, cross-language similarity, richer statistical calibration, report export.  
**Not in scope:** neural-network training, cross-platform account identity resolution, automated content bans, political truth classification, or claiming a numerically calibrated bot probability without validation.

**Critical checkpoint:** By **hour 12**, the detector must run independently on Engineer B's synthetic events and return a useful candidate graph; Engineer B should already have a working dashboard using a mock response. Reserve hours 19–24 for integration, testing, and demo rehearsal.
