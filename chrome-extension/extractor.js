/**
 * This function is injected only after the user presses "Extract visible posts".
 * Keep it self-contained: chrome.scripting.executeScript serializes the function.
 */
export function extractVisibleEvents() {
  const clean = (value) => (value || "").replace(/[\u200B-\u200D\uFEFF]/g, "").replace(/\s+/g, " ").trim();
  const normalizeText = (value) => clean(value).normalize("NFKC").toLowerCase();
  const tokenize = (value) => normalizeText(value).match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu) || [];
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  };
  const hash = (value) => {
    let result = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      result ^= value.charCodeAt(index);
      result = Math.imul(result, 16777619);
    }
    return (result >>> 0).toString(36);
  };
  const normalizeUrl = (value) => {
    try {
      const url = new URL(value, location.href);
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
  };
  const platform = (() => {
    const host = location.hostname.toLowerCase();
    if (host.endsWith("x.com") || host.endsWith("twitter.com")) return "x";
    if (host.endsWith("bsky.app")) return "bluesky";
    if (host.endsWith("mastodon.social") || host.includes("mastodon")) return "mastodon";
    if (host.endsWith("reddit.com")) return "reddit";
    return host;
  })();

  // Site-specific selectors first, then the broadly supported semantic article pattern.
  const selector = [
    '[data-testid="tweet"]',
    '[data-testid="feedItem"]',
    '[data-testid="post-container"]',
    'article[role="article"]',
    'main article',
    '[role="main"] article'
  ].join(",");
  const candidates = [...document.querySelectorAll(selector)].filter(isVisible);
  const unique = [...new Set(candidates)];
  const seen = new Set();
  const events = [];

  for (const item of unique) {
    const textNode = item.querySelector('[data-testid="tweetText"], [data-testid="postText"], [lang], p') || item;
    const text = clean(textNode.innerText);
    if (text.length < 2) continue;

    const time = item.querySelector("time[datetime]");
    const timestamp = time?.dateTime || time?.getAttribute("datetime") || null;
    const actorNode = item.querySelector('[data-testid="User-Name"], [data-testid="postAuthor"], [rel="author"], a[href*="/profile/"]');
    const anchors = [...item.querySelectorAll("a[href]")];
    const postLink = anchors
      .map((anchor) => normalizeUrl(anchor.getAttribute("href")))
      .find((url) => url && /\/(?:status|post|comments)\//.test(new URL(url).pathname));
    const links = [...item.querySelectorAll("a[href]")]
      .filter((anchor) => !actorNode?.contains(anchor) && anchor !== actorNode)
      .map((anchor) => normalizeUrl(anchor.getAttribute("href")))
      .filter(Boolean)
      .filter((url) => url !== postLink);
    const uniqueLinks = [...new Set(links)];
    const postUrl = postLink || normalizeUrl(location.href);
    const actorLabel = clean(actorNode?.innerText || actorNode?.getAttribute("aria-label") || "unknown");
    const actorId = `${platform}:${actorLabel.replace(/^@/, "").toLowerCase().replace(/\s+/g, "-") || "unknown"}`;
    const postId = item.dataset.tweetId || item.dataset.postId || item.id || `${platform}:${hash(`${actorId}|${timestamp}|${text}|${postUrl}`)}`;
    if (seen.has(postId)) continue;
    seen.add(postId);

    const normalizedText = normalizeText(text);
    events.push({
      post_id: postId,
      platform,
      actor_id: actorId,
      timestamp,
      text,
      normalized_text: normalizedText,
      tokens: tokenize(text),
      url: postUrl,
      links: uniqueLinks
    });
  }

  // Batch-level signals are attached to each event so the existing { events } API body stays intact.
  const linkPosts = new Map();
  for (const event of events) {
    for (const url of event.links) {
      if (!linkPosts.has(url)) linkPosts.set(url, []);
      linkPosts.get(url).push(event.post_id);
    }
  }
  const sharedByPost = new Map(events.map((event) => [event.post_id, []]));
  for (const [url, postIds] of linkPosts) {
    if (postIds.length < 2) continue;
    for (const postId of postIds) sharedByPost.get(postId).push({ url, post_ids: postIds });
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

  // Inverted indexes generate only pairs that share a token or a canonical outgoing URL.
  const tokenPosts = new Map();
  const urlPosts = new Map();
  events.forEach((event, index) => {
    for (const token of tokenSets[index]) {
      if (!tokenPosts.has(token)) tokenPosts.set(token, []);
      tokenPosts.get(token).push(index);
    }
    for (const url of new Set(event.links)) {
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
    const score = a.size && b.size ? intersection / (a.size + b.size - intersection) : 0;
    if (candidate.reasons.has("token_similarity") && (Math.min(a.size, b.size) < 3 || score < 0.8)) {
      candidate.reasons.delete("token_similarity");
    }
    if (!candidate.reasons.size) continue;
    const leftMatch = {
      post_id: events[right].post_id,
      matched_by: [...candidate.reasons],
      token_similarity: Number(score.toFixed(3)),
      shared_urls: [...candidate.urls]
    };
    const rightMatch = {
      post_id: events[left].post_id,
      matched_by: [...candidate.reasons],
      token_similarity: Number(score.toFixed(3)),
      shared_urls: [...candidate.urls]
    };
    nearDuplicates[left].push(leftMatch);
    nearDuplicates[right].push(rightMatch);
  }
  events.forEach((event, index) => {
    event.features = {
      shared_urls: sharedByPost.get(event.post_id),
      near_duplicates: nearDuplicates[index]
    };
  });

  return {
    page: location.href,
    platform,
    extracted_at: new Date().toISOString(),
    events
  };
}
