import { getDashboardUrl } from "./dashboard-settings.js";
const input = document.querySelector("#dashboard-url");
const saved = document.querySelector("#saved");

const dashboardUrl = await getDashboardUrl();
input.value = dashboardUrl;

document.querySelector("#save").addEventListener("click", async () => {
  const dashboardUrl = input.value.trim();
  try {
    const url = new URL(dashboardUrl);
    if (!/^https?:$/.test(url.protocol)) throw new Error("Use an HTTP or HTTPS dashboard URL.");
    await chrome.storage.sync.set({ dashboardUrl: url.href, dashboardUrlMigrationVersion: 1 });
    saved.textContent = "Saved.";
  } catch (error) {
    saved.textContent = `Invalid dashboard URL: ${error.message}`;
  }
});
