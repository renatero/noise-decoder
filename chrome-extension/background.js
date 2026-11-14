const DEFAULT_DASHBOARD_URL = "https://radar.188.166.112.226.nip.io/";
const MENU_ID = "investigate-with-coordination-radar";
const SETTINGS_MENU_ID = "open-coordination-radar-settings";

function createMenus() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_ID,
      title: "Investigate with Coordination Radar",
      contexts: ["selection", "link", "page"],
    });
    chrome.contextMenus.create({
      id: SETTINGS_MENU_ID,
      title: "Coordination Radar settings",
      contexts: ["action"],
    });
  });
}

function selectedInput(info) {
  if (info.linkUrl) return { value: info.linkUrl, kind: "link" };
  if (info.selectionText?.trim()) return { value: info.selectionText.trim(), kind: "selection" };
  return { value: info.pageUrl || "", kind: "page" };
}

async function dashboardUrl(input = "", kind = "page") {
  const { dashboardUrl: savedUrl } = await chrome.storage.sync.get({
    dashboardUrl: DEFAULT_DASHBOARD_URL,
  });
  const url = new URL(savedUrl);
  if (input) url.searchParams.set("investigate", input.slice(0, 12000));
  url.searchParams.set("input_type", kind);
  return url.href;
}

async function openDashboard(input, kind) {
  await chrome.tabs.create({ url: await dashboardUrl(input, kind) });
}

chrome.runtime.onInstalled.addListener(createMenus);
chrome.runtime.onStartup.addListener(createMenus);

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === SETTINGS_MENU_ID) {
    void chrome.runtime.openOptionsPage();
    return;
  }
  const { value, kind } = selectedInput(info);
  void openDashboard(value, kind);
});

chrome.action.onClicked.addListener(() => {
  void openDashboard();
});
