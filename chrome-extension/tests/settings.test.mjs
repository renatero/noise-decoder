import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { DEFAULT_ENDPOINT, getApiEndpoint } from "../settings.js";

let data;

beforeEach(() => {
  data = {};
  globalThis.chrome = {
    storage: {
      sync: {
        async get(defaults) {
          return { ...defaults, ...data };
        },
        async set(values) {
          Object.assign(data, values);
        }
      }
    }
  };
});

test("migrates the previous localhost default to the deployed API", async () => {
  data.endpoint = "http://localhost:8000/analyze";

  assert.equal(await getApiEndpoint(), DEFAULT_ENDPOINT);
  assert.equal(data.endpoint, DEFAULT_ENDPOINT);
  assert.equal(data.endpointDefaultMigrationVersion, 1);
});

test("preserves a configured non-local API endpoint during migration", async () => {
  data.endpoint = "https://detector.example/analyze";

  assert.equal(await getApiEndpoint(), "https://detector.example/analyze");
  assert.equal(data.endpoint, "https://detector.example/analyze");
  assert.equal(data.endpointDefaultMigrationVersion, 1);
});

test("uses deployed API by default on a new install", async () => {
  assert.equal(await getApiEndpoint(), DEFAULT_ENDPOINT);
  assert.equal(data.endpoint, DEFAULT_ENDPOINT);
});
