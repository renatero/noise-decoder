export function normalizeText(value) {
  return (value || "")
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .normalize("NFKC")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

export function tokenize(value) {
  return normalizeText(value).match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu) || [];
}

export function canonicalizeUrl(value, baseUrl) {
  try {
    const url = new URL(value, baseUrl);
    if (!/^https?:$/.test(url.protocol)) return null;
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (/^(utm_.+|fbclid|gclid|dclid|gclsrc|msclkid|mc_cid|mc_eid|igshid|ref_src|ref_url|_ga|vero_id|oly_anon_id|oly_enc_id)$/i.test(key)) {
        url.searchParams.delete(key);
      }
    }
    url.hostname = url.hostname.toLowerCase();
    if ((url.protocol === "https:" && url.port === "443") || (url.protocol === "http:" && url.port === "80")) url.port = "";
    if (url.pathname.length > 1) url.pathname = url.pathname.replace(/\/+$/, "");
    url.searchParams.sort();
    return url.href;
  } catch {
    return null;
  }
}

/** Normalize events and attach shared URL and near duplicate signals. */
export function enrichEvents(rawEvents) {
  const events = rawEvents.map((event) => {
    const normalizedText = normalizeText(event.text);
    return {
      ...event,
      normalized_text: normalizedText,
      tokens: tokenize(event.text),
      url: canonicalizeUrl(event.url),
      links: [...new Set((event.links || []).map((url) => canonicalizeUrl(url)).filter(Boolean))]
    };
  });

  const linkPosts = new Map();
  events.forEach((event, index) => {
    for (const url of event.links) {
      if (!linkPosts.has(url)) linkPosts.set(url, []);
      linkPosts.get(url).push(index);
    }
  });
  const sharedByPost = events.map(() => []);
  for (const [url, indexes] of linkPosts) {
    if (indexes.length < 2) continue;
    const postIds = indexes.map((index) => events[index].post_id);
    for (const index of indexes) sharedByPost[index].push({ url, post_ids: postIds });
  }

  const tokenSets = events.map((event) => new Set(event.tokens));
  const candidates = new Map();
  const addCandidate = (left, right, reason, url = null) => {
    if (left === right) return;
    const first = Math.min(left, right);
    const second = Math.max(left, right);
    const key = `${first}:${second}`;
    if (!candidates.has(key)) candidates.set(key, { left: first, right: second, reasons: new Set(), urls: new Set() });
    const candidate = candidates.get(key);
    candidate.reasons.add(reason);
    if (url) candidate.urls.add(url);
  };

  const tokenPosts = new Map();
  const urlPosts = new Map();
  events.forEach((event, index) => {
    for (const token of tokenSets[index]) {
      if (!tokenPosts.has(token)) tokenPosts.set(token, []);
      tokenPosts.get(token).push(index);
    }
    for (const url of event.links) {
      if (!urlPosts.has(url)) urlPosts.set(url, []);
      urlPosts.get(url).push(index);
    }
  });
  for (const postIndexes of tokenPosts.values()) {
    for (let left = 0; left < postIndexes.length; left += 1) {
      for (let right = left + 1; right < postIndexes.length; right += 1) {
        addCandidate(postIndexes[left], postIndexes[right], "token_similarity");
      }
    }
  }
  for (const [url, postIndexes] of urlPosts) {
    for (let left = 0; left < postIndexes.length; left += 1) {
      for (let right = left + 1; right < postIndexes.length; right += 1) {
        addCandidate(postIndexes[left], postIndexes[right], "canonical_url", url);
      }
    }
  }

  const nearDuplicates = events.map(() => []);
  for (const candidate of candidates.values()) {
    const { left, right } = candidate;
    const a = tokenSets[left];
    const b = tokenSets[right];
    let intersection = 0;
    for (const token of a) if (b.has(token)) intersection += 1;
    const similarity = a.size && b.size ? intersection / (a.size + b.size - intersection) : 0;
    if (candidate.reasons.has("token_similarity") && (Math.min(a.size, b.size) < 3 || similarity < 0.8)) {
      candidate.reasons.delete("token_similarity");
    }
    if (!candidate.reasons.size) continue;
    const makeMatch = (index) => ({
      post_id: events[index].post_id,
      matched_by: [...candidate.reasons],
      token_similarity: Number(similarity.toFixed(3)),
      shared_urls: [...candidate.urls]
    });
    nearDuplicates[left].push(makeMatch(right));
    nearDuplicates[right].push(makeMatch(left));
  }

  return events.map((event, index) => ({
    ...event,
    features: {
      shared_urls: sharedByPost[index],
      near_duplicates: nearDuplicates[index]
    }
  }));
}

