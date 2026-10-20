import assert from "node:assert/strict";
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { CANDIDATES } from "../../src/host/candidate";

// Fake codex, agy and claude CLIs on PATH, run by the reviewer kit's own dispatcher: each answers with a review, fails
// or hangs (starting a child of its own, as a real CLI starts helpers), as CONCLAVE_FAKE_<CLI> says. No model is called.
const root = join(__dirname, "..", "..", "..");
const fixtures = join(root, "test", "fixtures");
const dispatcher = join(root, "..", "..", "kits", "reviewer", "templates", "scripts", "review-dispatch.py");
const REVIEW = "1. `range(len(values) - size)` stops one window early: window_sums([1, 2, 3, 4], 2) gives [3, 5]. Use `range(len(values) - size + 1)`.";
const FAKE = `
import json, os, subprocess, sys, time
cli, args = sys.argv[1], sys.argv[2:]
mode = os.environ.get("CONCLAVE_FAKE_" + cli.upper(), "review")
if mode == "review":
    text = ${JSON.stringify(REVIEW)} + "\\n\\nOVERALL: needs-attention\\n"
    if cli == "codex":
        open(args[args.index("-o") + 1], "w", encoding="utf-8").write(text)
    else:
        sys.stdout.write(text)
elif mode == "fail":
    sys.exit(3)
else:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    open(os.environ["CONCLAVE_FAKE_PIDS"], "w").write(json.dumps([os.getpid(), child.pid]))
    time.sleep(600)
`;

function alive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

