"""Bridge normalized events to the current evidence-weighted engine interface."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

from src.collectors.bluesky import canonicalize_url
from src.engine.analyzer import analyze as engine_analyze


def _group_id(url: str) -> str:
    return f"url:{url}"


def build_engine_payload(
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build explainable shared-URL relationship evidence for Engineer A's graph engine.

    This adapter deliberately uses only observed, normalized URLs. It marks an
    actor pair as recurring only when the pair appears in at least two distinct
    URL groups; a one-off breaking-news response remains visible but is not
    passed to the community detector as a repeated edge.
    """
    events_by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    nodes: dict[str, dict[str, Any]] = {}
    engine_events: list[dict[str, Any]] = []
    for event in events:
        actor_id = str(event.get("actor_id") or "")
        if actor_id:
            node = nodes.setdefault(actor_id, {"id": actor_id, "platforms": set(), "event_ids": []})
            node["platforms"].add(event.get("platform", "unknown"))
            node["event_ids"].append(event.get("id"))
        engine_events.append(
            {
                "post_id": event.get("id"),
                "actor_id": actor_id,
                "platform": event.get("platform"),
                "timestamp": event.get("timestamp"),
                "text": event.get("text"),
                "url": event.get("source_url"),
            }
        )
        for raw_url in event.get("urls") or []:
            if canonical := canonicalize_url(str(raw_url)):
                events_by_url[canonical].append(event)

    groups: list[dict[str, Any]] = []
    pair_contexts: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for url, grouped_events in sorted(events_by_url.items()):
        by_actor: dict[str, list[str]] = defaultdict(list)
        for event in grouped_events:
            actor_id = str(event.get("actor_id") or "")
            if actor_id:
                by_actor[actor_id].append(str(event["id"]))
        if len(by_actor) < 2:
            continue
        context = {
            "id": _group_id(url),
            "post_ids": [str(event["id"]) for event in grouped_events],
            "post_ids_by_account": dict(sorted(by_actor.items())),
            "evidence": [{"shared_urls": [url]}],
        }
        groups.append(context)
        for left, right in combinations(sorted(by_actor), 2):
            pair_contexts[(left, right)].append(context)

    edges: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for (source, target), contexts in sorted(pair_contexts.items()):
        repeated = len(contexts) >= 2
        edge = {
            "id": f"{source}|{target}",
            "source": source,
            "target": target,
            "weight": float(len(contexts)),
            "repeated": repeated,
            "content_groups": contexts,
            "publication_bursts": [],
            "evidence_assessment": "recurring_pattern" if repeated else "limited",
        }
        edges.append(edge)
        evidence.append(
            {
                "edge_id": edge["id"],
                "event_ids": sorted({post_id for context in contexts for post_id in context["post_ids"]}),
                "shared_urls": [context["evidence"][0]["shared_urls"][0] for context in contexts],
                "assessment": edge["evidence_assessment"],
            }
        )

    graph_nodes = [
        {
            "id": actor_id,
            "platforms": sorted(node["platforms"]),
            "event_ids": node["event_ids"],
            "event_count": len(node["event_ids"]),
        }
        for actor_id, node in sorted(nodes.items())
    ]
    return {"events": engine_events, "actor_graph": {"nodes": graph_nodes, "edges": edges}}, groups, evidence


async def analyze_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Invoke Engineer A's engine and expose the agreed dashboard report schema."""
    payload, groups, evidence = build_engine_payload(events)
    engine_report = await engine_analyze(payload)
    communities = engine_report.get("communities", [])
    if len(events) < 2:
        status = "insufficient_data"
    elif communities:
        status = "suspicious"
    else:
        status = "inconclusive"
    return {
        "status": status,
        "nodes": engine_report.get("nodes", []),
        "edges": engine_report.get("edges", []),
        "clusters": communities or groups,
        "evidence": evidence,
        "statistics": {
            "events_observed": len(events),
            "actors_observed": len(payload["actor_graph"]["nodes"]),
            "relationship_groups": len(groups),
            "repeated_relationships": sum(1 for edge in payload["actor_graph"]["edges"] if edge["repeated"]),
            **engine_report.get("statistics", {}),
        },
        "limitations": [
            *engine_report.get("limitations", []),
            "Shared URLs and repeated public posting patterns are evidence to review, not proof of bot identity, coordination, or propaganda intent.",
        ],
        "summary": engine_report.get("summary", "Analysis completed."),
    }
