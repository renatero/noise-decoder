import test from "node:test";
import assert from "node:assert/strict";
import { buildClusters, canonicalizeUrl, enrichEvents } from "../features.mjs";

function event(postId, text, links = []) {
  return { post_id: postId, actor_id: `actor:${postId}`, platform: "demo", timestamp: null, text, url: `https://social.example/posts/${postId}`, links };
}

function matchFor(events, postId, otherPostId) {
  return events.find((item) => item.post_id === postId).features.near_duplicates.find((match) => match.post_id === otherPostId);
}

test("capitalization differences normalize and match as duplicate text", () => {
  const events = enrichEvents([
    event("one", "Coordinated messages spread across several local channels"),
    event("two", "COORDINATED MESSAGES SPREAD ACROSS SEVERAL LOCAL CHANNELS")
  ]);

  assert.equal(events[0].normalized_text, events[1].normalized_text);
  assert.deepEqual(events[0].tokens, events[1].tokens);
  assert.deepEqual(matchFor(events, "one", "two").matched_by, ["token_similarity"]);
  assert.equal(matchFor(events, "one", "two").token_similarity, 1);
});

test("URLs with tracking variants canonicalize to the same target", () => {
  const firstUrl = "https://EXAMPLE.com:443/story/?id=42&utm_source=feed#top";
  const secondUrl = "https://example.com/story?id=42&fbclid=tracking-value";
  const events = enrichEvents([
    event("one", "First unrelated message about a garden", [firstUrl]),
    event("two", "Another separate note about music", [secondUrl])
  ]);
  const canonical = "https://example.com/story?id=42";

  assert.equal(canonicalizeUrl(firstUrl), canonical);
  assert.equal(canonicalizeUrl(secondUrl), canonical);
  assert.deepEqual(events[0].links, [canonical]);
  assert.deepEqual(matchFor(events, "one", "two").matched_by, ["canonical_url"]);
  assert.deepEqual(matchFor(events, "one", "two").shared_urls, [canonical]);
});

test("slightly rewritten messages match above the similarity threshold", () => {
  const events = enrichEvents([
    event("one", "Officials announce new climate policy today"),
    event("two", "Officials announce new climate policy today globally")
  ]);
  const match = matchFor(events, "one", "two");

  assert.ok(match);
  assert.deepEqual(match.matched_by, ["token_similarity"]);
  assert.equal(match.token_similarity, 0.857);
});

test("clusters posts by shared canonical URL and similar text, excluding unrelated posts", () => {
  const events = enrichEvents([
    event("url-one", "A quiet note about gardening", ["https://example.com/shared?utm_source=feed"]),
    event("url-two", "Completely different content about music", ["https://example.com/shared"]),
    event("text-one", "Officials announce new climate policy today"),
    event("text-two", "Officials announce new climate policy today globally"),
    event("unrelated", "A separate report about ocean temperatures")
  ]);

  const clusters = buildClusters(events);
  const memberSets = clusters.map((cluster) => new Set(cluster.post_ids));

  assert.equal(clusters.length, 2);
  assert.ok(memberSets.some((members) => members.size === 2 && members.has("url-one") && members.has("url-two")));
  assert.ok(memberSets.some((members) => members.size === 2 && members.has("text-one") && members.has("text-two")));
  assert.ok(clusters.every((cluster) => !cluster.post_ids.includes("unrelated")));
  assert.ok(clusters.every((cluster) => cluster.evidence.length === 1));
});
