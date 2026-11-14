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
