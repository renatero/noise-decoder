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
