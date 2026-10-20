import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmdirSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { PythonService } from "../../src/host/python";
import { removeTree } from "../../src/host/removeTree";
import { existingEntryDocs, setUpRepository } from "../../src/host/repoInit";
import { run } from "../../src/host/run";

// New repositories set up with this SDK's own forge.py (conclave.sdkPath set to the repository root). Every forge argv
// is recorded, and the suite fails if --force ever appears in one.
const root = join(__dirname, "..", "..", "..");
const sdk = join(root, "..", "..");

suite("repoInit", () => {
  let base: string;
  let api: ConclaveApi;
  const argvs: string[][] = [];
  const recording: typeof run = (file, args, timeoutMs, cwd, options) => {
    argvs.push(args);
    return run(file, args, timeoutMs, cwd, options);
  };

  suiteSetup(async () => {
    base = mkdtempSync(join(tmpdir(), "conclave-repoinit-"));
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    api = await extension.activate();
    await vscode.workspace.getConfiguration("conclave").update("sdkPath", sdk, vscode.ConfigurationTarget.Global);
  });

  // removeTree removes the links this suite makes as entries, never going through them (D02 T01 §20).
  suiteTeardown(async () => {
    await vscode.workspace.getConfiguration("conclave").update("sdkPath", undefined, vscode.ConfigurationTarget.Global);
    removeTree(base);
  });

  teardown(() => assert.ok(!argvs.some((a) => a.includes("--force")), `--force was passed: ${JSON.stringify(argvs)}`));

  test("repoInit: a new folder is set up with the todo kit and opened in a new window", async () => {
    const work = join(base, "new");
    const opened: string[] = [];
    const result = await api.setUpRepository({ folder: work, agent: "all", mode: "isolated", kits: ["todo"] }, "window", {
      run: recording, openFolder: async (uri) => opened.push(uri.fsPath),
    });
    assert.ok(result.ok, JSON.stringify(result).slice(0, 500));
    assert.ok(result.written.includes("AGENTS.md") && result.written.includes("todo/TODO-00-INDEX.md"));
    assert.ok(existsSync(join(work, "AGENTS.md")) && existsSync(join(work, "todo", "TODO-00-INDEX.md")));
    assert.deepEqual(result.kept, []);
    assert.deepEqual(result.kits.map((k) => k.kit), ["base", "todo"]);
    assert.deepEqual(opened, [vscode.Uri.file(work).fsPath]);
    assert.deepEqual(argvs.at(-1)?.slice(-8), ["init", work, "--agent", "all", "--mode", "isolated", "--kit", "todo"]);
  });

  // Adding to the workspace goes through an injected function: in this single-folder test window, a real add makes it
  // a multi-root workspace, which restarts the extension host and with it the whole test run.
  test("repoInit: an existing AGENTS.md is listed as kept, left byte for byte, and the folder is added to the workspace", async () => {
    const work = join(base, "existing");
    mkdirSync(work);
    const mine = "# My own agent instructions\n\nNot forge's.\n";
    writeFileSync(join(work, "AGENTS.md"), mine);
    const before = createHash("sha256").update(readFileSync(join(work, "AGENTS.md"))).digest("hex");
    assert.deepEqual(existingEntryDocs(work), ["AGENTS.md"]);
    const added: string[] = [];
    const result = await api.setUpRepository({ folder: work, agent: "all", mode: "isolated", kits: [] }, "workspace", {
      run: recording, addToWorkspace: (uri) => (added.push(uri.fsPath), true),
    });
    assert.ok(result.ok, JSON.stringify(result).slice(0, 500));
    assert.deepEqual(result.kept, ["AGENTS.md"]);
    assert.ok(result.skipped.includes("AGENTS.md") && !result.written.includes("AGENTS.md"));
    assert.equal(createHash("sha256").update(readFileSync(join(work, "AGENTS.md"))).digest("hex"), before, "AGENTS.md changed");
    assert.deepEqual(added, [vscode.Uri.file(work).fsPath]);
  });

  test("repoInit: a protected file that init changed without reporting it is a failure naming the file", async () => {
    const work = join(base, "guarded");
    mkdirSync(work);
    writeFileSync(join(work, "AGENTS.md"), "mine\n");
    // A run that changes AGENTS.md and reports a successful init that wrote nothing.
    const result = await api.setUpRepository({ folder: work, agent: "all", mode: "isolated", kits: [] }, "none", {
      run: async () => {
        writeFileSync(join(work, "AGENTS.md"), "changed\n");
        return { code: 0, stdout: JSON.stringify({ target: work, mode: "isolated", agent: "all", written: [], skipped: ["AGENTS.md"], kits: [] }), stderr: "" };
      },
    });
    assert.ok(!result.ok && /changed protected files it did not report writing: AGENTS\.md/.test(result.message), JSON.stringify(result));
  });

  test("repoInit: a folder inside .git, or the SDK folder itself, is refused before forge runs, also through a link", async () => {
    const runs = argvs.length;
    // Links (junctions on Windows, which need no rights) to a repository's .git folder and to an SDK folder. Both
    // targets are folders this test made under base: a link must never lead to a real repository, since a recursive
    // delete on Windows can follow a junction and delete what it points to.
    mkdirSync(join(base, "repo", ".git"), { recursive: true });
    const standIn = join(base, "sdk-stand-in");
    mkdirSync(join(standIn, "kits"), { recursive: true });
    symlinkSync(join(base, "repo", ".git"), join(base, "git-alias"), "junction");
    symlinkSync(standIn, join(base, "sdk-alias"), "junction");
    const throughGit = await api.setUpRepository({ folder: join(base, "git-alias", "new"), agent: "all", mode: "isolated", kits: [] }, "none", { run: recording });
    assert.ok(!throughGit.ok && /inside a \.git folder/.test(throughGit.message), JSON.stringify(throughGit));
    const throughSdk = await setUpRepository({ folder: join(base, "sdk-alias"), agent: "all", mode: "isolated", kits: [] }, "none", {
      source: async () => ({ folder: standIn, label: "stand-in" }), python: async () => ({ message: "not reached" }), run: recording,
    });
    assert.ok(!throughSdk.ok && /source folder itself/.test(throughSdk.message), JSON.stringify(throughSdk));
    for (const folder of ["", "relative/new"]) {
      const relative = await api.setUpRepository({ folder, agent: "all", mode: "isolated", kits: [] }, "none", { run: recording });
      assert.ok(!relative.ok && /must be an absolute path/.test(relative.message), JSON.stringify(relative));
    }
    // A dangling link: its destination inside .git does not exist yet (made, linked, removed: Windows only links to a
    // folder that exists), and forge would create it.
    mkdirSync(join(base, "repo", ".git", "not-created-yet"));
    symlinkSync(join(base, "repo", ".git", "not-created-yet"), join(base, "dangling"), "junction");
    rmdirSync(join(base, "repo", ".git", "not-created-yet"));
    const dangling = await api.setUpRepository({ folder: join(base, "dangling"), agent: "all", mode: "isolated", kits: [] }, "none", { run: recording });
    assert.ok(!dangling.ok && /inside a \.git folder/.test(dangling.message), JSON.stringify(dangling));
    const inGit = await api.setUpRepository({ folder: join(base, "repo", ".git", "new"), agent: "all", mode: "isolated", kits: [] }, "none", { run: recording });
    assert.ok(!inGit.ok && /inside a \.git folder/.test(inGit.message), JSON.stringify(inGit));
    const theSdk = await api.setUpRepository({ folder: sdk, agent: "all", mode: "isolated", kits: [] }, "none", { run: recording });
    assert.ok(!theSdk.ok && /source folder itself/.test(theSdk.message), JSON.stringify(theSdk));
    assert.equal(argvs.length, runs, "forge ran for a refused folder");
  });

  test("repoInit: a link retargeted into .git after the check is refused by forge, which writes nothing there", async () => {
    const git = join(base, "raced", ".git");
    const safe = join(base, "raced-safe");
    mkdirSync(git, { recursive: true });
    mkdirSync(safe);
    const alias = join(base, "raced-alias");
    symlinkSync(safe, alias, "junction");
    const python = new PythonService();
    try {
      const result = await setUpRepository({ folder: alias, agent: "all", mode: "isolated", kits: [] }, "none", {
        source: async () => ({ folder: sdk, label: "this checkout" }),
        // The check has passed by now: the link is moved into .git before forge runs.
        python: async () => {
          removeTree(alias);
          symlinkSync(git, alias, "junction");
          const resolved = await python.python();
          return resolved.ok ? resolved : { message: resolved.message };
        },
        run: recording,
      });
      assert.ok(!result.ok && /inside a \.git folder/.test(result.message), JSON.stringify(result).slice(0, 500));
      assert.deepEqual(readdirSync(git), [], "forge wrote inside .git");
      assert.deepEqual(readdirSync(safe), []);
    } finally {
      python.dispose();
    }
  });
});
