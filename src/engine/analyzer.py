"""Network discovery for evidence-weighted actor relationships."""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any, TypedDict

import networkx as nx


class AnalysisReport(TypedDict):
    """Machine-readable report returned by :func:`analyze`."""

    status: str
    summary: str
    findings: list[str]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    communities: list[dict[str, Any]]
    statistics: dict[str, Any]
    permutation_analysis: dict[str, Any]
    limitations: list[str]


def discover_communities(
    payload: Mapping[str, Any], *, resolution: float = 1.0, max_examples: int = 3
) -> dict[str, Any]:
    """Build weighted actor communities and attach evidence-backed summaries."""
    graph_data = payload.get("actor_graph") or {}
    raw_nodes = graph_data.get("nodes") or []
    raw_edges = graph_data.get("edges") or []
    events_by_id: dict[str, Mapping[str, Any]] = {}
    for event in payload.get("events", []):
        if event.get("post_id") is not None:
            events_by_id.setdefault(str(event["post_id"]), event)

    graph = nx.Graph()
    for node in raw_nodes:
        actor_id = node.get("id")
        if not actor_id:
            continue
        graph.add_node(str(actor_id), **{key: value for key, value in node.items() if key != "id"})

    for edge in raw_edges:
        source = edge.get("source")
        target = edge.get("target")
        weight = _valid_weight(edge.get("weight"))
        # Network discovery focuses on repeated relationships; one-off relationships stay in the input graph.
        if not source or not target or source == target or not edge.get("repeated") or weight is None:
            continue
        graph.add_edge(str(source), str(target), **{**edge, "weight": weight})

    communities: list[dict[str, Any]] = []
    partition_scores: list[float] = []
    for component in nx.connected_components(graph):
        if len(component) < 2:
            continue
        component_graph = graph.subgraph(component).copy()
        partition = nx.community.greedy_modularity_communities(
            component_graph, weight="weight", resolution=resolution
        )
        partition_score = float(nx.community.modularity(component_graph, partition, weight="weight"))
        for members in partition:
            if len(members) < 2:
                continue
            community_graph = component_graph.subgraph(members).copy()
            communities.append(
                _summarize_community(
                    community_graph,
                    events_by_id,
                    max_examples=max_examples,
                    partition_modularity=partition_score,
                )
            )
        partition_scores.append(partition_score)

    communities.sort(
        key=lambda community: (
            -community["repeated_coordination_events"],
            -community["cluster_size"],
            community["id"],
        )
    )
    return {
        "communities": communities,
        "statistics": {
            "identified_actors": graph.number_of_nodes(),
            "repeated_actor_edges": graph.number_of_edges(),
            "connected_components": nx.number_connected_components(graph) if graph else 0,
            "communities_discovered": len(communities),
            "resolution": resolution,
            "mean_partition_modularity": round(sum(partition_scores) / len(partition_scores), 4) if partition_scores else 0.0,
        },
    }


def _summarize_community(
    graph: nx.Graph,
    events_by_id: Mapping[str, Mapping[str, Any]],
    *,
    max_examples: int,
    partition_modularity: float,
) -> dict[str, Any]:
    actor_ids = sorted(str(actor_id) for actor_id in graph.nodes)
    edges = [
        {"source": source, "target": target, **attributes}
        for source, target, attributes in graph.edges(data=True)
    ]
    repeated_contexts: dict[tuple[str, str], dict[str, Any]] = {}
    examples: list[dict[str, Any]] = []
    platforms: set[str] = set()
    for actor_id in actor_ids:
        platforms.update(str(platform) for platform in graph.nodes[actor_id].get("platforms", []) if platform)

    for edge in edges:
        for context_type, field in (("content_group", "content_groups"), ("publication_burst", "publication_bursts")):
            for context in edge.get(field, []) or []:
                context_id = str(context.get("id", ""))
                if not context_id:
                    continue
                repeated_contexts[(context_type, context_id)] = context
                example = _representative_example(
                    context_type, context, edge, events_by_id
                )
                examples.append(example)

    unique_examples = {
        (example["context_type"], example["context_id"]): example
        for example in examples
    }
    representative_examples = sorted(
        unique_examples.values(),
        key=lambda example: (
            example.get("window_start") or "",
            example["context_type"],
            example["context_id"],
        ),
    )[:max_examples]
    repeated_bursts = {
        context_id
        for (context_type, context_id) in repeated_contexts
        if context_type == "publication_burst"
    }
    repeated_groups = {
        context_id
        for (context_type, context_id) in repeated_contexts
        if context_type == "content_group"
    }
    repeated_event_count = len(repeated_contexts)
    distinct_urls = {
        url
        for edge in edges
        for field in ("content_groups", "publication_bursts")
        for context in edge.get(field, []) or []
        for support in context.get("evidence", []) or []
        for url in support.get("shared_urls", []) or []
    }
    total_weight = sum(float(edge.get("weight", 0)) for edge in edges)
    max_burst_duration = max(
        (
            duration
            for context in repeated_contexts.values()
            if context.get("window_start") and context.get("window_end")
            for duration in [_duration_seconds(context.get("window_start"), context.get("window_end"))]
            if duration is not None
        ),
        default=None,
    )
    explanation = _explanation(
        len(actor_ids), len(distinct_urls), len(repeated_groups), len(repeated_bursts), max_burst_duration
    )
    return {
        "id": "community:" + "|".join(actor_ids),
        "cluster_size": len(actor_ids),
        "actor_ids": actor_ids,
        "repeated_coordination_events": repeated_event_count,
        "repeated_content_groups": len(repeated_groups),
        "repeated_publication_bursts": len(repeated_bursts),
        "participating_platforms": sorted(platforms),
        "weighted_edge_support": round(total_weight, 3),
        "partition_modularity": round(partition_modularity, 4),
        "representative_examples": representative_examples,
        "explanation": explanation,
        "limitations": [
            "Community membership reflects repeated evidence-weighted relationships, not proof of coordination or intent.",
            "Account identifiers can be based on display names and may not uniquely identify real accounts.",
        ],
    }


