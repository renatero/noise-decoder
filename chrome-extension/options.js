const DEFAULT_ENDPOINT = "http://localhost:8000/analyze";
const input = document.querySelector("#endpoint");
const saved = document.querySelector("#saved");

const { endpoint } = await chrome.storage.sync.get({ endpoint: DEFAULT_ENDPOINT });
input.value = endpoint;

document.querySelector("#save").addEventListener("click", async () => {
  const endpoint = input.value.trim();
  try {
    const url = new URL(endpoint);
    if (!/^https?:$/.test(url.protocol)) throw new Error("Use an HTTP or HTTPS endpoint.");
    const origin = `${url.protocol}//${url.hostname}/*`;
    const alreadyGranted = await chrome.permissions.contains({ origins: [origin] });
    if (!alreadyGranted && !["localhost", "127.0.0.1"].includes(url.hostname)) {
      const granted = await chrome.permissions.request({ origins: [origin] });
      if (!granted) throw new Error("Permission to contact that API was not granted.");
    }
    await chrome.storage.sync.set({ endpoint: url.href });
    saved.textContent = "Saved.";
  } catch (error) {
    saved.textContent = `Invalid endpoint: ${error.message}`;
  }
});
