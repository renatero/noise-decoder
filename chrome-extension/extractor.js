/**
 * Injected only after an explicit popup click. It is self-contained because
 * chrome.scripting.executeScript serializes this function.
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
    try { return new URL(value, location.href).href; } catch { return null; }
  };
  const host = location.hostname.toLowerCase().replace(/^www\./, "");
  const platform = (() => {
    if (host.endsWith("x.com") || host.endsWith("twitter.com")) return "x";
    if (host.endsWith("bsky.app")) return "bluesky";
    if (host.endsWith("youtube.com") || host === "youtu.be") return "youtube";
    if (host.endsWith("reddit.com")) return "reddit";
    if (host.endsWith("tiktok.com")) return "tiktok";
    if (host.endsWith("instagram.com")) return "instagram";
    if (host.endsWith("facebook.com")) return "facebook";
    if (host === "t.me" || host.endsWith("telegram.org")) return "telegram";
    if (host.endsWith("threads.net")) return "threads";
    if (host.includes("mastodon")) return "mastodon";
    return host;
  })();
  const canonicalUrl = () => absoluteUrl(
    document.querySelector('link[rel="canonical"]')?.getAttribute("href") ||
    document.querySelector('meta[property="og:url"]')?.getAttribute("content") || location.href
  ) || location.href;
  const actorIdFor = (label) => {
    const normalized = clean(label).replace(/^@/, "").toLowerCase().replace(/\s+/g, "-");
    return normalized ? `${platform}:${normalized.slice(0, 180)}` : null;
  };
  const linksFrom = (root, omit = []) => [...root.querySelectorAll("a[href]")]
    .filter((anchor) => !omit.some((element) => element && (element === anchor || element.contains(anchor))))
    .map((anchor) => absoluteUrl(anchor.getAttribute("href")))
    .filter(Boolean)
    .filter((url) => !omit.some((element) => element?.href === url));

  // SS.LV listing rows are public advertisements, not news articles. Their
  // listing markup does not expose seller identity or publication time.
  if (host === "ss.lv" || host.endsWith(".ss.lv")) {
    const events = [...document.querySelectorAll('tr[id^="tr_"]')]
      .filter(isVisible)
      .map((row) => {
        const titleLink = row.querySelector('a[id^="dm_"][href*="/msg/"]');
        const postId = row.id.slice(3) || titleLink?.id.slice(3);
        const text = clean(titleLink?.innerText);
        const url = absoluteUrl(titleLink?.getAttribute("href"));
        return postId && text && url ? {
          post_id: `ss.lv:${postId}`, actor_id: null, text, url, links: [], timestamp: null, platform: "ss.lv"
        } : null;
      }).filter(Boolean);
    return {
      page: location.href, platform: "ss.lv", extracted_at: new Date().toISOString(), events,
      limitations: events.length
        ? ["SS.LV listing pages do not display a seller identity or publication timestamp; actor_id and timestamp are null."]
        : ["No visible SS.LV advertisements were found. Open a category or search-results page."]
    };
  }

  const newsDomains = [
    "yle.fi", "hs.fi", "is.fi", "iltalehti.fi", "mtvuutiset.fi", "sttinfo.fi", "hbl.fi", "aamulehti.fi", "ts.fi", "kaleva.fi", "verkkouutiset.fi", "faktabaari.fi", "valtioneuvosto.fi",
    "lsm.lv", "delfi.lv", "tvnet.lv", "jauns.lv", "apollo.lv", "tv3.lv", "la.lv", "ir.lv", "nra.lv", "rebaltica.lv", "mk.gov.lv", "vp.gov.lv",
    "reuters.com", "apnews.com", "factcheck.afp.com", "bbc.com", "dw.com", "france24.com", "euronews.com", "politico.eu", "euobserver.com", "theguardian.com", "lemonde.fr", "spiegel.de", "rferl.org", "bellingcat.com", "euvsdisinfo.eu", "europa.eu",
    "npr.org", "pbs.org", "abcnews.go.com", "cbsnews.com", "nbcnews.com", "cnn.com", "foxnews.com", "msnbc.com", "nytimes.com", "wsj.com", "usatoday.com", "politico.com", "axios.com", "thehill.com", "propublica.org", "newsmax.com", "oann.com", "breitbart.com", "dailywire.com", "dailycaller.com", "huffpost.com", "motherjones.com", "newsnationnow.com", "factcheck.org", "politifact.com", "snopes.com", "congress.gov", "whitehouse.gov", "supremecourt.gov"
  ];
  const knownNewsSource = newsDomains.some((domain) => host === domain || host.endsWith(`.${domain}`));
  const jsonLdRecords = [];
  const addJsonLd = (value) => {
    if (Array.isArray(value)) value.forEach(addJsonLd);
    else if (value && typeof value === "object") {
      jsonLdRecords.push(value);
      if (value["@graph"]) addJsonLd(value["@graph"]);
    }
  };
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    try { addJsonLd(JSON.parse(script.textContent)); } catch { /* Ignore invalid JSON-LD. */ }
  }
  const schemaArticle = jsonLdRecords.find((item) => {
    const types = Array.isArray(item["@type"]) ? item["@type"] : [item["@type"]];
    return types.some((type) => /Article|NewsArticle|ReportageNewsArticle|LiveBlogPosting/i.test(type || ""));
  });

  // Inventory publishers use a metadata-first article adapter instead of a
  // brittle per-site scraper. It only handles the current article page.
  if (knownNewsSource) {
    const article = document.querySelector("article");
    const title = clean(schemaArticle?.headline || document.querySelector('meta[property="og:title"]')?.content || document.querySelector("h1")?.innerText || document.title);
    const description = clean(schemaArticle?.description || document.querySelector('meta[name="description"]')?.content);
    const articleText = clean(article?.innerText).slice(0, 12000);
    const text = clean([title, description, articleText].filter(Boolean).join("\n\n")).slice(0, 14000);
    const author = schemaArticle?.author;
    const authorName = clean(Array.isArray(author) ? author[0]?.name || author[0] : author?.name || author);
    const timestamp = schemaArticle?.datePublished || document.querySelector('meta[property="article:published_time"]')?.content || document.querySelector("time[datetime]")?.dateTime || null;
    const url = absoluteUrl(schemaArticle?.mainEntityOfPage?.["@id"] || schemaArticle?.url) || canonicalUrl();
    const event = text ? {
      post_id: `${host}:${hash(url)}`, actor_id: actorIdFor(authorName), text, url,
      links: [...new Set(linksFrom(article || document).filter((link) => link !== url))], timestamp, platform: host
    } : null;
    return {
      page: location.href, platform: host, extracted_at: new Date().toISOString(), events: event ? [event] : [],
      limitations: event
        ? ["Article metadata and visible text were collected. An absent byline or publication time is represented as null."]
        : ["No readable article was found. Open a specific article page and try again."]
    };
  }

  // Social DOMs change frequently. Collect only cards already visible; never
  // expand hidden replies, log in, or circumvent a platform's access controls.
  const selector = [
    '[data-testid="tweet"]', '[data-testid="feedItem"]', '[data-testid="postThreadItem"]', '[data-testid="post-container"]',
    "ytd-comment-thread-renderer", "ytd-comment-view-model", "shreddit-post", "shreddit-comment",
    '[data-e2e="comment-level-1"]', '[data-e2e="comment-level-2"]', 'article[role="article"]', "main article", '[role="main"] article'
  ].join(",");
  const seen = new Set();
  const events = [];
  for (const item of [...new Set([...document.querySelectorAll(selector)].filter(isVisible))]) {
    const textNode = item.querySelector('[data-testid="tweetText"], [data-testid="postText"], #content-text, [data-e2e="comment-text"], [slot="comment"], [lang], p') || item;
    const text = clean(textNode.innerText).slice(0, 12000);
    if (text.length < 2) continue;
    const timestamp = item.querySelector("time[datetime]")?.dateTime || item.querySelector("time[datetime]")?.getAttribute("datetime") || null;
    const author = item.querySelector('[data-testid="User-Name"], [data-testid="postAuthor"], #author-text, [data-e2e="comment-username"], [rel="author"], a[href*="/@"], a[href*="/user/"], a[href*="/u/"]');
    const allLinks = [...item.querySelectorAll("a[href]")].map((anchor) => absoluteUrl(anchor.getAttribute("href"))).filter(Boolean);
    const url = allLinks.find((link) => /\/status\/|\/post\/|\/comments\/|\/watch\?|\/r\/|\/video\//.test(link)) || canonicalUrl();
    const links = [...new Set(linksFrom(item, [author]).filter((link) => link !== url))];
    const actorId = actorIdFor(author?.innerText || author?.getAttribute("aria-label"));
    const postId = item.dataset.commentId || item.dataset.postId || item.dataset.tweetId || item.id || hash(`${actorId || "no-author"}|${timestamp || "no-time"}|${text}|${url}`);
    if (seen.has(postId)) continue;
    seen.add(postId);
    events.push({ post_id: `${platform}:${postId}`, actor_id: actorId, text, url, links, timestamp, platform });
  }
  return {
    page: location.href, platform, extracted_at: new Date().toISOString(), events,
    limitations: events.length
      ? ["Only visible post/comment cards were collected. Hidden, ranked-out, login-gated, and unloaded replies are not included."]
      : ["No supported visible post or comment cards were found on this page."]
  };
}
