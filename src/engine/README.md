# Network discovery engine

Install the engine dependency from the repository root:

```sh
python -m pip install -r requirements.txt
```

`analyze(payload)` accepts the extension request body, including its weighted `actor_graph`, events, and permutation analysis. It builds an undirected NetworkX graph and discovers communities with greedy modularity on connected components formed by repeated actor edges. One-off edges remain available in the returned graph but do not join communities.

Each community reports its actor count, number of repeated content-group and publication-burst contexts, participating platforms, summed weighted edge support, partition modularity, representative post excerpts, and a plain-language explanation. The engine preserves the supplied max-statistic permutation result separately from the heuristic community/edge score. Neither modularity nor the heuristic score is a probability or a finding of intent.

The community method is a heuristic. Very small or sparse graphs may not have a meaningful modularity partition, and actor IDs may be based on visible display names. Generated explanations use distinct canonical URL counts and observed burst durations; they do not claim that URLs are unrelated or that accounts coordinated.
