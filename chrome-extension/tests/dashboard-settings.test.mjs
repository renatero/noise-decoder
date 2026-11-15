import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { DEFAULT_DASHBOARD_URL, getDashboardUrl } from "../dashboard-settings.js";

let data;

beforeEach(() => {
  data = {};
  globalThis.chrome = {
    storage: {
      sync: {
        async get(defaults) { return { ...defaults, ...data }; },
        async set(values) { Object.assign(data, values); }
      }
    }
  };
});

test("migrates the previous dashboard defaults to the current VPS", async () => {
  data.dashboardUrl = "http://2.24.173.100/";
  data.dashboardUrlMigrationVersion = 2;

  assert.equal(await getDashboardUrl(), DEFAULT_DASHBOARD_URL);
  assert.equal(DEFAULT_DASHBOARD_URL, "https://decodethenoise.today/dashboard");
  assert.equal(data.dashboardUrlMigrationVersion, 3);
});

test("migrates the earlier nip.io default to the domain while retaining migration versioning", async () => {
  data.dashboardUrl = "https://radar.188.166.112.226.nip.io/";
  data.dashboardUrlMigrationVersion = 2;

  assert.equal(await getDashboardUrl(), DEFAULT_DASHBOARD_URL);
  assert.equal(data.dashboardUrlMigrationVersion, 3);
});

test("moves the current HTTPS root setting to the dashboard path", async () => {
  data.dashboardUrl = "https://decodethenoise.today/";
  data.dashboardUrlMigrationVersion = 2;

  assert.equal(await getDashboardUrl(), DEFAULT_DASHBOARD_URL);
  assert.equal(data.dashboardUrlMigrationVersion, 3);
});

test("preserves a custom dashboard URL during migration", async () => {
  data.dashboardUrl = "https://radar.example/custom/";

  assert.equal(await getDashboardUrl(), "https://radar.example/custom/");
});