suite("testReviewer", () => {
  let base: string;
  let api: ConclaveApi;
  let folder: vscode.Uri;
  let path: string | undefined;
  const yes = async () => true;

  suiteSetup(async () => {
    base = mkdtempSync(join(tmpdir(), "conclave-testreviewer-"));
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    api = await extension.activate();
    const work = join(base, "workspace");
    mkdirSync(join(work, "scripts"), { recursive: true });
    mkdirSync(join(work, ".conclave"), { recursive: true });
    copyFileSync(dispatcher, join(work, "scripts", "review-dispatch.py"));
    copyFileSync(join(fixtures, "workspaces", "shipped", ".conclave", "reviewers.toml"), join(work, ".conclave", "reviewers.toml"));
    folder = vscode.Uri.file(work);
    const python = await api.python(folder);
    assert.ok(python.ok, "no Python for the fake CLIs");
    const bin = join(base, "bin");
    mkdirSync(bin);
    writeFileSync(join(bin, "fake_cli.py"), FAKE);
    for (const cli of ["codex", "agy", "claude"]) {
      if (process.platform === "win32") {
        // The prefix (-3 for the launcher) stays unquoted: py.exe reads its own options from the raw command line.
        writeFileSync(join(bin, `${cli}.cmd`), `@"${python.command}" ${python.prefix.join(" ")} "${join(bin, "fake_cli.py")}" ${cli} %*\r\n`);
      } else {
        writeFileSync(join(bin, cli), `#!/bin/sh\nexec "${python.command}" ${python.prefix.join(" ")} "${join(bin, "fake_cli.py")}" ${cli} "$@"\n`);
        chmodSync(join(bin, cli), 0o755);
      }
    }
    path = process.env.PATH;
    process.env.PATH = `${bin}${delimiter}${path ?? ""}`;
    process.env.CONCLAVE_FAKE_CLAUDE = "review";
    process.env.CONCLAVE_FAKE_AGY = "fail";
    process.env.CONCLAVE_FAKE_CODEX = "hang";
  });

  suiteTeardown(() => {
    process.env.PATH = path;
    for (const name of ["CONCLAVE_FAKE_CLAUDE", "CONCLAVE_FAKE_AGY", "CONCLAVE_FAKE_CODEX", "CONCLAVE_FAKE_PIDS"]) {
      delete process.env[name];
    }
    rmSync(base, { recursive: true, force: true });
  });

  function pins(): string[] {
    return existsSync(CANDIDATES) ? readdirSync(CANDIDATES).filter((n) => n.startsWith(`pin-${process.pid}-`)) : [];
  }

  test("testReviewer: a reviewer that answers gives its review verbatim, through a temporary pin that is deleted", async () => {
    const before = pins();
    let asked = "";
    const outcome = await api.testReviewer(folder, "sonnet", { confirm: async (title, detail) => ((asked = `${title} ${detail}`), true) });
    assert.equal(asked, "Test sonnet on a planted bug? Runs review-dispatch.py with a one-reviewer temporary pin: claude-sonnet-5-5 through claude, as writer codex. This makes a real model call.");
    assert.equal(outcome.kind, "review", JSON.stringify(outcome));
    assert.ok(outcome.kind === "review" && outcome.reviewer === "sonnet" && outcome.review === `${REVIEW}\n\nOVERALL: needs-attention`);
    assert.deepEqual(pins(), before);
    assert.ok(api.recentLog().some((l) => /^Test reviewer sonnet: review from sonnet after \d+ s\.$/.test(l)));
  });

  test("testReviewer: a reviewer that fails gives the dispatcher's failover line", async () => {
    const outcome = await api.testReviewer(folder, "gemini", { confirm: yes });
    assert.deepEqual(outcome, { kind: "failover", lines: ["Skipped: gemini (exited 3)"] });
  });

  test("testReviewer: a declined confirmation starts no process", async () => {
    let runs = 0;
    const outcome = await api.testReviewer(folder, "sonnet", { confirm: async () => false, run: async () => ((runs += 1), { code: 0, stdout: "" }) });
    assert.deepEqual(outcome, { kind: "cancelled" });
    assert.equal(runs, 0);
  });

  test("testReviewer: a pin the dispatcher refuses gives its refusal", async () => {
    const pinText = readFileSync(join(folder.fsPath, ".conclave", "reviewers.toml"), "utf8").replace('model = "claude-sonnet-5-5"', 'model = "Sonnet 5.5"');
    const outcome = await api.testReviewer(folder, "sonnet", { confirm: yes, pinText });
    assert.equal(outcome.kind, "refused", JSON.stringify(outcome));
    assert.match(outcome.kind === "refused" ? outcome.message : "", /model/);
  });

  test("testReviewer: a process a cancel could not end keeps the guard and the temporary pin until it ends", async () => {
    const before = pins();
    let survivorRuns = true;
    const outcome = await api.testReviewer(folder, "sonnet", {
      confirm: yes,
      run: async () => ({ code: undefined, stdout: "", stderr: "", error: "cancelled, but 1 process did not end (4242)", survivors: [4242] }),
      alive: () => survivorRuns,
    });
    assert.deepEqual(outcome, { kind: "cancelled", note: "cancelled, but 1 process did not end (4242)" });
    assert.equal(pins().length, before.length + 1, "the temporary pin was deleted while a reviewer may still read it");
    assert.deepEqual(await api.testReviewer(folder, "sonnet", { confirm: yes }), { kind: "refused", message: "A cancelled test's process 4242 still runs" });
    // Held for as long as the survivor runs: no deadline lets a second test start beside it.
    await new Promise((r) => setTimeout(r, 1200));
    assert.equal((await api.testReviewer(folder, "sonnet", { confirm: yes })).kind, "refused");
    survivorRuns = false;
    const started = Date.now();
    while (pins().length !== before.length && Date.now() - started < 5000) {
      await new Promise((r) => setTimeout(r, 100));
    }
    assert.deepEqual(pins(), before);
    await new Promise((r) => setTimeout(r, 50));
    assert.deepEqual(await api.testReviewer(folder, "sonnet", { confirm: async () => false }), { kind: "cancelled" }, "the guard was not released");
  });

  test("testReviewer: cancelling a hung reviewer leaves no process and no temporary pin; one test runs at a time", async () => {
    const pidsFile = join(base, "pids.json");
    process.env.CONCLAVE_FAKE_PIDS = pidsFile;
    const before = pins();
    const controller = new AbortController();
    const running = api.testReviewer(folder, "astra", { confirm: yes, signal: controller.signal });
    const started = Date.now();
    while (!existsSync(pidsFile) && Date.now() - started < 15_000) {
      await new Promise((r) => setTimeout(r, 50));
    }
    await new Promise((r) => setTimeout(r, 200));
    const [fake, child] = JSON.parse(readFileSync(pidsFile, "utf8")) as [number, number];
    assert.ok(alive(fake) && alive(child));
    assert.deepEqual(await api.testReviewer(folder, "sonnet", { confirm: yes }), { kind: "refused", message: "Another test is running" });
    controller.abort();
    assert.deepEqual(await running, { kind: "cancelled" });
    const until = Date.now() + 5000;
    while ((alive(fake) || alive(child)) && Date.now() < until) {
      await new Promise((r) => setTimeout(r, 50));
    }
    assert.equal(alive(fake), false, "the hung CLI is still running");
    assert.equal(alive(child), false, "the hung CLI's child is still running");
    assert.deepEqual(pins(), before);
  });
  // Last in the suite: an unconfirmed end holds the guard until the window is reloaded.
  test("testReviewer: a cancel whose end could not be confirmed keeps the guard and the pin, even after its known survivors end", async () => {
    const before = pins();
    let survivorRuns = true;
    const error = "cancelled, but 1 process did not end (4242), and the process table could not be read to confirm that every other process ended";
    const outcome = await api.testReviewer(folder, "sonnet", {
      confirm: yes,
      run: async () => ({ code: undefined, stdout: "", stderr: "", error, survivors: [4242], unverified: true }),
      alive: () => survivorRuns,
    });
    assert.deepEqual(outcome, { kind: "cancelled", note: error });
    assert.deepEqual(await api.testReviewer(folder, "sonnet", { confirm: yes }), { kind: "refused", message: "A cancelled test's process 4242 still runs" });
    survivorRuns = false;
    await new Promise((r) => setTimeout(r, 1500));
    // The known survivor has ended, but the end was never confirmed: still held, and the pin is kept.
    assert.equal(pins().length, before.length + 1, "the temporary pin was deleted while an unseen reviewer may read it");
    const refused = await api.testReviewer(folder, "sonnet", { confirm: yes });
    assert.ok(refused.kind === "refused" && /could not be confirmed ended/.test(refused.message), JSON.stringify(refused));
  });
});
