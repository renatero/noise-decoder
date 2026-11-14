import test from "node:test";
import assert from "node:assert/strict";
import { buildClusters, canonicalizeUrl, detectTimeBursts, enrichEvents, recordCoActivity } from "../features.mjs";

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

test("time bursts include posts exactly on the configured rolling-window boundary", () => {
  const relatedEvents = enrichEvents([
    { ...event("first", "A local post about gardening", ["https://example.com/shared"]), actor_id: "account:a", timestamp: "2026-05-01T12:00:00Z" },
    { ...event("second", "A separate post about music", ["https://example.com/shared"]), actor_id: "account:b", timestamp: "2026-05-01T13:00:00Z" }
  ]);
  const result = detectTimeBursts(relatedEvents, buildClusters(relatedEvents), { windowMinutes: 60, minimumAccounts: 2 });

  assert.equal(result.bursts.length, 1);
  assert.deepEqual(result.bursts[0].post_ids, ["first", "second"]);
  assert.equal(result.bursts[0].distinct_account_count, 2);
  assert.equal(result.bursts[0].window_minutes, 60);
});

test("time bursts require distinct identified accounts and exclude invalid timestamps", () => {
  const sharedUrl = "https://example.com/shared";
  const relatedEvents = enrichEvents([
    { ...event("known-a", "Post one on the shared topic", [sharedUrl]), actor_id: "account:a", timestamp: "2026-05-01T12:00:00Z" },
    { ...event("unknown", "Post two on the shared topic", [sharedUrl]), actor_id: "platform:unknown", timestamp: "2026-05-01T12:01:00Z" },
    { ...event("invalid-time", "Post three on the shared topic", [sharedUrl]), actor_id: "account:b", timestamp: "not-a-date" }
  ]);
  const clusters = buildClusters(relatedEvents);
  const insufficient = detectTimeBursts(relatedEvents, clusters, { windowMinutes: 60, minimumAccounts: 2 });

  assert.equal(insufficient.bursts.length, 0);
  assert.equal(insufficient.statistics.excluded_invalid_timestamps, 1);
  assert.equal(insufficient.statistics.posts_without_account_id, 1);

  const withSecondKnownAccount = enrichEvents([
    ...relatedEvents,
    { ...event("known-b", "Post four on the shared topic", [sharedUrl]), actor_id: "account:b", timestamp: "2026-05-01T12:02:00Z" }
  ]);
  const qualifying = detectTimeBursts(withSecondKnownAccount, buildClusters(withSecondKnownAccount), {
    windowMinutes: 60,
    minimumAccounts: 2
  });
  assert.equal(qualifying.bursts.length, 1);
  assert.deepEqual(qualifying.bursts[0].post_ids, ["known-a", "unknown", "known-b"]);
  assert.equal(qualifying.bursts[0].distinct_account_count, 2);
});

test("minimum account setting suppresses bursts below the configured threshold", () => {
  const relatedEvents = enrichEvents([
    { ...event("first", "A local post about gardening", ["https://example.com/shared"]), actor_id: "account:a", timestamp: "2026-05-01T12:00:00Z" },
    { ...event("second", "A separate post about music", ["https://example.com/shared"]), actor_id: "account:b", timestamp: "2026-05-01T12:05:00Z" }
  ]);
  const result = detectTimeBursts(relatedEvents, buildClusters(relatedEvents), { windowMinutes: 60, minimumAccounts: 3 });

  assert.equal(result.config.minimum_accounts, 3);
  assert.equal(result.bursts.length, 0);
});

test("co-activity marks a pair repeated across distinct content groups", () => {
  const events = [
    { ...event("a1", "First message"), actor_id: "account:a" },
    { ...event("b1", "Second message"), actor_id: "account:b" },
    { ...event("a2", "Third message"), actor_id: "account:a" },
    { ...event("b2", "Fourth message"), actor_id: "account:b" }
  ];
  const clusters = [
    { id: "group-one", post_ids: ["a1", "b1"], evidence: [] },
    { id: "group-two", post_ids: ["a2", "b2"], evidence: [] }
  ];

  const result = recordCoActivity(events, clusters, { bursts: [] });

  assert.equal(result.statistics.account_pairs_seen, 1);
  assert.equal(result.statistics.repeated_pairs_found, 1);
  assert.deepEqual(result.repeated_pairs[0].account_ids, ["account:a", "account:b"]);
  assert.equal(result.repeated_pairs[0].content_group_count, 2);
  assert.deepEqual(result.repeated_pairs[0].content_groups.map((group) => group.id), ["group-one", "group-two"]);
});

test("co-activity marks a pair repeated across separate publication bursts", () => {
  const events = [
    { ...event("a1", "First message"), actor_id: "account:a" },
    { ...event("b1", "Second message"), actor_id: "account:b" },
    { ...event("a2", "Third message"), actor_id: "account:a" },
    { ...event("b2", "Fourth message"), actor_id: "account:b" }
  ];
  const clusters = [{ id: "group-one", post_ids: ["a1", "b1", "a2", "b2"], evidence: [] }];
  const timeAnalysis = {
    bursts: [
      { id: "burst-one", cluster_id: "group-one", post_ids: ["a1", "b1"], evidence: [] },
      { id: "burst-two", cluster_id: "group-one", post_ids: ["a2", "b2"], evidence: [] }
    ]
  };

  const result = recordCoActivity(events, clusters, timeAnalysis);
  const pair = result.repeated_pairs[0];

  assert.equal(result.repeated_pairs.length, 1);
  assert.equal(pair.content_group_count, 1);
  assert.equal(pair.publication_burst_count, 2);
  assert.equal(pair.evidence_assessment, "limited");
  assert.match(pair.interpretation, /breaking-news event or other common cause/);
  assert.deepEqual(pair.publication_bursts.map((burst) => burst.id), ["burst-one", "burst-two"]);
});

test("one content group and a burst derived from it do not count as repeated co-activity", () => {
  const events = [
    { ...event("a1", "First message"), actor_id: "account:a" },
    { ...event("b1", "Second message"), actor_id: "account:b" }
  ];
  const clusters = [{ id: "group-one", post_ids: ["a1", "b1"], evidence: [] }];
  const timeAnalysis = {
    bursts: [{ id: "burst-one", cluster_id: "group-one", post_ids: ["a1", "b1"], evidence: [] }]
  };

  const result = recordCoActivity(events, clusters, timeAnalysis);

  assert.equal(result.account_pairs.length, 1);
  assert.equal(result.account_pairs[0].content_group_count, 1);
  assert.equal(result.account_pairs[0].publication_burst_count, 1);
  assert.equal(result.account_pairs[0].repeated, false);
  assert.equal(result.account_pairs[0].evidence_assessment, "limited");
  assert.match(result.account_pairs[0].interpretation, /simultaneous response to breaking news/);
  assert.deepEqual(result.repeated_pairs, []);
});