/** Group posts connected by a shared canonical URL or near-duplicate text. */
export function buildClusters(events) {
  const byId = new Map(events.map((event) => [event.post_id, event]));
  const adjacency = new Map(events.map((event) => [event.post_id, new Set()]));
  const evidenceByPair = new Map();

  for (const event of events) {
    for (const match of event.features?.near_duplicates || []) {
      if (!byId.has(match.post_id)) continue;
      adjacency.get(event.post_id).add(match.post_id);
      adjacency.get(match.post_id).add(event.post_id);

      const [first, second] = [event.post_id, match.post_id].sort();
      const key = `${first}\u0000${second}`;
      if (!evidenceByPair.has(key)) {
        evidenceByPair.set(key, {
          source_post_id: first,
          target_post_id: second,
          matched_by: [...match.matched_by].sort(),
          token_similarity: match.token_similarity,
          shared_urls: [...match.shared_urls]
        });
      }
    }
  }

  const visited = new Set();
  const clusters = [];
  for (const event of events) {
    if (visited.has(event.post_id) || !adjacency.get(event.post_id).size) continue;
    const pending = [event.post_id];
    const memberIds = [];
    visited.add(event.post_id);
    while (pending.length) {
      const postId = pending.pop();
      memberIds.push(postId);
      for (const neighbor of adjacency.get(postId)) {
        if (visited.has(neighbor)) continue;
        visited.add(neighbor);
        pending.push(neighbor);
      }
    }

    const memberSet = new Set(memberIds);
    const evidence = [...evidenceByPair.values()].filter((edge) => memberSet.has(edge.source_post_id) && memberSet.has(edge.target_post_id));
    const seed = [...memberIds].sort().join("\u0000");
    let hash = 2166136261;
    for (let index = 0; index < seed.length; index += 1) {
      hash ^= seed.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    clusters.push({
      id: `group-${(hash >>> 0).toString(36)}`,
      post_ids: memberIds,
      evidence
    });
  }

  return clusters;
}

/** Find related-post bursts that fit inside a rolling window. */
export function detectTimeBursts(events, clusters, { windowMinutes = 60, minimumAccounts = 2 } = {}) {
  const safeWindowMinutes = Number.isInteger(windowMinutes) && windowMinutes > 0 ? windowMinutes : 60;
  const safeMinimumAccounts = Number.isInteger(minimumAccounts) && minimumAccounts >= 2 ? minimumAccounts : 2;
  const windowMs = safeWindowMinutes * 60_000;
  const eventById = new Map(events.map((event) => [event.post_id, event]));
  const validEvents = events.map((event) => ({ event, timestampMs: Date.parse(event.timestamp || "") }));
  const excludedTimestampCount = validEvents.filter(({ timestampMs }) => !Number.isFinite(timestampMs)).length;
  const unidentifiableAccountCount = validEvents.filter(({ event, timestampMs }) =>
    Number.isFinite(timestampMs) && !hasAccountId(event.actor_id)
  ).length;
  const bursts = [];

  for (const cluster of clusters) {
    const posts = cluster.post_ids
      .map((postId) => eventById.get(postId))
      .filter(Boolean)
      .map((event) => ({ event, timestampMs: Date.parse(event.timestamp || "") }))
      .filter(({ timestampMs }) => Number.isFinite(timestampMs))
      .sort((left, right) => left.timestampMs - right.timestampMs);
    if (posts.length < safeMinimumAccounts) continue;

    // Sliding frequencies make each cluster scan linear after timestamp sorting.
    let right = 0;
    const accountCounts = new Map();
    let distinctAccounts = 0;
    const qualifyingWindowsByEnd = new Map();
    for (let left = 0; left < posts.length; left += 1) {
      if (right < left) right = left;
      while (right < posts.length && posts[right].timestampMs - posts[left].timestampMs <= windowMs) {
        const actorId = posts[right].event.actor_id;
        if (hasAccountId(actorId)) {
          const nextCount = (accountCounts.get(actorId) || 0) + 1;
          accountCounts.set(actorId, nextCount);
          if (nextCount === 1) distinctAccounts += 1;
        }
        right += 1;
      }

      if (distinctAccounts >= safeMinimumAccounts) {
        const endIndex = right - 1;
        // Keep the widest qualifying window for each end point; later starts are contained in it.
        if (!qualifyingWindowsByEnd.has(endIndex)) qualifyingWindowsByEnd.set(endIndex, { start: left, end: endIndex });
      }

      const actorId = posts[left].event.actor_id;
      if (hasAccountId(actorId)) {
        const nextCount = accountCounts.get(actorId) - 1;
        if (nextCount === 0) {
          accountCounts.delete(actorId);
          distinctAccounts -= 1;
        } else {
          accountCounts.set(actorId, nextCount);
        }
      }
    }

    for (const { start, end } of qualifyingWindowsByEnd.values()) {
      const windowPosts = posts.slice(start, end + 1);
      const postIds = windowPosts.map(({ event }) => event.post_id);
      const postIdSet = new Set(postIds);
      const accountIds = [...new Set(windowPosts.map(({ event }) => event.actor_id).filter(hasAccountId))];
      const evidence = cluster.evidence.filter((edge) =>
        postIdSet.has(edge.source_post_id) && postIdSet.has(edge.target_post_id)
      );
      bursts.push({
        id: `${cluster.id}:burst:${postIds[0]}:${postIds[postIds.length - 1]}`,
        cluster_id: cluster.id,
        window_start: new Date(windowPosts[0].timestampMs).toISOString(),
        window_end: new Date(windowPosts[windowPosts.length - 1].timestampMs).toISOString(),
        window_minutes: safeWindowMinutes,
        post_count: postIds.length,
        distinct_account_count: accountIds.length,
        post_ids: postIds,
        account_ids: accountIds,
        evidence
      });
    }
  }

  return {
    config: { window_minutes: safeWindowMinutes, minimum_accounts: safeMinimumAccounts },
    bursts,
    statistics: {
      events_with_valid_timestamps: events.length - excludedTimestampCount,
      excluded_invalid_timestamps: excludedTimestampCount,
      posts_without_account_id: unidentifiableAccountCount
    }
  };
}

function hasAccountId(value) {
  const actorId = typeof value === "string" ? value.trim() : "";
  return Boolean(actorId) && actorId.toLowerCase() !== "unknown" && !/:unknown$/i.test(actorId);
}

/** Record account pairs that recur in separate related-content groups or burst windows. */
export function recordCoActivity(events, clusters, timeWindowAnalysis) {
  const eventsById = new Map(events.map((event) => [event.post_id, event]));
  const pairRecords = new Map();

  const getPair = (firstActor, secondActor) => {
    const accountIds = [firstActor, secondActor].sort();
    const key = JSON.stringify(accountIds);
    if (!pairRecords.has(key)) {
      pairRecords.set(key, {
        account_ids: accountIds,
        content_groups: new Map(),
        publication_bursts: new Map()
      });
    }
    return pairRecords.get(key);
  };

  const addContextPairs = (membersByActor, type, context) => {
    const actors = [...membersByActor.keys()].filter(hasAccountId).sort();
    for (let left = 0; left < actors.length; left += 1) {
      for (let right = left + 1; right < actors.length; right += 1) {
        const firstActor = actors[left];
        const secondActor = actors[right];
        const record = getPair(firstActor, secondActor);
        const support = {
          ...context,
          post_ids_by_account: {
            [firstActor]: membersByActor.get(firstActor),
            [secondActor]: membersByActor.get(secondActor)
          },
          evidence: (context.evidence || []).filter((edge) => {
            const source = eventsById.get(edge.source_post_id);
            const target = eventsById.get(edge.target_post_id);
            return source && target && new Set([source.actor_id, target.actor_id]).size === 2 &&
              [source.actor_id, target.actor_id].includes(firstActor) &&
              [source.actor_id, target.actor_id].includes(secondActor);
          })
        };
        if (type === "content_group") record.content_groups.set(context.id, support);
        else record.publication_bursts.set(context.id, support);
      }
    }
  };

  for (const cluster of clusters) {
    const membersByActor = new Map();
    for (const postId of cluster.post_ids) {
      const event = eventsById.get(postId);
      if (!event || !hasAccountId(event.actor_id)) continue;
      if (!membersByActor.has(event.actor_id)) membersByActor.set(event.actor_id, []);
      membersByActor.get(event.actor_id).push(postId);
    }
    const memberPostIds = new Set(cluster.post_ids);
    const pairEvidence = cluster.evidence.filter((edge) => {
      const source = eventsById.get(edge.source_post_id);
      const target = eventsById.get(edge.target_post_id);
      return source && target && source.actor_id !== target.actor_id &&
        memberPostIds.has(edge.source_post_id) && memberPostIds.has(edge.target_post_id);
    });
    addContextPairs(membersByActor, "content_group", {
      id: cluster.id,
      cluster_id: cluster.id,
      evidence: pairEvidence
    });
  }

  for (const burst of timeWindowAnalysis?.bursts || []) {
    const membersByActor = new Map();
    for (const postId of burst.post_ids) {
      const event = eventsById.get(postId);
      if (!event || !hasAccountId(event.actor_id)) continue;
      if (!membersByActor.has(event.actor_id)) membersByActor.set(event.actor_id, []);
      membersByActor.get(event.actor_id).push(postId);
    }
    addContextPairs(membersByActor, "publication_burst", {
      id: burst.id,
      cluster_id: burst.cluster_id,
      window_start: burst.window_start,
      window_end: burst.window_end,
      evidence: burst.evidence
    });
  }

  const records = [...pairRecords.values()].map((record) => {
    const contentGroups = [...record.content_groups.values()];
    const publicationBursts = [...record.publication_bursts.values()];
    return {
      account_ids: record.account_ids,
      content_group_count: contentGroups.length,
      publication_burst_count: publicationBursts.length,
      repeated: contentGroups.length >= 2 || publicationBursts.length >= 2,
      evidence_assessment: contentGroups.length >= 2 ? "recurring_pattern" : "limited",
      interpretation: contentGroups.length >= 2
        ? "This pair recurs across distinct content groups; the pattern alone does not establish coordination."
        : publicationBursts.length >= 2
          ? "This pair recurs across bursts within one content group; a shared breaking-news event or other common cause may explain it."
          : "This pair appears in one content group or burst; a simultaneous response to breaking news may explain it.",
      content_groups: contentGroups,
      publication_bursts: publicationBursts
    };
  }).sort((left, right) => left.account_ids.join("\u0000").localeCompare(right.account_ids.join("\u0000")));
  const repeatedPairs = records.filter((record) => record.repeated);

  return {
    account_pairs: records,
    repeated_pairs: repeatedPairs,
    statistics: {
      account_pairs_seen: records.length,
      repeated_pairs_found: repeatedPairs.length
    }
  };
}

/** Build an undirected actor graph with inspectable, co-activity-based edge weights. */
export function buildWeightedActorGraph(events, clusters, timeWindowAnalysis, coActivity) {
  const nodesByActor = new Map();
  const eventsById = new Map(events.map((event) => [event.post_id, event]));
  const groupIdsByActor = new Map();
  const burstIdsByActor = new Map();

  for (const event of events) {
    if (!hasAccountId(event.actor_id)) continue;
    if (!nodesByActor.has(event.actor_id)) {
      nodesByActor.set(event.actor_id, {
        id: event.actor_id,
        platforms: new Set(),
        post_ids: []
      });
    }
    const node = nodesByActor.get(event.actor_id);
    node.platforms.add(event.platform);
    node.post_ids.push(event.post_id);
  }

  for (const cluster of clusters) {
    for (const postId of cluster.post_ids) {
      const event = eventsById.get(postId);
      if (!event || !hasAccountId(event.actor_id)) continue;
      if (!groupIdsByActor.has(event.actor_id)) groupIdsByActor.set(event.actor_id, new Set());
      groupIdsByActor.get(event.actor_id).add(cluster.id);
    }
  }
  for (const burst of timeWindowAnalysis?.bursts || []) {
    for (const postId of burst.post_ids) {
      const event = eventsById.get(postId);
      if (!event || !hasAccountId(event.actor_id)) continue;
      if (!burstIdsByActor.has(event.actor_id)) burstIdsByActor.set(event.actor_id, new Set());
      burstIdsByActor.get(event.actor_id).add(burst.id);
    }
  }

  const nodes = [...nodesByActor.values()].map((node) => ({
    id: node.id,
    platforms: [...node.platforms].sort(),
    post_count: node.post_ids.length,
    post_ids: node.post_ids,
    content_group_ids: [...(groupIdsByActor.get(node.id) || [])],
    content_group_count: (groupIdsByActor.get(node.id) || new Set()).size,
    publication_burst_ids: [...(burstIdsByActor.get(node.id) || [])],
    publication_burst_count: (burstIdsByActor.get(node.id) || new Set()).size
  }));

  const edges = (coActivity?.account_pairs || []).map((pair) => {
    const burstCountsByGroup = new Map();
    for (const burst of pair.publication_bursts) {
      const groupId = burst.cluster_id || "unassigned";
      burstCountsByGroup.set(groupId, (burstCountsByGroup.get(groupId) || 0) + 1);
    }
    const additionalBurstWeight = [...burstCountsByGroup.values()]
      .reduce((total, count) => total + Math.max(0, count - 1) * 0.25, 0);
    const baseWeight = pair.content_group_count || (pair.publication_burst_count ? 0.5 : 0);
    return {
      source: pair.account_ids[0],
      target: pair.account_ids[1],
      weight: Number((baseWeight + additionalBurstWeight).toFixed(3)),
      content_group_count: pair.content_group_count,
      publication_burst_count: pair.publication_burst_count,
      evidence_assessment: pair.evidence_assessment,
      repeated: pair.repeated,
      content_groups: pair.content_groups,
      publication_bursts: pair.publication_bursts
    };
  });

  return {
    directed: false,
    weight_method: {
      content_group_weight: 1,
      first_burst_additional_weight: 0,
      additional_burst_weight_within_same_group: 0.25,
      standalone_burst_weight: 0.5,
      explanation: "A first burst within a content group adds no extra weight, reducing double-counting of one shared event. Repeated bursts add modest weight; edge weights are support scores, not probabilities of coordination."
    },
    nodes,
    edges,
    statistics: {
      identified_actors: nodes.length,
      weighted_edges: edges.length,
      excluded_posts_without_account_id: events.filter((event) => !hasAccountId(event.actor_id)).length
    }
  };
}

/** Compare repeated observed actor-pair weights with a stratified permutation null. */
export function runPermutationNullModel(
  events,
  clusters,
  timeWindowAnalysis,
  coActivity,
  observedGraph,
  { permutations = 199, seed = Math.floor(Math.random() * 0x1_0000_0000) } = {}
) {
  const permutationCount = Number.isInteger(permutations) && permutations > 0 ? permutations : 199;
  const random = seededRandom(seed >>> 0);
  const windowMinutes = timeWindowAnalysis?.config?.window_minutes || 60;
  const windowMs = windowMinutes * 60_000;
  const topicKeys = topicProxyForEvents(events);
  const strata = new Map();
  let eligiblePosts = 0;
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    const timestampMs = Date.parse(event.timestamp || "");
    if (!Number.isFinite(timestampMs) || !hasAccountId(event.actor_id)) continue;
    eligiblePosts += 1;
    const timeBucket = Math.floor(timestampMs / windowMs);
    const key = JSON.stringify([event.platform || "unknown", topicKeys[index], timeBucket]);
    if (!strata.has(key)) strata.set(key, []);
    strata.get(key).push(index);
  }

  const shuffleableStrata = [...strata.values()].filter((indexes) =>
    indexes.length > 1 && new Set(indexes.map((index) => events[index].actor_id)).size > 1
  );
  const shuffleablePosts = shuffleableStrata.reduce((sum, indexes) => sum + indexes.length, 0);
  const observedRepeatedPairs = coActivity.repeated_pairs || [];
  const observedEdges = new Map((observedGraph.edges || []).map((edge) => [pairKey(edge.source, edge.target), edge]));
  const scoresByPair = new Map(observedRepeatedPairs.map((pair) => {
    const key = pairKey(pair.account_ids[0], pair.account_ids[1]);
    const edge = observedEdges.get(key);
    return [key, { pair, observedWeight: edge?.weight || 0, nullWeights: [] }];
  }));

  for (let permutation = 0; permutation < permutationCount; permutation += 1) {
    const shuffledActorIds = events.map((event) => event.actor_id);
    for (const indexes of shuffleableStrata) {
      const actorIds = indexes.map((index) => events[index].actor_id);
      fisherYatesShuffle(actorIds, random);
      indexes.forEach((index, position) => { shuffledActorIds[index] = actorIds[position]; });
    }
    const permutedEvents = events.map((event, index) => ({ ...event, actor_id: shuffledActorIds[index] }));
    const permutedCoActivity = recordCoActivity(permutedEvents, clusters, timeWindowAnalysis);
    const permutedGraph = buildWeightedActorGraph(permutedEvents, clusters, timeWindowAnalysis, permutedCoActivity);
    const permutedEdges = new Map(permutedGraph.edges.map((edge) => [pairKey(edge.source, edge.target), edge.weight]));
    for (const [key, record] of scoresByPair) record.nullWeights.push(permutedEdges.get(key) || 0);
  }

  const results = [...scoresByPair.values()].map(({ pair, observedWeight, nullWeights }) => {
    const exceedances = nullWeights.filter((weight) => weight >= observedWeight).length;
    const testable = shuffleableStrata.length > 0 && new Set(nullWeights).size > 1;
    const mean = nullWeights.reduce((sum, weight) => sum + weight, 0) / permutationCount;
    const variance = nullWeights.reduce((sum, weight) => sum + (weight - mean) ** 2, 0) / permutationCount;
    const sorted = [...nullWeights].sort((left, right) => left - right);
    const percentileIndex = Math.max(0, Math.ceil(0.95 * sorted.length) - 1);
    return {
      account_ids: pair.account_ids,
      observed_weight: observedWeight,
      null_mean_weight: Number(mean.toFixed(3)),
      null_standard_deviation: Number(Math.sqrt(variance).toFixed(3)),
      null_95th_percentile_weight: Number(sorted[percentileIndex].toFixed(3)),
      exceedances,
      p_value: testable
        ? Number(((exceedances + 1) / (permutationCount + 1)).toFixed(4))
        : null,
      testable,
      evidence_assessment: pair.evidence_assessment
    };
  });

  return {
    method: "stratified_actor_assignment_permutation",
    permutations: permutationCount,
    seed: seed >>> 0,
    strata: {
      topic_proxy: "most common non-stopword token in the extracted batch",
      time_bucket_minutes: windowMinutes,
      preserve_platform: true,
      eligible_posts: eligiblePosts,
      shuffleable_strata: shuffleableStrata.length,
      shuffleable_posts: shuffleablePosts,
      fixed_eligible_posts: eligiblePosts - shuffleablePosts
    },
    statistics: {
      repeated_pairs_tested: results.length,
      untestable_pairs: results.filter((result) => !result.testable).length,
      minimum_p_value: Number((1 / (permutationCount + 1)).toFixed(4)),
      p_value_resolution: Number((1 / (permutationCount + 1)).toFixed(4))
    },
    results,
    limitations: [
      "The dominant non-stopword token is a coarse topic proxy; actor labels are shuffled only within the same platform, topic proxy, and fixed time bucket.",
      "With 199 permutations, p-values have 0.005 resolution; this is for demonstrating the method, not high-resolution inference.",
      "Results do not adjust for testing many actor pairs and do not establish coordination or intent.",
      ...(shuffleableStrata.length ? [] : ["No strata contained multiple distinct identified accounts, so the null comparison is not testable for this sample."]),
      ...(results.some((result) => !result.testable) && shuffleableStrata.length
        ? ["Some pair-specific null distributions did not vary across permutations; their p-values are null."]
        : [])
    ]
  };
}

