import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { existingEntryDocs } from "../../src/host/repoInit";
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

  suiteTeardown(async () => {
    await vscode.workspace.getConfiguration("conclave").update("sdkPath", undefined, vscode.ConfigurationTarget.Global);
    rmSync(base, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
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

  test("repoInit: an existing AGENTS.md is listed as kept, left byte for byte, and the folder joins the workspace", async () => {
    const work = join(base, "existing");
    mkdirSync(work);
    const mine = "# My own agent instructions\n\nNot forge's.\n";
    writeFileSync(join(work, "AGENTS.md"), mine);
    const before = createHash("sha256").update(readFileSync(join(work, "AGENTS.md"))).digest("hex");
    assert.deepEqual(existingEntryDocs(work), ["AGENTS.md"]);
    const count = vscode.workspace.workspaceFolders?.length ?? 0;
    const result = await api.setUpRepository({ folder: work, agent: "all", mode: "isolated", kits: [] }, "workspace", { run: recording });
    try {
      assert.ok(result.ok, JSON.stringify(result).slice(0, 500));
      assert.deepEqual(result.kept, ["AGENTS.md"]);
      assert.ok(result.skipped.includes("AGENTS.md") && !result.written.includes("AGENTS.md"));
      assert.equal(createHash("sha256").update(readFileSync(join(work, "AGENTS.md"))).digest("hex"), before, "AGENTS.md changed");
      const started = Date.now();
      while ((vscode.workspace.workspaceFolders?.length ?? 0) === count && Date.now() - started < 5000) {
        await new Promise((r) => setTimeout(r, 50));
      }
      assert.ok(vscode.workspace.workspaceFolders?.some((f) => f.uri.fsPath === vscode.Uri.file(work).fsPath), "the folder was not added");
    } finally {
      const index = vscode.workspace.workspaceFolders?.findIndex((f) => f.uri.fsPath === vscode.Uri.file(work).fsPath) ?? -1;
      if (index > 0) {
        vscode.workspace.updateWorkspaceFolders(index, 1);
      }
      api.forgetKitState(vscode.Uri.file(work));
    }
  });

  test("repoInit: a folder inside .git, or the SDK folder itself, is refused before forge runs", async () => {
    const runs = argvs.length;
    const inGit = await api.setUpRepository({ folder: join(base, "repo", ".git", "new"), agent: "all", mode: "isolated", kits: [] }, "none", { run: recording });
    assert.ok(!inGit.ok && /inside a \.git folder/.test(inGit.message), JSON.stringify(inGit));
    const theSdk = await api.setUpRepository({ folder: sdk, agent: "all", mode: "isolated", kits: [] }, "none", { run: recording });
    assert.ok(!theSdk.ok && /source folder itself/.test(theSdk.message), JSON.stringify(theSdk));
    assert.equal(argvs.length, runs, "forge ran for a refused folder");
  });
});
