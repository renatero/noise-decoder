import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const listeners = {};
const menus = [];
const openedTabs = [];
let settingsOpened = 0;

globalThis.chrome = {
  contextMenus: {
    removeAll(callback) { callback(); },
    create(menu) { menus.push(menu); },
    onClicked: { addListener(listener) { listeners.contextMenu = listener; } },
  },
  runtime: {
    onInstalled: { addListener(listener) { listeners.installed = listener; } },
    onStartup: { addListener(listener) { listeners.startup = listener; } },
    async openOptionsPage() { settingsOpened += 1; },
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

assert.deepEqual(menus, [
  {
    id: "investigate-with-coordination-radar",
    title: "Investigate with Coordination Radar",
    contexts: ["selection", "link", "page"],
  },
  {
    id: "open-coordination-radar-settings",
    title: "Coordination Radar settings",
    contexts: ["action"],
  },
]);

async function expectHandoff(info, expectedInput, expectedType) {
  const before = openedTabs.length;
  listeners.contextMenu({ menuItemId: "investigate-with-coordination-radar", ...info });
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

listeners.contextMenu({ menuItemId: "open-coordination-radar-settings" });
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(settingsOpened, 1);

listeners.action();
for (let attempt = 0; attempt < 10 && openedTabs.length < 4; attempt += 1) {
  await new Promise((resolve) => setTimeout(resolve, 0));
}
const toolbarUrl = new URL(openedTabs.at(-1).url);
assert.equal(toolbarUrl.searchParams.get("investigate"), null);
assert.equal(toolbarUrl.searchParams.get("input_type"), "page");

const [manifest, background] = await Promise.all([
  readFile(new URL("../manifest.json", import.meta.url), "utf8"),
  readFile(new URL("../background.js", import.meta.url), "utf8"),
]);
assert.equal(manifest.includes('"scripting"'), false);
assert.equal(manifest.includes('"host_permissions"'), false);
assert.equal(background.includes("fetch("), false);

console.log("background handoff tests: 6 passed");
