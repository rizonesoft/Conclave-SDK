import assert from "node:assert/strict";
import { test } from "node:test";
import type { NoPython, Python, RunResult } from "../../src/core/python";
import { checkWorkspace, type CheckDeps } from "../../src/core/workspaceState";

const PY: Python = { ok: true, command: "/usr/bin/python3", prefix: [], version: "3.12.3", source: "python3" };
const READY = JSON.stringify({ ok: true, schema_version: 1, reviewers: {}, routes: {}, clis: {} });

function deps(over: Partial<CheckDeps> = {}, files: string[] = ["/w/scripts/review-dispatch.py"]) {
  const runs: string[][] = [];
  const logs: string[] = [];
  const base: CheckDeps = {
    trusted: true,
    join: (a, b) => `${a}/${b}`,
    isFile: (p) => files.includes(p),
    readText: () => undefined,
    python: async () => PY,
    run: async (file, args, _timeout, cwd): Promise<RunResult> => {
      runs.push([cwd, file, ...args]);
      return { code: 0, stdout: READY };
    },
    log: (line) => logs.push(line),
    now: () => 0,
  };
  return { deps: { ...base, ...over }, runs, logs };
}

test("Restricted Mode is untrusted and starts nothing", async () => {
  let asked = false;
  const { deps: d, runs } = deps({ trusted: false, python: async () => ((asked = true), PY) });
  assert.deepEqual(await checkWorkspace("/w", d), { state: "untrusted" });
  assert.deepEqual(runs, []);
  assert.equal(asked, false, "Python was resolved in Restricted Mode");
});

test("no scripts/review-dispatch.py is no-dispatcher, before Python is looked for", async () => {
  let asked = false;
  const { deps: d, runs } = deps({ python: async () => ((asked = true), PY) }, []);
  assert.deepEqual(await checkWorkspace("/w", d), { state: "no-dispatcher" });
  assert.deepEqual(runs, []);
  assert.equal(asked, false);
});

test("no usable Python is no-python with its reason; an untrusted resolution is untrusted", async () => {
  const none: NoPython = { ok: false, fromSetting: false, untrusted: false, tried: [], message: "No Python 3.11 or later" };
  assert.deepEqual(await checkWorkspace("/w", deps({ python: async () => none }).deps),
    { state: "no-python", message: "No Python 3.11 or later" });
  const locked: NoPython = { ...none, untrusted: true };
  assert.deepEqual(await checkWorkspace("/w", deps({ python: async () => locked }).deps), { state: "untrusted" });
});

test("the dispatcher runs in the folder with the resolved Python, and every call is logged", async () => {
  const { deps: d, runs, logs } = deps({ python: async () => ({ ...PY, command: "C:\\Windows\\py.exe", prefix: ["-3"] }) });
  assert.equal((await checkWorkspace("/w", d)).state, "ready");
  assert.deepEqual(runs, [["/w", "C:\\Windows\\py.exe", "-3", "/w/scripts/review-dispatch.py", "--check-pin", "--json"]]);
  assert.equal(logs.length, 1);
  assert.match(logs[0], /^check-pin: C:\\Windows\\py\.exe -3 \/w\/scripts\/review-dispatch\.py --check-pin --json in \/w: exit 0 in 0 ms -> ready$/);
});

test("a candidate pin is passed with --pin, and its own text decides the layout", async () => {
  const read: string[] = [];
  const { deps: d, runs } = deps({ readText: (p) => (read.push(p), "reviewers = { a = { cli = 'codex' } }\n") });
  assert.equal((await checkWorkspace("/w", d, "/tmp/candidate.toml")).state, "pin-layout");
  assert.deepEqual(runs[0].slice(-2), ["--pin", "/tmp/candidate.toml"]);
  assert.deepEqual(read, ["/tmp/candidate.toml"]);
});

test("a dispatcher that cannot run is logged with why, and shown by the output rule", async () => {
  const { deps: d, logs } = deps({ run: async () => ({ code: undefined, stdout: "", error: "timed out after 30 s" }) });
  assert.equal((await checkWorkspace("/w", d)).state, "old-dispatcher");
  assert.match(logs[0], /exit none \(timed out after 30 s\)/);
});