def _representative_example(
    context_type: str,
    context: Mapping[str, Any],
    edge: Mapping[str, Any],
    events_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    post_ids_by_account = context.get("post_ids_by_account", {})
    posts: list[dict[str, Any]] = []
    seen_post_ids: set[str] = set()
    for actor_id in (edge["source"], edge["target"]):
        for post_id in post_ids_by_account.get(actor_id, []):
            post_id = str(post_id)
            if post_id in seen_post_ids:
                continue
            seen_post_ids.add(post_id)
            event = events_by_id.get(str(post_id))
            if not event:
                continue
            text = " ".join(str(event.get("text", "")).split())
            posts.append(
                {
                    "post_id": str(post_id),
                    "actor_id": actor_id,
                    "timestamp": event.get("timestamp"),
                    "url": event.get("url"),
                    "text_excerpt": text[:240],
                }
            )
    support_urls = sorted(
        {
            url
            for item in context.get("evidence", []) or []
            for url in item.get("shared_urls", []) or []
        }
    )
    example: dict[str, Any] = {
        "context_type": context_type,
        "context_id": context.get("id"),
        "cluster_id": context.get("cluster_id"),
        "accounts": [edge["source"], edge["target"]],
        "post_count": len({post["post_id"] for post in posts}),
        "posts": posts[:4],
        "shared_urls": support_urls,
        "edge_weight": edge.get("weight", 0),
        "matching_evidence": context.get("evidence", []),
    }
    if context_type == "publication_burst":
        example.update(
            {
                "window_start": context.get("window_start"),
                "window_end": context.get("window_end"),
            }
        )
    return example


def _explanation(
    actor_count: int,
    distinct_url_count: int,
    content_group_count: int,
    burst_count: int,
    max_burst_duration: int | None,
) -> str:
    clauses = [f"{actor_count} accounts formed a repeated-evidence network"]
    if distinct_url_count:
        clauses.append(f"sharing {distinct_url_count} distinct canonical URL{'s' if distinct_url_count != 1 else ''}")
    if content_group_count:
        clauses.append(f"across {content_group_count} content group{'s' if content_group_count != 1 else ''}")
    if burst_count:
        if max_burst_duration is not None:
            clauses.append(
                f"with {burst_count} detected publication burst{'s' if burst_count != 1 else ''} "
                f"lasting up to {max_burst_duration} seconds"
            )
        else:
            clauses.append(f"with {burst_count} detected publication burst{'s' if burst_count != 1 else ''}")
    return ", ".join(clauses) + "."


def _duration_seconds(start: Any, end: Any) -> int | None:
    if not start or not end:
        return None
    from datetime import datetime, timezone

    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None
    return max(0, round((end_dt - start_dt).total_seconds()))


def _valid_weight(value: Any) -> float | None:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return None
    return weight if isfinite(weight) and weight > 0 else None


async def analyze(payload: Mapping[str, Any] | None = None) -> AnalysisReport:
    """Return NetworkX communities and evidence-backed network summaries."""
    payload = payload or {}
    graph_data = payload.get("actor_graph") or {}
    if not graph_data.get("nodes") or not graph_data.get("edges"):
        return {
            "status": "insufficient_data",
            "summary": "No weighted actor graph was provided for network discovery.",
            "findings": [],
            "nodes": list(graph_data.get("nodes") or []),
            "edges": list(graph_data.get("edges") or []),
            "communities": [],
            "statistics": {
                "identified_actors": len(graph_data.get("nodes") or []),
                "repeated_actor_edges": sum(1 for edge in graph_data.get("edges", []) if edge.get("repeated")),
                "communities_discovered": 0,
            },
            "permutation_analysis": dict(payload.get("permutation_analysis") or {}),
            "limitations": ["The extension must provide an actor_graph with repeated evidence-weighted edges."],
        }

    result = discover_communities(payload)
    communities = result["communities"]
    summary = (
        f"Discovered {len(communities)} evidence-weighted actor communit{'y' if len(communities) == 1 else 'ies'}."
        if communities
        else "No multi-account communities were found among repeated actor relationships."
    )
    limitations = [
        "Communities are candidate networks based on the supplied evidence-weighted graph; they do not establish coordination or intent.",
        "Greedy modularity is a heuristic partition and may change with different graph data or resolution settings.",
    ]
    permutation_analysis = dict(payload.get("permutation_analysis") or {})
    if permutation_analysis.get("permutation_p_value") is not None:
        limitations.append("The permutation p-value evaluates the strongest discovered cluster and is distinct from any heuristic edge or community score.")
    return {
        "status": "complete",
        "summary": summary,
        "findings": [community["explanation"] for community in communities],
        "nodes": list(graph_data.get("nodes") or []),
        "edges": list(graph_data.get("edges") or []),
        "communities": communities,
        "statistics": result["statistics"],
        "permutation_analysis": permutation_analysis,
        "limitations": limitations,
    }
