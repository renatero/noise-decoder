/**
 * This function is injected only after the user presses "Extract visible posts".
 * Keep it self-contained: chrome.scripting.executeScript serializes the function.
 */
export function extractVisibleEvents() {
  const clean = (value) => (value || "").replace(/\s+/g, " ").trim();
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
  const absoluteUrl = (value) => {
    try {
      return new URL(value, location.href).href;
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

  // SS.LV category/search pages render each visible advertisement as a table row
  // (`tr_123456`) whose title link is `a#dm_123456`. They do not expose an
  // advertiser identity or publication time in the listing markup, so do not
  // fabricate either value.
  if (location.hostname === "ss.lv" || location.hostname.endsWith(".ss.lv")) {
    const events = [...document.querySelectorAll('tr[id^="tr_"]')]
      .filter(isVisible)
      .map((row) => {
        const titleLink = row.querySelector('a[id^="dm_"][href*="/msg/"]');
        if (!titleLink) return null;
        const postId = row.id.slice(3) || titleLink.id.slice(3);
        const text = clean(titleLink.innerText);
        const url = absoluteUrl(titleLink.getAttribute("href"));
        if (!postId || !text || !url) return null;
        return {
          post_id: `ss.lv:${postId}`,
          actor_id: null,
          text,
          url,
          timestamp: null,
          platform: "ss.lv"
        };
      })
      .filter(Boolean);

    return {
      page: location.href,
      platform: "ss.lv",
      extracted_at: new Date().toISOString(),
      limitations: events.length
        ? ["SS.LV listing pages do not expose a seller identity or publication timestamp; actor_id and timestamp are null."]
        : ["No visible SS.LV advertisements were found. Open a category or search-results page."],
      events
    };
  }

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
    const links = [...item.querySelectorAll("a[href]")]
      .map((anchor) => absoluteUrl(anchor.getAttribute("href")))
      .filter(Boolean)
      .filter((url) => !url.startsWith("javascript:"));
    const uniqueLinks = [...new Set(links)];
    const postUrl = uniqueLinks.find((url) => /\/status\/|\/post\/|\/comments\//.test(url)) || location.href;
    const actorNode = item.querySelector('[data-testid="User-Name"], [data-testid="postAuthor"], [rel="author"], a[href*="/profile/"]');
    const actorLabel = clean(actorNode?.innerText || actorNode?.getAttribute("aria-label") || "unknown");
    const actorId = `${platform}:${actorLabel.replace(/^@/, "").toLowerCase().replace(/\s+/g, "-") || "unknown"}`;
    const postId = item.dataset.tweetId || item.dataset.postId || item.id || `${platform}:${hash(`${actorId}|${timestamp}|${text}|${postUrl}`)}`;
    if (seen.has(postId)) continue;
    seen.add(postId);

    events.push({
      post_id: postId,
      platform,
      actor_id: actorId,
      timestamp,
      text,
      url: postUrl
    });
  }

  return {
    page: location.href,
    platform,
    extracted_at: new Date().toISOString(),
    events
  };
}
