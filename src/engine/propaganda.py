"""Low-confidence lexical cues for the PTC 18-technique taxonomy.

These rules are a transparent report aid, not a trained propaganda classifier.
They deliberately report candidate text spans for human review.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


REFERENCE = {
    "title": "Fine-Grained Analysis of Propaganda in News Articles",
    "url": "https://aclanthology.org/D19-1565/",
    "taxonomy": "PTC-18",
}

# Each pattern is only a lexical cue. Context and meaning can make a match
# non-propagandistic, and many real examples will not match these rules.
_RULES = (
    ("loaded_language", "Loaded Language", "Emotionally charged or evaluative wording.", r"\b(?:evil|traitor(?:ous)?|vile|corrupt|disgusting|shameful|barbaric|heroic|cowardly|monstrous|catastrophic|pathetic|tyrannical)\b"),
    ("name_calling_labeling", "Name Calling, Labeling", "A person or group is reduced to an insulting or stigmatizing label.", r"\b(?:traitors?|parasites?|vermin|thugs?|lunatics?|crooks?|terrorists?|puppets?|enemies)\b"),
    ("repetition", "Repetition", "A short phrase is repeated in the same message.", r"\b(\w+(?:\s+\w+){1,4})\b(?:[\s,;:—-]+)\1\b"),
    ("exaggeration_minimisation", "Exaggeration, Minimization", "Absolute, inflated, or minimizing wording is used.", r"\b(?:always|never|everyone|nobody|no one|the only|completely|totally|unprecedented|nothing but|just a few|only a handful|all of them)\b"),
    ("doubt", "Doubt", "Wording explicitly casts suspicion on a claim or source.", r"\b(?:can we trust|questionable|it is unclear|it's unclear|allegedly|supposedly|who really knows|raise(s|d)? questions about|no evidence that)\b"),
    ("appeal_to_fear_prejudice", "Appeal to Fear/Prejudice", "Threat or danger language is used to provoke fear or prejudice.", r"\b(?:before it's too late|coming for (?:our|your)|terrifying threat|dangerous threat|will destroy (?:our|your)|under attack|fear of|threat to (?:our|your))\b"),
    ("flag_waving", "Flag-Waving", "A national or group identity is invoked as a reason to agree or act.", r"\b(?:defend our (?:nation|country|freedom)|real patriots|true patriot|stand with our nation|love it or leave it|for our country)\b"),
    ("causal_oversimplification", "Causal Oversimplification", "A complex outcome is attributed to a single stated cause.", r"\b(?:the only reason|solely because|all because of|is entirely caused by|is the reason (?:for|that)|one simple cause|just because of)\b"),
    ("slogans", "Slogans", "A short, memorable imperative or campaign-style phrase is used.", r"\b(?:make (?:[\w'-]+ ){1,3}great again|take back (?:our|the) [\w'-]+|[\w'-]+ first|enough is enough|stand up and fight|never back down)\b"),
    ("appeal_to_authority", "Appeal to Authority", "An authority is invoked as support without showing the underlying evidence.", r"\b(?:experts? (?:say|agree|confirm|warn)|scientists? (?:say|agree|confirm)|the science says|everyone in authority knows|according to (?:the )?(?:experts?|scientists?))\b"),
    ("black_and_white_fallacy", "Black-and-White Fallacy", "The choice is framed as only two mutually exclusive sides.", r"\b(?:either.{1,80}\bor\b|with us or against us|no middle ground|only two choices|if you're not [\w'-]+,? you're [\w'-]+)\b"),
    ("thought_terminating_cliches", "Thought-terminating Cliches", "A stock phrase is used to shut down further discussion.", r"\b(?:end of story|case closed|nothing to see here|it is what it is|move on|because i said so|wake up and stop asking)\b"),
    ("whataboutism", "Whataboutism", "A criticism is deflected by pointing to another actor or alleged inconsistency.", r"\b(?:what about (?:when|the|your|their|those)|but what about|you didn't complain when|why aren't you talking about)\b"),
    ("reductio_ad_hitlerum", "Reductio ad Hitlerum", "An opponent or position is discredited through a Hitler or Nazi comparison.", r"\b(?:just like hitler|like hitler|hitler would|sound(?:s)? like (?:a )?nazi|nazi(?:s|ism)? (?:are|is) exactly like)\b"),
    ("red_herring", "Red Herring", "A stock phrase signals a shift away from the issue under discussion.", r"\b(?:speaking of something else|that is beside the point,? but|let's talk about something else|instead of discussing that|the real issue is)\b"),
    ("bandwagon", "Bandwagon", "Popularity is presented as a reason to accept a claim or join in.", r"\b(?:everyone knows|everyone is doing it|millions have already|the whole world agrees|most people know|join the majority|all the smart people)\b"),
    ("obfuscation_vagueness", "Obfuscation, Intentional Vagueness, Confusion", "Vague or evasive wording avoids naming actors, actions, or evidence.", r"\b(?:certain people|some say|various factors|things happened|mistakes were made|at this point in time|many things were done|appropriate measures were taken)\b"),
    ("straw_man", "Straw Men", "A cue may introduce an oversimplified version of an opponent's position.", r"\b(?:so you're saying|so you are saying|you just want to|they just want to)\b[^.!?]{0,100}\b(?:everyone|all|always|never|destroy|ban|abolish)\b"),
)

_COMPILED_RULES = tuple(
    (identifier, label, description, re.compile(pattern, re.IGNORECASE))
    for identifier, label, description, pattern in _RULES
)


def _collapse_whitespace_with_offsets(value: str) -> tuple[str, list[int], list[int]]:
    """Collapse whitespace while retaining source offsets for every output char."""
    chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    index = 0
    while index < len(value):
        if value[index].isspace():
            start = index
            while index < len(value) and value[index].isspace():
                index += 1
            if chars and index < len(value):
                chars.append(" ")
                starts.append(start)
                ends.append(index)
            continue
        chars.append(value[index])
        starts.append(index)
        ends.append(index + 1)
        index += 1
    return "".join(chars), starts, ends


def detect_technique_cues(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return technique candidates with exact matched text and supporting posts."""
    matches: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events):
        original_text = str(event.get("text") or "")
        text, source_starts, source_ends = _collapse_whitespace_with_offsets(original_text)
        if not text:
            continue
        post_id = str(event.get("post_id") or event.get("id") or f"event:{index}")
        actor_id = str(event.get("actor_id") or "")
        for identifier, label, description, pattern in _COMPILED_RULES:
            match = pattern.search(text)
            if not match:
                continue
            technique = matches.setdefault(identifier, {
                "id": identifier,
                "name": label,
                "description": description,
                "confidence": "low",
                "evidence": [],
                "_post_ids": set(),
                "_actor_ids": set(),
            })
            if post_id in technique["_post_ids"]:
                continue
            technique["_post_ids"].add(post_id)
            if actor_id:
                technique["_actor_ids"].add(actor_id)
            technique["evidence"].append({
                "post_id": post_id,
                "actor_id": actor_id or None,
                "matched_text": match.group(0)[:160],
                "start_offset": source_starts[match.start()],
                "end_offset": source_ends[match.end() - 1],
                "text_excerpt": text[:240],
            })

    result = []
    for technique in matches.values():
        post_count = len(technique.pop("_post_ids"))
        actor_count = len(technique.pop("_actor_ids"))
        technique["supporting_post_count"] = post_count
        technique["supporting_actor_count"] = actor_count
        technique["corroborated_across_actors"] = actor_count >= 2
        technique["evidence"] = technique["evidence"][:5]
        result.append(technique)
    return sorted(result, key=lambda item: (-item["supporting_actor_count"], -item["supporting_post_count"], item["id"]))


