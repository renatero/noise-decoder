import assert from "node:assert/strict";

const listeners = {};
const menus = [];
const openedTabs = [];

globalThis.chrome = {
  contextMenus: {
    removeAll(callback) { callback(); },
    create(menu) { menus.push(menu); },
    onClicked: { addListener(listener) { listeners.contextMenu = listener; } },
  },
  runtime: {
    onInstalled: { addListener(listener) { listeners.installed = listener; } },
    onStartup: { addListener(listener) { listeners.startup = listener; } },
  },
  action: { onClicked: { addListener(listener) { listeners.action = listener; } } },
  storage: {
    sync: {
      async get() {
        return { dashboardUrl: "https://radar.example/app?from=extension" };
      },
    },
  },
  tabs: { async create(tab) { openedTabs.push(tab); } },
};

await import("../background.js");
listeners.installed();

assert.deepEqual(menus, [{
  id: "investigate-with-coordination-radar",
  title: "Investigate with Coordination Radar",
  contexts: ["selection", "link", "page"],
}]);

async function expectHandoff(info, expectedInput, expectedType) {
  const before = openedTabs.length;
  listeners.contextMenu(info);
  for (let attempt = 0; attempt < 10 && openedTabs.length === before; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  const url = new URL(openedTabs.at(-1).url);
  assert.equal(url.searchParams.get("from"), "extension");
  assert.equal(url.searchParams.get("investigate"), expectedInput);
  assert.equal(url.searchParams.get("input_type"), expectedType);
}

await expectHandoff({ selectionText: "A selected public claim", pageUrl: "https://example.org/page" }, "A selected public claim", "selection");
await expectHandoff({ linkUrl: "https://example.org/story", pageUrl: "https://example.org/page" }, "https://example.org/story", "link");
await expectHandoff({ pageUrl: "https://example.org/page" }, "https://example.org/page", "page");

listeners.action();
for (let attempt = 0; attempt < 10 && openedTabs.length < 4; attempt += 1) {
  await new Promise((resolve) => setTimeout(resolve, 0));
}
const toolbarUrl = new URL(openedTabs.at(-1).url);
assert.equal(toolbarUrl.searchParams.get("investigate"), null);
assert.equal(toolbarUrl.searchParams.get("input_type"), "page");

console.log("background handoff tests: 4 passed");
