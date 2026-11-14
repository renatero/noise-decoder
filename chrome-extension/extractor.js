/**
 * This function is injected only after the user presses "Extract visible posts".
 * Keep it self-contained: chrome.scripting.executeScript serializes the function.
 */
export function extractVisibleEvents() {
  const clean = (value) => (value || "").replace(/[\u200B-\u200D\uFEFF]/g, "").replace(/\s+/g, " ").trim();
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
      .map((anchor) => absoluteUrl(anchor.getAttribute("href")))
      .find((url) => url && /\/(?:status|post|comments)\//.test(new URL(url).pathname));
    const links = anchors
      .filter((anchor) => !actorNode?.contains(anchor) && anchor !== actorNode)
      .map((anchor) => absoluteUrl(anchor.getAttribute("href")))
      .filter(Boolean)
      .filter((url) => url !== postLink);
    const uniqueLinks = [...new Set(links)];
    const postUrl = postLink || absoluteUrl(location.href);
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
      url: postUrl,
      links: uniqueLinks
    });
  }

  return {
    page: location.href,
    platform,
    extracted_at: new Date().toISOString(),
    events
  };
}
