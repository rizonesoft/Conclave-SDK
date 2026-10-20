import assert from "node:assert/strict";
import { test } from "node:test";
import { PROBE, resolvePython, type PythonDeps, type RunResult } from "../../src/core/python";

// A fake system: which names are on PATH (name -> absolute path) and what each executable answers to the probe.
function system(platform: NodeJS.Platform, onPath: Record<string, string>, answers: Record<string, RunResult>) {
  const runs: string[][] = [];
  const deps: PythonDeps = {
    platform,
    trusted: true,
    find: (name) => onPath[name],
    run: async (file, args) => {
      runs.push([file, ...args]);
      return answers[file] ?? { code: undefined, stdout: "", error: "ENOENT" };
    },
  };
  return { deps, runs };
}
const version = (v: string): RunResult => ({ code: 0, stdout: v + "\n" });

test("Windows tries py -3 first and passes -3 before the probe", async () => {
  const { deps, runs } = system("win32", { py: "C:\\Windows\\py.exe" }, { "C:\\Windows\\py.exe": version("3.14.4") });
  const found = await resolvePython("", deps);
  assert.deepEqual(found, { ok: true, command: "C:\\Windows\\py.exe", prefix: ["-3"], version: "3.14.4", source: "py -3" });
  assert.deepEqual(runs[0], ["C:\\Windows\\py.exe", "-3", ...PROBE]);
});

test("Windows falls back to python when there is no launcher", async () => {
  const { deps } = system("win32", { python: "C:\\Python312\\python.exe" }, { "C:\\Python312\\python.exe": version("3.12.3") });
  const found = await resolvePython("", deps);
  assert.ok(found.ok && found.source === "python" && found.command === "C:\\Python312\\python.exe");
});

test("Linux and WSL try python3 then python", async () => {
  const both = system("linux", { python3: "/usr/bin/python3", python: "/usr/bin/python" },
    { "/usr/bin/python3": version("3.12.3"), "/usr/bin/python": version("3.12.3") });
  const first = await resolvePython("", both.deps);
  assert.ok(first.ok && first.source === "python3");
  const only = system("linux", { python: "/usr/bin/python" }, { "/usr/bin/python": version("3.11.4") });
  const second = await resolvePython("", only.deps);
  assert.ok(second.ok && second.source === "python" && second.version === "3.11.4");
});

test("Python 3.10 is too old, and the refusal names every candidate and why", async () => {
  const { deps } = system("linux", { python3: "/usr/bin/python3" }, { "/usr/bin/python3": version("3.10.12") });
  const found = await resolvePython("", deps);
  assert.equal(found.ok, false);
  assert.ok(!found.ok);
  assert.deepEqual(found.tried, [
    { candidate: "python3", reason: "is Python 3.10.12, older than 3.11" },
    { candidate: "python", reason: "not found on PATH" },
  ]);
  assert.match(found.message, /python3: is Python 3\.10\.12, older than 3\.11; python: not found on PATH/);
  assert.equal(found.fromSetting, false);
});

test("nothing on PATH is a refusal, not a guess", async () => {
  const { deps, runs } = system("win32", {}, {});
  const found = await resolvePython("", deps);
  assert.ok(!found.ok);
  assert.deepEqual(found.tried.map((t) => t.reason), ["not found on PATH", "not found on PATH"]);
  assert.deepEqual(runs, [], "a candidate that is not on PATH must never be run by its bare name");
});

test("a set conclave.pythonPath wins over discovery", async () => {
  const { deps } = system("win32", { py: "C:\\Windows\\py.exe" },
    { "D:\\py311\\python.exe": version("3.11.9"), "C:\\Windows\\py.exe": version("3.14.4") });
  const found = await resolvePython("D:\\py311\\python.exe", deps);
  assert.deepEqual(found, { ok: true, command: "D:\\py311\\python.exe", prefix: [], version: "3.11.9", source: "conclave.pythonPath" });
});

test("a set but unusable conclave.pythonPath is refused without falling back", async () => {
  const good = { "C:\\Windows\\py.exe": version("3.14.4") };
  for (const [setting, answers, reason] of [
    ["D:\\missing\\python.exe", {}, /could not start/],
    ["D:\\old\\python.exe", { "D:\\old\\python.exe": version("3.9.18") }, /older than 3\.11/],
    ["D:\\bad\\python.exe", { "D:\\bad\\python.exe": { code: 2, stdout: "" } }, /exited 2/],
    ["pythonx", {}, /not found on PATH/],
  ] as const) {
    const { deps, runs } = system("win32", { py: "C:\\Windows\\py.exe" }, { ...good, ...answers });
    const found = await resolvePython(setting, deps);
    assert.ok(!found.ok, setting);
    assert.equal(found.fromSetting, true, setting);
    assert.match(found.tried[0].reason, reason, setting);
    assert.ok(!runs.some((r) => r[0] === "C:\\Windows\\py.exe"), `${setting}: discovery ran after a bad setting`);
  }
});

test("a batch shim is named as the reason, never run", async () => {
  const { deps, runs } = system("win32", { python: "C:\\pyenv\\shims\\python.bat" }, {});
  const found = await resolvePython("", deps);
  assert.ok(!found.ok);
  assert.match(found.tried[1].reason, /is a batch file/);
  assert.deepEqual(runs, []);
});

test("Restricted Mode finds and runs nothing, whatever the setting", async () => {
  for (const setting of ["", "/opt/python/bin/python3"]) {
    const { deps, runs } = system("linux", { python3: "/usr/bin/python3" }, { "/usr/bin/python3": version("3.12.3") });
    let looked = false;
    const found = await resolvePython(setting, { ...deps, trusted: false, find: (n) => ((looked = true), deps.find(n)) });
    assert.ok(!found.ok && found.untrusted, setting);
    assert.match(found.message, /Restricted Mode/);
    assert.deepEqual(runs, [], "a process started in Restricted Mode");
    assert.equal(looked, false, "PATH was searched in Restricted Mode");
  }
});

test("a set conclave.pythonPath on Linux and WSL, usable or not", async () => {
  const good = system("linux", { python3: "/usr/bin/python3" }, { "/opt/py/bin/python3": version("3.13.1") });
  assert.deepEqual(await resolvePython("/opt/py/bin/python3", good.deps),
    { ok: true, command: "/opt/py/bin/python3", prefix: [], version: "3.13.1", source: "conclave.pythonPath" });
  const named = system("linux", { "python3.12": "/usr/bin/python3.12" }, { "/usr/bin/python3.12": version("3.12.3") });
  const byName = await resolvePython("python3.12", named.deps);
  assert.ok(byName.ok && byName.command === "/usr/bin/python3.12");
  const old = system("linux", { python3: "/usr/bin/python3" },
    { "/opt/old/python3": version("3.10.12"), "/usr/bin/python3": version("3.12.3") });
  const refused = await resolvePython("/opt/old/python3", old.deps);
  assert.ok(!refused.ok && refused.fromSetting);
  assert.match(refused.tried[0].reason, /older than 3\.11/);
  assert.ok(!old.runs.some((r) => r[0] === "/usr/bin/python3"), "discovery ran after a bad setting");
});
