import assert from "node:assert/strict";
import { posix, win32 } from "node:path";
import { test } from "node:test";
import { AGENTS, initArgs, MODES, refuseTarget } from "../../src/core/repoInit";

test("repoInit: the argv names the folder, agent, mode and each kit, and WordPress's host", () => {
  assert.deepEqual(initArgs({ folder: "/r/new", agent: "all", mode: "isolated", kits: ["todo", "reviewer"] }),
    ["init", "/r/new", "--agent", "all", "--mode", "isolated", "--kit", "todo", "--kit", "reviewer"]);
  // base comes with init, and a kit named twice is passed once.
  assert.deepEqual(initArgs({ folder: "/r/new", agent: "claude", mode: "copy", kits: ["base", "todo", "todo"] }),
    ["init", "/r/new", "--agent", "claude", "--mode", "copy", "--kit", "todo"]);
  assert.deepEqual(initArgs({ folder: "/r/site", agent: "all", mode: "isolated", kits: ["wordpress"], wordpressHost: "wpcom" }),
    ["init", "/r/site", "--agent", "all", "--mode", "isolated", "--kit", "wordpress", "--wp-host", "wpcom"]);
  // A host without the WordPress kit is not passed.
  assert.ok(!initArgs({ folder: "/r/new", agent: "all", mode: "isolated", kits: [], wordpressHost: "wpcom" }).includes("--wp-host"));
});

test("repoInit: no input produces --force or any option it does not choose", () => {
  const hostile = ["--force", "todo --force", "-f", "TODO", "../x", ""];
  for (const kit of hostile) {
    assert.throws(() => initArgs({ folder: "/r/new", agent: "all", mode: "isolated", kits: [kit] }), /kit name/, kit);
  }
  assert.throws(() => initArgs({ folder: "/r/new", agent: "--force" as never, mode: "isolated", kits: [] }), /unknown agent/);
  assert.throws(() => initArgs({ folder: "/r/new", agent: "all", mode: "--force" as never, kits: [] }), /unknown mode/);
  assert.throws(() => initArgs({ folder: "/r/new", agent: "all", mode: "isolated", kits: ["wordpress"], wordpressHost: "--force" as never }), /unknown WordPress host/);
  // A folder that forge's parser would read as an option is refused.
  for (const folder of ["--force", "-f", ""]) {
    assert.throws(() => initArgs({ folder, agent: "all", mode: "isolated", kits: [] }), /must be a path/, folder);
  }
  // Every valid combination: no argument is --force.
  for (const agent of AGENTS) {
    for (const mode of MODES) {
      const args = initArgs({ folder: "/r/new", agent, mode, kits: ["todo", "wordpress"], wordpressHost: "pressable" });
      assert.ok(!args.includes("--force"), args.join(" "));
    }
  }
});

test("repoInit: a target inside a .git folder, or the SDK folder itself, is refused", () => {
  const win = { resolve: win32.resolve, sep: "\\", caseInsensitive: true };
  const nix = { resolve: posix.resolve, sep: "/", caseInsensitive: false };
  assert.match(refuseTarget("R:\\GitHub\\Site\\.git\\hooks", "R:\\GitHub\\Conclave-SDK", win) ?? "", /inside a \.git folder/);
  assert.match(refuseTarget("R:\\GitHub\\Site\\.GIT", "R:\\GitHub\\Conclave-SDK", win) ?? "", /inside a \.git folder/);
  assert.match(refuseTarget("r:\\github\\conclave-sdk\\", "R:\\GitHub\\Conclave-SDK", win) ?? "", /source folder itself/);
  assert.match(refuseTarget("/home/u/site/.git/x", "/home/u/sdk", nix) ?? "", /inside a \.git folder/);
  assert.match(refuseTarget("/home/u/sdk/../sdk", "/home/u/sdk", nix) ?? "", /source folder itself/);
  assert.equal(refuseTarget("R:\\GitHub\\New", "R:\\GitHub\\Conclave-SDK", win), undefined);
  assert.equal(refuseTarget("/home/u/new-site", "/home/u/sdk", nix), undefined);
  // On POSIX a folder differing only in case is another folder.
  assert.equal(refuseTarget("/home/u/SDK", "/home/u/sdk", nix), undefined);
});