def score_adjustment(communities: Sequence[Mapping[str, Any]], base_score: float) -> dict[str, Any]:
    """Apply a small bounded uplift for cross-account rhetorical cue evidence.

    A technique only contributes when its lexical cue appears in posts from at
    least two distinct actors in a discovered repeated-evidence community.
    """
    corroborated_ids = {
        technique["id"]
        for community in communities
        for technique in community.get("propaganda_techniques", [])
        if technique.get("corroborated_across_actors")
    }
    fraction = min(0.25, 0.05 * len(corroborated_ids))
    delta = round(base_score * fraction, 3)
    return {
        "method": "5% per distinct technique corroborated across at least two actors in a repeated-evidence community; capped at 25%",
        "corroborated_technique_count": len(corroborated_ids),
        "corroborated_technique_ids": sorted(corroborated_ids),
        "adjustment_fraction": round(fraction, 3),
        "score_delta": delta,
        "network_score": round(base_score, 3),
        "adjusted_score": round(base_score + delta, 3),
    }


def report_technique_analysis(techniques: list[dict[str, Any]], adjustment: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "reference": dict(REFERENCE),
        "method": "Transparent lexical cue rules; candidate labels have low confidence and require human review.",
        "techniques": techniques,
        "score_adjustment": dict(adjustment),
        "limitations": [
            "The 18-technique taxonomy is adapted from an English news-article dataset; lexical cues do not establish propaganda, intent, or truthfulness.",
            "These rules are not the paper's trained model and can miss implicit, multilingual, sarcastic, or context-dependent examples.",
        ],
    }
