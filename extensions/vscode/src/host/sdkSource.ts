import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import * as vscode from "vscode";
import { bundledSource, chooseSource, type SdkRefusal, type SdkSettings, type SdkSource } from "../core/sdkSource";
import { log } from "./output";

export interface SdkSourceOptions {
  extensionPath: string;
  // True in the Extension Development Host and tests, where the SDK checkout the extension runs from is the fallback.
  development: boolean;
}

const kind = (path: string) => {
  try {
    const info = statSync(path);
    return info.isFile() ? "file" : info.isDirectory() ? "dir" : "other";
  } catch {
    return "none";
  }
};

// A folder holding a forge.py file and a kits/ folder: the types matter, not just the names.
function isSdkFolder(path: string): boolean {
  return kind(join(path, "forge.py")) === "file" && kind(join(path, "kits")) === "dir";
}

function readCommit(path: string): string | undefined {
  try {
    return readFileSync(path, "utf8").trim();
  } catch {
    return undefined;
  }
}

// Resolves the SDK forge.py runs from: the bundle, or a local checkout in conclave.sdkPath. It runs no SDK code; it
// returns the folder, the SHA (or "local") and the label log lines show.
export class SdkSourceService {
  constructor(private readonly options: SdkSourceOptions) {}

  resolve(folder?: vscode.Uri): Promise<SdkSource | SdkRefusal> {
    const config = vscode.workspace.getConfiguration("conclave", folder);
    return this.resolveWith({ sdkPath: config.get<string>("sdkPath", "") });
  }

  async resolveWith(settings: SdkSettings): Promise<SdkSource | SdkRefusal> {
    const choice = chooseSource(settings, isSdkFolder);
    if ("state" in choice) {
      return this.refuse(choice);
    }
    if (choice.kind === "path") {
      log(`SDK source: local checkout ${choice.path}`);
      return { ok: true, folder: choice.path, sha: "local", label: choice.path };
    }
    const result = bundledSource(this.options.extensionPath, this.options.development, { isSdkFolder, readCommit, join });
    return "ok" in result ? (log(`SDK source: ${result.label} ${result.folder}`), result) : this.refuse(result);
  }

  private refuse(refusal: SdkRefusal): SdkRefusal {
    log(`SDK source refused: ${refusal.message}`);
    return refusal;
  }
}
