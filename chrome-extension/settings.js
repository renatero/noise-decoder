export const DEFAULT_ENDPOINT = "https://decodethenoise.today/analyze";

const DEFAULT_MIGRATION_VERSION = 2;
const LEGACY_DEFAULTS = new Set([
  "http://2.24.173.100/analyze",
  "http://188.166.112.226:8000/analyze"
]);

/** Move existing installs from the old loopback default while preserving custom endpoints. */
export async function getApiEndpoint() {
  const settings = await chrome.storage.sync.get({
    endpoint: DEFAULT_ENDPOINT,
    endpointDefaultMigrationVersion: 0
  });
  if (settings.endpointDefaultMigrationVersion < DEFAULT_MIGRATION_VERSION) {
    let endpoint = settings.endpoint || DEFAULT_ENDPOINT;
    if (LEGACY_DEFAULTS.has(endpoint)) endpoint = DEFAULT_ENDPOINT;
    try {
      const url = new URL(endpoint);
      if (["localhost", "127.0.0.1", "::1", "[::1]"].includes(url.hostname) &&
          url.port === "8000" && /^\/analyze\/?$/.test(url.pathname)) {
        endpoint = DEFAULT_ENDPOINT;
      }
    } catch {
      endpoint = DEFAULT_ENDPOINT;
    }
    await chrome.storage.sync.set({
      endpoint,
      endpointDefaultMigrationVersion: DEFAULT_MIGRATION_VERSION
    });
    return endpoint;
  }
  return settings.endpoint || DEFAULT_ENDPOINT;
}
