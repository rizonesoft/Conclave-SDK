import assert from "node:assert/strict";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";

suite("Conclave extension", () => {
  test("activates in a workspace with a reviewer pin and opens the Reviewers panel", async () => {
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension, "the extension is not installed in the test host");
    const api = await extension.activate();
    assert.equal(api.output.name, "Conclave");

    const commands = await vscode.commands.getCommands(true);
    assert.ok(commands.includes("conclave.openReviewers"), "conclave.openReviewers is not registered");
    const panel = await vscode.commands.executeCommand<vscode.WebviewPanel>("conclave.openReviewers");
    assert.ok(panel, "the command returned no panel");
    assert.equal(panel.title, "Reviewers");
    panel.dispose();
  });
});
