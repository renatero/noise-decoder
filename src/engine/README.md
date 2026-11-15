# Network discovery engine

Install the engine dependency from the repository root:

```sh
python -m pip install -r requirements.txt
```

`analyze(payload)` accepts the extension request body, including its weighted `actor_graph`, events, and permutation analysis. It builds an undirected NetworkX graph and discovers communities with greedy modularity on connected components formed by repeated actor edges. One-off edges remain available in the returned graph but do not join communities.

Each community reports its actor count, number of repeated content-group and publication-burst contexts, participating platforms, summed weighted edge support, partition modularity, representative post excerpts, and a plain-language explanation. The engine preserves the supplied max-statistic permutation result separately from the heuristic community/edge score. Neither modularity nor the heuristic score is a probability or a finding of intent.

The community method is a heuristic. Very small or sparse graphs may not have a meaningful modularity partition, and actor IDs may be based on visible display names. Generated explanations use distinct canonical URL counts and observed burst durations; they do not claim that URLs are unrelated or that accounts coordinated.

## Possible propaganda-technique cues

The report also checks event text against transparent lexical rules for the 18 labels in the PTC taxonomy. A match is a low-confidence candidate, with the matching phrase and supporting post/account IDs shown for review; these rules are not the PTC paper's trained model and do not establish propaganda, intent, or truthfulness. See [Da San Martino et al., *Fine-Grained Analysis of Propaganda in News Articles*](https://aclanthology.org/D19-1565/).

The score adjustment only counts a technique when its cue appears in posts by at least two different accounts in an already-discovered repeated-evidence community. Each distinct corroborated technique adds 5% of the network-only heuristic score, capped at a 25% uplift. The report retains `network_heuristic_suspicion_score` and reports the adjusted value as `heuristic_suspicion_score`. The permutation p-value still tests the network-only score; it does not test the adjusted score. Single-account, single-post, or unclustered cues do not change the score.

## PTC benchmark

`src.engine.benchmarks.ptc` evaluates the lexical cue detector against the labeled PTC v2 / SemEval-2020 Task 11 training partition. It reports exact-span and character-overlap precision, recall, and F1 for binary span identification and end-to-end technique-labeled spans, plus sentence-level diagnostic scores derived from the corpus's sentence-per-line format. The report includes the corpus label mapping and per-technique breakdown.

Download the [PTC v2 archive from Zenodo](https://zenodo.org/records/3952415) and extract it locally. The task page limits corpus use to academic purposes; do not commit or redistribute the article text. The runner accepts either the archive's `datasets` directory or its parent directory:

```sh
curl -fL 'https://zenodo.org/records/3952415/files/datasets-v2.tgz?download=1' -o /tmp/ptc.tgz
mkdir -p /tmp/ptc
tar -xzf /tmp/ptc.tgz -C /tmp/ptc
python -m src.engine.benchmarks.ptc --data-dir /tmp/ptc/datasets --output reports/ptc-benchmark.json
PTC_DATA_DIR=/tmp/ptc/datasets python -m unittest src.engine.tests.test_ptc_benchmark -v
```

The archive's labeled split is the training partition, not a held-out test set. SemEval 2020 merges several rare labels and omits Obfuscation, Intentional Vagueness, Confusion. Consequently, the benchmark is a diagnostic of the current lexical rules, not a direct comparison to official challenge scores.
