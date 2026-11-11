import test from "node:test";
import assert from "node:assert/strict";
import { tokenProvider, login, SCOPES } from "../src/auth.js";
const config = {
  clientId: "client",
  tenantId: "tenant",
  mailbox: "owner@example.test",
  homeAccountId: "home",
  graphUserId: "user",
  preserved: "yes",
};
function fixture() {
  const store = {
    record: { schemaVersion: 1, config, cache: "old" },
    saves: 0,
    withLock: (fn) => fn(),
    async read() {
      return structuredClone(this.record);
    },
    async save(r) {
      this.saves++;
      this.record = r;
    },
  };
  const cache = {
    deserialize(s) {
      assert.equal(s, "old");
    },
    serialize: () => "refreshed",
    getAccountByHomeId: async () => ({ homeAccountId: "home" }),
  };
  const response = {
    accessToken: "synthetic-token",
    account: { homeAccountId: "home" },
  };
  const app = {
    getTokenCache: () => cache,
    acquireTokenSilent: async () => response,
    acquireTokenByDeviceCode: async () => response,
  };
  return {
    store,
    app,
    response,
    options: {
      makeApplication: () => app,
      makeClient: () => ({
        me: async () => ({ id: "user", mail: config.mailbox }),
      }),
    },
  };
}
test("silent auth reloads and persists refreshed cache without requesting send scope", async () => {
  const f = fixture();
  assert.equal(await tokenProvider(f.store, () => f.app)(), "synthetic-token");
  assert.equal(f.store.saves, 1);
  assert.equal(f.store.record.cache, "refreshed");
  assert.ok(!SCOPES.some((s) => /send/i.test(s)));
});
test("silent auth rejects changed account without saving and redacts provider errors", async () => {
  const f = fixture();
  f.response.account.homeAccountId = "different";
  await assert.rejects(
    tokenProvider(f.store, () => f.app)(),
    /needs attention/,
  );
  assert.equal(f.store.saves, 0);
  f.app.acquireTokenSilent = async () => {
    throw Error("private-provider-token");
  };
  await assert.rejects(
    tokenProvider(f.store, () => f.app)(),
    (e) => !e.message.includes("private-provider-token"),
  );
});
test("wrong mailbox login preserves existing session", async () => {
  const f = fixture();
  f.options.makeClient = () => ({
    me: async () => ({ id: "other", mail: "other@example.test" }),
  });
  await assert.rejects(
    login(f.store, config, () => {}, f.options),
    /does not match/,
  );
  assert.equal(f.store.saves, 0);
  assert.equal(f.store.record.cache, "old");
});
test("successful login preserves unrelated settings and binds verified identity", async () => {
  const f = fixture();
  const result = await login(
    f.store,
    { clientId: "client", tenantId: "tenant", mailbox: config.mailbox },
    () => {},
    f.options,
  );
  assert.equal(result.connected, true);
  assert.equal(f.store.record.config.preserved, "yes");
  assert.equal(f.store.record.config.graphUserId, "user");
  assert.equal(f.store.record.cache, "refreshed");
});
test("cancelled or incomplete login never replaces session or leaks provider errors", async () => {
  const f = fixture();
  f.app.acquireTokenByDeviceCode = async () => null;
  await assert.rejects(
    login(f.store, config, () => {}, f.options),
    /no account/,
  );
  f.app.acquireTokenByDeviceCode = async () => {
    throw Error("private-provider-token");
  };
  await assert.rejects(
    login(f.store, config, () => {}, f.options),
    (e) => !e.message.includes("private-provider-token"),
  );
  assert.equal(f.store.saves, 0);
});
