# Noise Decoder Chrome extension

This is a Manifest V3 extension for user-initiated collection of **visible public posts** from the active tab. It does not run in the background or collect page data until the user selects **Extract visible posts**.

## Load locally

1. In Chrome, open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this `chrome-extension` directory.
4. Open a supported public feed, use the extension, review its payload, and select **Send for analysis**.

The default endpoint is `http://localhost:8000/analyze`. Change it through **Configure API endpoint**. The extension asks for permission only when you save a non-local API origin. Until the API is available, failed requests show a clearly marked mock response.

## API handoff

The extension sends this body (with extraction features attached to each event, related posts grouped into clusters, and coordination signals):

```json
{ "events": [{ "post_id": "…", "actor_id": "…", "text": "…", "url": "…", "timestamp": "…", "platform": "…" }], "clusters": [{ "id": "group-…", "post_ids": ["…", "…"], "evidence": [] }], "time_window_analysis": { "config": { "window_minutes": 60, "minimum_accounts": 2 }, "bursts": [], "statistics": {} }, "co_activity": { "account_pairs": [], "repeated_pairs": [], "statistics": {} }, "actor_graph": { "directed": false, "weight_method": {}, "nodes": [], "edges": [], "statistics": {} }, "permutation_analysis": { "method": "stratified_actor_assignment_max_cluster_permutation", "permutations": 199, "strongest_cluster": null, "heuristic_suspicion_score": null, "permutation_p_value": null, "null_max_cluster_score": {}, "strata": {}, "statistics": {}, "limitations": [] } }
```

`post_id` is the platform post ID where available (otherwise a stable page-derived ID), and `url` is the permalink for the post where one can be found. Events retain the visible `text` and also include `normalized_text`, Unicode-aware `tokens`, normalized outgoing `links`, and `features`. URL normalization removes fragments and common analytics parameters (such as `utm_*`, `fbclid`, and `gclid`), sorts remaining query parameters, and canonicalizes the host and trailing slash. `features.shared_urls` lists links found in multiple extracted posts. `features.near_duplicates` lists matching post IDs and the reason for each match: `canonical_url` means an exact normalized outgoing URL match; `token_similarity` means token-set Jaccard similarity of at least 0.8, with at least three unique tokens on each side. An inverted index narrows comparisons to pairs that share a token or URL.

`clusters` groups connected posts when any pair shares a canonical outgoing URL or meets the token-similarity threshold. Each cluster includes its member post IDs and pairwise evidence. These groups are candidate relationships for later analysis; shared links or similar text alone do not establish coordination.

`time_window_analysis` evaluates each related-post cluster using rolling windows. The settings page lets the user set the window duration (1–10,080 minutes; default 60) and minimum distinct accounts (2–100; default 2). A burst includes its time range, counts, post/account IDs, and within-window relationship evidence. Invalid timestamps are counted and excluded; posts without a usable account ID do not count toward the distinct-account threshold. The calculation reports observed patterns and does not infer intent.

`co_activity` records account pairs appearing together in content groups and publication bursts. Each pair contains its context IDs, per-account post IDs, and direct relationship evidence when available. `repeated_pairs` includes pairs seen in at least two distinct content groups or at least two distinct bursts; appearing in a group and a burst derived from that same group does not alone count as repeated. Pairs with evidence confined to one content group are labeled `limited`, including repeated bursts within that group, since a shared breaking-news event or another common cause may explain the activity. Only recurrence across distinct content groups is labeled `recurring_pattern`; no result establishes coordination.

`actor_graph` is an undirected weighted graph. Nodes are identified accounts and include their observed post, group, and burst IDs. Edges represent co-activity pairs and include their supporting contexts. The weight method is returned with the graph: each distinct content group contributes 1; the first burst in a group adds no extra weight, each additional burst in the same group adds 0.25, and a standalone burst contributes 0.5. Weights are evidence support scores, not coordination probabilities.

`permutation_analysis` repeats the actor-cluster discovery procedure in all 199 simulated assignments: it finds connected components using repeated co-activity edges and selects the component with the largest sum of edge weights. This max-statistic comparison accounts for selecting the strongest cluster and avoids interpreting thousands of uncorrected pairwise tests. Actor IDs are shuffled only among identified posts with the same platform, dominant non-stopword topic token, and fixed UTC time bucket; each post's content, URL, timestamp, and group membership stays fixed. The upper-tail plus-one p-value uses simulated maximum cluster scores, giving 0.005 resolution. This is enough to demonstrate the null-model comparison and flag broad departures, but not fine-grained ranking or strong inference. The heuristic suspicion score (summed graph edge weights) is a separate, uncalibrated score, not a probability. The report carries the random seed, null distribution summaries, and shuffleable-strata counts. The p-value is null if no observed cluster exists, no strata can be shuffled, or the maximum score does not vary across permutations.

The detector should return a JSON report with `status`, `nodes`, `edges`, `clusters`, `evidence`, `statistics`, and `limitations`. Extraction is intentionally conservative and page structure varies across platforms, so users must review the payload before submitting it.

## Feature tests

Run the feature extraction unit tests with Node.js:

```sh
node chrome-extension/tests/features.test.mjs
```
