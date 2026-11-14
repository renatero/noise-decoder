import { platformForUrl, sourceForUrl } from "./sources.js";

const MENU_ITEMS = [
  ["inspect-selection", "Inspect selected text with Noise Decoder", ["selection"]],
  ["inspect-link", "Inspect link with Noise Decoder", ["link"]],
  ["inspect-page", "Inspect page with Noise Decoder", ["page"]]
];

function clean(value) {
  return (value || "").replace(/\s+/g, " ").trim();
}

function hash(value) {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 16777619);
  }
  return (result >>> 0).toString(36);
}

async function createMenus() {
  await chrome.contextMenus.removeAll();
  for (const [id, title, contexts] of MENU_ITEMS) chrome.contextMenus.create({ id, title, contexts });
}

chrome.runtime.onInstalled.addListener(() => { createMenus(); });
chrome.runtime.onStartup.addListener(() => { createMenus(); });

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const url = info.linkUrl || info.pageUrl || tab?.url;
  if (!url?.startsWith("http")) return;
  const kind = info.menuItemId.replace("inspect-", "");
  const text = clean(info.selectionText || info.linkText || tab?.title || url).slice(0, 20000);
  const capturedAt = new Date().toISOString();
  const event = {
    post_id: `inspection:${hash(`${kind}|${url}|${text}`)}`,
    actor_id: null,
    text,
    url,
    timestamp: null,
    platform: platformForUrl(url)
  };
  await chrome.storage.local.set({
    pendingInspection: {
      event,
      kind,
      captured_at: capturedAt,
      page_title: tab?.title || null,
      source: sourceForUrl(url)
    }
  });
});
