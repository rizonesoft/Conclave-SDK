import assert from "node:assert/strict";
import { test } from "node:test";
import { canExtract, chooseSource, evictions, githubRefusal, validRef, validRepository } from "../../src/core/sdkSource";

const checkout = (path: string) => path === "R:\\GitHub\\Conclave-SDK";
const settings = (over: Partial<{ sdkPath: string; sdkRepository: string; sdkRef: string }> = {}) =>
  ({ sdkPath: "", sdkRepository: "rizonetech/Conclave-SDK", sdkRef: "", ...over });

test("sdkSource: a set sdkPath wins, and an unusable one is refused, never passed over", () => {
  assert.deepEqual(chooseSource(settings({ sdkPath: "R:\\GitHub\\Conclave-SDK", sdkRef: "main" }), checkout),
    { kind: "path", path: "R:\\GitHub\\Conclave-SDK" });
  const bad = chooseSource(settings({ sdkPath: "R:\\elsewhere", sdkRef: "main" }), checkout);
  assert.deepEqual(bad, { state: "sdk-path-invalid", message: "conclave.sdkPath is not a Conclave-SDK checkout." });
});

test("sdkSource: an sdkRef selects GitHub, defaulting the repository; nothing set is the bundle", () => {
  assert.deepEqual(chooseSource(settings({ sdkRef: "v1.2" }), checkout), { kind: "github", repository: "rizonetech/Conclave-SDK", ref: "v1.2" });
  assert.deepEqual(chooseSource(settings({ sdkRef: "main", sdkRepository: "" }), checkout),
    { kind: "github", repository: "rizonetech/Conclave-SDK", ref: "main" });
  assert.deepEqual(chooseSource(settings(), checkout), { kind: "bundled" });
});

test("sdkSource: repository and ref are validated before any request", () => {
  for (const repository of ["../x", "", "https://github.com/a/b", "a/b/c", "a/..", "a/.git", "a b/c"]) {
    assert.equal(validRepository(repository), false, repository);
    const refused = chooseSource(settings({ sdkRef: "main", sdkRepository: repository || "x" }), checkout);
    if (repository) {
      assert.ok("state" in refused && refused.state === "sdk-settings-invalid", repository);
    }
  }
  assert.ok(validRepository("rizonetech/Conclave-SDK") && validRepository("a-b/c.d_e"));
  for (const ref of ["../x", "-x", "a..b", "a b", "a~1", "a^", "x:y", "a?", "a*", "a[", "a\\b", "x.lock", "x/", "x.", "/x", "a//b", "a@{1}", "a/.b", "\u0007"]) {
    assert.equal(validRef(ref), false, JSON.stringify(ref));
  }
  for (const ref of ["main", "v1.2.3", "feature/editor", "1a2b3c4", "a".repeat(40)]) {
    assert.equal(validRef(ref), true, ref);
  }
  const empty = chooseSource(settings({ sdkRef: "   " }), checkout);
  assert.deepEqual(empty, { kind: "bundled" }, "a blank ref is no ref");
});

test("sdkSource: GitHub's answers map to their refusals", () => {
  const repo = "rizonetech/Conclave-SDK";
  assert.equal(githubRefusal(undefined, {}, repo).state, "github-offline");
  assert.equal(githubRefusal(401, {}, repo).state, "github-no-access");
  assert.equal(githubRefusal(404, {}, repo).state, "github-no-access", "an internal repository answers 404 to a non-member");
  const limited = githubRefusal(403, { "x-ratelimit-remaining": "0", "x-ratelimit-reset": "1792500000" }, repo);
  assert.equal(limited.state, "github-rate-limited");
  assert.ok(limited.state === "github-rate-limited" && limited.reset === new Date(1792500000 * 1000).toISOString());
  assert.equal(githubRefusal(403, { "x-ratelimit-remaining": "12" }, repo).state, "github-no-access");
});

test("sdkSource: the cache keeps the three most recently used SHAs", () => {
  const used = [
    { sha: "a".repeat(40), at: 1 },
    { sha: "b".repeat(40), at: 4 },
    { sha: "c".repeat(40), at: 3 },
    { sha: "d".repeat(40), at: 2 },
  ];
  assert.deepEqual(evictions(used), ["a".repeat(40)]);
  assert.deepEqual(evictions(used.slice(0, 3)), []);
});

test("sdkSource: extraction needs Python 3.11.4 or later", () => {
  assert.deepEqual(["3.11.3", "3.11.4", "3.12.0", "3.10.14", "4.0.0"].map(canExtract), [false, true, true, false, true]);
});
