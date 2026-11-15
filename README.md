# noise-decoder
hostinger challenge junction 2026

## Run the demonstration

```bash
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/dashboard` locally, or
`https://decodethenoise.today/dashboard` on the VPS. The root path serves the
project progress overview. The dashboard provides two reproducible synthetic scenarios, bounded
public Bluesky and Hacker News search, BBC World / Guardian World / Al Jazeera
news feeds, an offline public-data snapshot, and normalized JSON
import. See [the API guide](src/api/README.md), [deployment guide](deploy/README.md),
and [demo runbook](docs/demo-runbook.md). The source selector offers individual
sources or **Live: All sources**. See [source research and coverage](docs/news-sources.md).

## Verify

```bash
python3 -m unittest discover -s src/collectors/tests -v
python3 -m unittest discover -s src/api/tests -v
python3 -m unittest discover -s src/discovery/tests -v
python3 -m unittest discover -s src/engine/tests -v
node --experimental-default-type=module chrome-extension/tests/background.test.mjs
```

## Behavioral coordination detection: time-window signal

The first time-based signal looks for accounts publishing posts that are already related by a shared canonical URL or similar content. It identifies candidate bursts for review; timing and content similarity alone do not establish coordination.

### Algorithm outline

1. Start from the candidate post groups produced by the shared-URL and near-duplicate matcher. Retain each pair's matching reason and evidence.
2. Parse each post's published timestamp as a UTC instant. Exclude posts with missing or invalid timestamps from the time-window calculation and report the excluded count. Do not substitute extraction time for publication time.
3. Within each candidate group, sort eligible posts by timestamp and scan rolling windows of configurable duration. The default is 60 minutes; a rolling window can capture a burst that crosses a clock-hour boundary.
4. For each window, count posts and distinct identified accounts. Emit a burst candidate when the configured minimum account count appears; the default is two. Repeated posts from one account alone do not qualify.
5. Report the window start and end, configured duration, post count, distinct account count, participating post and account IDs, plus the shared URL or text-similarity edges that connect those posts. Preserve the original related-post group even when it contains no qualifying burst.
6. Describe the result as an observed timing pattern, not an attribution of intent. Account IDs and timestamps depend on the fields exposed by each platform; display-name-based actor IDs may not uniquely identify accounts.

The extension settings page exposes both the window duration (1–10,080 minutes) and minimum distinct accounts (2–100). Invalid or missing publication timestamps are excluded and counted; posts without an identifiable account ID can contribute to the post count but not the distinct-account threshold.

### Repeated co-activity

After finding candidate content groups and time-window bursts, enumerate distinct account pairs in each context. For every pair, record the content-group IDs and publication-burst IDs where both accounts appear, the posts contributed by each account, and direct pairwise relationship evidence when available. Mark the pair as repeated when it appears in at least two distinct content groups or at least two distinct publication bursts. A single group and a burst derived from that same group do not alone count as repetition.

Keep both the full account-pair records and the repeated-pair subset in the output. This makes the recurrence count inspectable and preserves one-off co-activity for context. A single group or burst is labeled limited. Repeated bursts within one content group remain limited because a shared breaking-news event or another common cause may explain them; only recurrence across distinct content groups is labeled a recurring pattern. The system does not detect breaking news directly, so none of these signals proves coordination. Actor IDs may be display-name-derived, and bursts are based on visible posts only.

### Weighted actor graph

Return an undirected actor graph with identified accounts as nodes and observed co-activity pairs as edges. Each node lists its posts, content groups, and publication bursts. Each edge carries its weight, evidence assessment, repeated flag, and the supporting group/burst records. The documented support score gives one point per distinct content group; a first burst within a group adds no extra weight, additional bursts within that same group add 0.25 each, and a burst without a content-group association has a base weight of 0.5. This deliberately limits the effect of one simultaneous response to a breaking-news event. Weights are evidence support scores, not probabilities or coordination judgments.

### Permutation null model

For each observed graph, discover connected actor clusters using repeated co-activity edges and select the cluster with the largest sum of edge weights. Repeat that same discovery and selection procedure in every one of 199 simulated assignments. Keep every post's content, URL, timestamp, platform, and related-group membership fixed. Shuffle actor labels only among identified posts sharing the same platform, fixed UTC time bucket (using the configured window duration), and a coarse topic proxy: each post's most common non-stopword token in the extracted batch. The actor-label counts within each stratum are preserved. Strata without at least two posts from distinct identified accounts cannot be shuffled and are reported. The max-statistic compares the strongest candidate from the whole discovery procedure, avoiding interpretation of thousands of uncorrected pairwise tests. A p-value is null if the observed maximum is absent or its simulated distribution does not vary.

Report the network-only `network_heuristic_suspicion_score` separately from its max-statistic permutation p-value. Reports also list low-confidence candidate text cues from the PTC 18-technique taxonomy, with matched spans for review. A distinct technique adds 5% to the network score only when it appears in posts by at least two actors in a repeated-evidence community; the uplift is capped at 25%. The adjusted value is `heuristic_suspicion_score`. The permutation p-value still compares the network-only score; it does not test this adjusted score. The score is an uncalibrated ranking/support measure, not a probability. Use the upper-tail Monte Carlo estimate `p = (1 + simulated maximum scores at least as large as observed) / (199 + 1)`. With 199 permutations, the smallest reportable p-value and the step size are 0.005. That coarse resolution is enough for this demo to show the null comparison and flag broad departures from the simulated baseline; it is not enough for fine-grained ranking or strong inferential claims. The report includes the seed, null mean and spread, 95th percentile, exceedance count, and stratum diagnostics so the result can be inspected and reproduced.

The 18 labels follow Da San Martino et al., [*Fine-Grained Analysis of Propaganda in News Articles*](https://aclanthology.org/D19-1565/). Our transparent lexical rules are not the paper's trained model: a cue is not evidence that a post is propaganda, deceptive, or false, and requires human review. Context.dev background articles can receive separate technique cues but never affect the account-network score.

### Connected actor communities

The Python engine consumes the extension's evidence-weighted `actor_graph` and uses NetworkX greedy modularity to partition connected networks formed by repeated edges. It reports community size, repeated content-group and burst counts, participating platforms, weighted support, representative post excerpts, and a generated explanation. Example wording uses measurable language such as “7 accounts shared 4 distinct canonical URLs across 3 content groups”; it does not label links unrelated or claim coordination. The max-statistic permutation p-value and the heuristic suspicion score remain separate fields.

### Run the engine with the sample payload

Edit [`payload.json`](payload.json) in the repository root with the request body you want to analyze. Install dependencies once with `python -m pip install -r requirements.txt`, then run:

```sh
python - <<'PY'
import asyncio
import json
from src.engine.analyzer import analyze

with open("payload.json", encoding="utf-8") as payload_file:
    payload = json.load(payload_file)

report = asyncio.run(analyze(payload))
print(json.dumps(report, indent=2))
PY
```

### Run the local FastAPI service

In another terminal, start the loopback-only endpoint used by the extension:

```sh
python -m src.api.server
```

Check readiness at `http://localhost:8000/health`, inspect the OpenAPI docs at `http://localhost:8000/docs`, and send requests to `http://localhost:8000/analyze`. The extension's **Send for analysis** button uses that endpoint. See [`src/api/README.md`](src/api/README.md) for request details.