function topicProxyForEvents(events) {
  const commonWords = new Set([
    "about", "after", "again", "also", "amid", "been", "before", "being", "between", "could", "from", "have", "into", "just", "more", "most", "over", "said", "same", "some", "such", "than", "that", "their", "there", "these", "they", "this", "those", "through", "under", "very", "were", "what", "when", "where", "which", "while", "with", "would", "your"
  ]);
  const tokenSets = events.map((event) => new Set(event.tokens || tokenize(event.text)));
  const frequencies = new Map();
  for (const tokens of tokenSets) {
    for (const token of tokens) {
      if (token.length < 4 || commonWords.has(token)) continue;
      frequencies.set(token, (frequencies.get(token) || 0) + 1);
    }
  }
  return tokenSets.map((tokens) => [...tokens]
    .filter((token) => token.length >= 4 && !commonWords.has(token))
    .sort((left, right) => (frequencies.get(right) || 0) - (frequencies.get(left) || 0) || left.localeCompare(right))[0] || "unclassified");
}

function pairKey(firstActor, secondActor) {
  return JSON.stringify([firstActor, secondActor].sort());
}

function seededRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6D2B79F5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 0x1_0000_0000;
  };
}

function fisherYatesShuffle(values, random) {
  for (let index = values.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    [values[index], values[swapIndex]] = [values[swapIndex], values[index]];
  }
}
