import { getApiEndpoint } from "./settings.js";
const DEFAULT_WINDOW_MINUTES = 60;
const DEFAULT_MINIMUM_ACCOUNTS = 2;
const input = document.querySelector("#endpoint");
const windowMinutesInput = document.querySelector("#window-minutes");
const minimumAccountsInput = document.querySelector("#minimum-accounts");
const saved = document.querySelector("#saved");

const endpoint = await getApiEndpoint();
const { windowMinutes, minimumAccounts } = await chrome.storage.sync.get({
  windowMinutes: DEFAULT_WINDOW_MINUTES,
  minimumAccounts: DEFAULT_MINIMUM_ACCOUNTS
});
input.value = endpoint;
windowMinutesInput.value = windowMinutes;
minimumAccountsInput.value = minimumAccounts;

document.querySelector("#save").addEventListener("click", async () => {
  const endpoint = input.value.trim();
  try {
    const windowMinutes = Number(windowMinutesInput.value);
    const minimumAccounts = Number(minimumAccountsInput.value);
    if (!Number.isInteger(windowMinutes) || windowMinutes < 1 || windowMinutes > 10080) {
      throw new Error("Set the time window to a whole number from 1 to 10080 minutes.");
    }
    if (!Number.isInteger(minimumAccounts) || minimumAccounts < 2 || minimumAccounts > 100) {
      throw new Error("Set the minimum accounts to a whole number from 2 to 100.");
    }
    const url = new URL(endpoint);
    if (!/^https?:$/.test(url.protocol)) throw new Error("Use an HTTP or HTTPS endpoint.");
    const origin = `${url.protocol}//${url.hostname}/*`;
    const alreadyGranted = await chrome.permissions.contains({ origins: [origin] });
    if (!alreadyGranted && !["localhost", "127.0.0.1"].includes(url.hostname)) {
      const granted = await chrome.permissions.request({ origins: [origin] });
      if (!granted) throw new Error("Permission to contact that API was not granted.");
    }
    await chrome.storage.sync.set({ endpoint: url.href, endpointDefaultMigrationVersion: 1, windowMinutes, minimumAccounts });
    saved.textContent = "Saved.";
  } catch (error) {
    saved.textContent = `Invalid endpoint: ${error.message}`;
  }
});
