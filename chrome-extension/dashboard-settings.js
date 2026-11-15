export const DEFAULT_DASHBOARD_URL = "https://decodethenoise.today/dashboard";

const DASHBOARD_MIGRATION_VERSION = 3;
const LEGACY_DEFAULTS = new Set([
  "http://188.166.112.226:8000/",
  "https://radar.188.166.112.226.nip.io/",
  "http://2.24.173.100/",
  "https://decodethenoise.today/"
]);

/** Migrate deployed defaults from earlier builds, while retaining user overrides. */
export async function getDashboardUrl() {
  const settings = await chrome.storage.sync.get({
    dashboardUrl: DEFAULT_DASHBOARD_URL,
    dashboardUrlMigrationVersion: 0
  });
  if (settings.dashboardUrlMigrationVersion < DASHBOARD_MIGRATION_VERSION) {
    const dashboardUrl = LEGACY_DEFAULTS.has(settings.dashboardUrl)
      ? DEFAULT_DASHBOARD_URL
      : settings.dashboardUrl || DEFAULT_DASHBOARD_URL;
    await chrome.storage.sync.set({
      dashboardUrl,
      dashboardUrlMigrationVersion: DASHBOARD_MIGRATION_VERSION
    });
    return dashboardUrl;
  }
  return settings.dashboardUrl || DEFAULT_DASHBOARD_URL;
}
