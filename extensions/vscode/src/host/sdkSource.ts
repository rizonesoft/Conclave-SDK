import { createWriteStream, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import * as vscode from "vscode";
import {
  canExtract,
  chooseSource,
  evictions,
  githubRefusal,
  SHA,
  type SdkRefusal,
  type SdkSettings,
  type SdkSource,
} from "../core/sdkSource";
import { log } from "./output";
import type { PythonService } from "./python";
import { run } from "./run";

const EXTRACT_TIMEOUT_MS = 120_000;

export interface SdkSourceOptions {
  extensionPath: string;
  storage: string;
  // True in the Extension Development Host and tests, where the SDK checkout the extension runs from is the fallback.
  development: boolean;
  // The GitHub REST API's base; a local stand-in in tests.
  apiBase?: string;
  // The GitHub session; VS Code's sign-in by default, asked for only when the GitHub source is needed.
  getSession?: () => Promise<{ accessToken: string } | undefined>;
}

function isSdkFolder(path: string): boolean {
  return existsSync(join(path, "forge.py")) && existsSync(join(path, "kits"));
}

async function vscodeSession(): Promise<{ accessToken: string } | undefined> {
  try {
    return await vscode.authentication.getSession("github", ["repo"], { createIfNone: true });
  } catch {
    return undefined;
  }
}

// Resolves the SDK forge.py runs from: a local checkout, a GitHub commit cached per SHA, or the bundle. It runs no SDK
// code; it returns the folder, the SHA (or "local") and the label confirmations show.
export class SdkSourceService {
  private readonly inFlight = new Map<string, Promise<SdkSource | SdkRefusal>>();

  constructor(private readonly python: PythonService, private readonly options: SdkSourceOptions) {}

  resolve(folder?: vscode.Uri): Promise<SdkSource | SdkRefusal> {
    const config = vscode.workspace.getConfiguration("conclave", folder);
    return this.resolveWith({
      sdkPath: config.get<string>("sdkPath", ""),
      sdkRepository: config.get<string>("sdkRepository", ""),
      sdkRef: config.get<string>("sdkRef", ""),
    }, folder);
  }

  async resolveWith(settings: SdkSettings, folder?: vscode.Uri): Promise<SdkSource | SdkRefusal> {
    const choice = chooseSource(settings, isSdkFolder);
    if ("state" in choice) {
      log(`SDK source refused: ${choice.message}`);
      return choice;
    }
    if (choice.kind === "path") {
      log(`SDK source: local checkout ${choice.path}`);
      return { ok: true, folder: choice.path, sha: "local", label: choice.path };
    }
    if (choice.kind === "bundled") {
      return this.bundled();
    }
    const key = `${choice.repository}\n${choice.ref}`;
    let call = this.inFlight.get(key);
    if (!call) {
      call = this.github(choice.repository, choice.ref, folder).finally(() => this.inFlight.delete(key));
      this.inFlight.set(key, call);
    }
    return call;
  }

  private bundled(): SdkSource | SdkRefusal {
    const bundle = join(this.options.extensionPath, "sdk");
    const commit = join(bundle, "SDK_COMMIT");
    if (isSdkFolder(bundle) && existsSync(commit)) {
      const sha = readFileSync(commit, "utf8").trim();
      log(`SDK source: bundled Conclave-SDK@${sha.slice(0, 7)}`);
      return { ok: true, folder: bundle, sha, label: `bundled Conclave-SDK@${sha.slice(0, 7)}` };
    }
    const checkout = join(this.options.extensionPath, "..", "..");
    if (this.options.development && isSdkFolder(checkout)) {
      log(`SDK source: local Conclave-SDK (development) ${checkout}`);
      return { ok: true, folder: checkout, sha: "local", label: "local Conclave-SDK (development)" };
    }
    const message = "This build of the extension has no bundled SDK; set conclave.sdkPath or conclave.sdkRef.";
    log(`SDK source refused: ${message}`);
    return { state: "sdk-bundle-missing", message };
  }

  private async github(repository: string, ref: string, folder?: vscode.Uri): Promise<SdkSource | SdkRefusal> {
    const python = await this.python.python(folder);
    if (!python.ok || !canExtract(python.version)) {
      const message = python.ok
        ? `Python ${python.version} cannot extract a GitHub source safely; it needs 3.11.4 or later (tarfile's data filter).`
        : `No usable Python to extract a GitHub source: ${python.message}`;
      log(`SDK source refused: ${message}`);
      return { state: "sdk-python-too-old", message };
    }
    const session = await (this.options.getSession ?? vscodeSession)();
    if (!session) {
      log("SDK source refused: GitHub sign-in was cancelled.");
      return { state: "github-signin", message: "GitHub sign-in was cancelled, so the GitHub source cannot be read." };
    }
    const base = this.options.apiBase ?? "https://api.github.com";
    const headers = { Authorization: `Bearer ${session.accessToken}`, "User-Agent": "conclave-vscode", "X-GitHub-Api-Version": "2022-11-28" };

    // One commit SHA first; everything after uses it.
    let answer: Response;
    try {
      answer = await fetch(`${base}/repos/${repository}/commits/${encodeURIComponent(ref)}`, {
        headers: { ...headers, Accept: "application/vnd.github.sha" },
      });
    } catch {
      return this.refuse(githubRefusal(undefined, {}, repository));
    }
    log(`SDK source: GET ${repository}/commits/${ref} -> ${answer.status}`);
    const text = answer.ok ? (await answer.text()).trim() : "";
    if (!answer.ok || !SHA.test(text)) {
      return this.refuse(answer.ok
        ? { state: "github-no-access", message: `GitHub did not answer ${ref} with a commit.` }
        : githubRefusal(answer.status, Object.fromEntries(answer.headers), repository));
    }
    const sha = text;
    const label = `${repository}@${sha.slice(0, 7)}`;
    const cache = join(this.options.storage, "sdk");
    const target = join(cache, sha);
    if (existsSync(join(target, ".complete"))) {
      writeFileSync(join(target, ".used"), String(Date.now()));
      log(`SDK source: ${label} from the cache`);
      return { ok: true, folder: target, sha, label };
    }

    mkdirSync(cache, { recursive: true });
    const archive = join(cache, `${sha}.tar.gz.partial`);
    const partial = join(cache, `${sha}.partial`);
    rmSync(archive, { force: true });
    rmSync(partial, { recursive: true, force: true });
    try {
      let tarball: Response;
      try {
        tarball = await fetch(`${base}/repos/${repository}/tarball/${sha}`, { headers: { ...headers, Accept: "application/vnd.github+json" } });
      } catch {
        return this.refuse(githubRefusal(undefined, {}, repository));
      }
      log(`SDK source: GET ${repository}/tarball/${sha.slice(0, 7)} -> ${tarball.status} (cache miss)`);
      if (!tarball.ok || !tarball.body) {
        return this.refuse(githubRefusal(tarball.status, Object.fromEntries(tarball.headers), repository));
      }
      await pipeline(Readable.fromWeb(tarball.body as import("node:stream/web").ReadableStream), createWriteStream(archive));
      const extractor = join(this.options.extensionPath, "resources", "extract_sdk.py");
      const result = await run(python.command, [...python.prefix, "-I", extractor, archive, partial], EXTRACT_TIMEOUT_MS);
      let reply: { ok?: boolean; top?: string; error?: string } = {};
      try {
        reply = JSON.parse(result.stdout);
      } catch {
        reply = { ok: false, error: result.error ?? `the extractor exited ${result.code} with no answer` };
      }
      if (result.code !== 0 || !reply.ok || !reply.top) {
        return this.refuse({ state: "sdk-archive-refused", message: `The archive for ${label} was refused: ${reply.error ?? "no reason given"}.` });
      }
      renameSync(join(partial, reply.top), target);
      writeFileSync(join(target, ".used"), String(Date.now()));
      writeFileSync(join(target, ".complete"), sha);
      this.evict(cache);
      log(`SDK source: ${label} extracted to the cache`);
      return { ok: true, folder: target, sha, label };
    } finally {
      rmSync(archive, { force: true });
      rmSync(partial, { recursive: true, force: true });
    }
  }

  // Keeps the most recently used complete SHAs and deletes the rest.
  private evict(cache: string): void {
    const used = readdirSync(cache)
      .filter((name) => SHA.test(name) && existsSync(join(cache, name, ".complete")))
      .map((sha) => {
        const marker = join(cache, sha, ".used");
        return { sha, at: existsSync(marker) ? Number(readFileSync(marker, "utf8")) || statSync(marker).mtimeMs : 0 };
      });
    for (const sha of evictions(used)) {
      rmSync(join(cache, sha), { recursive: true, force: true });
      log(`SDK source: removed ${sha.slice(0, 7)} from the cache`);
    }
  }

  private refuse(refusal: SdkRefusal): SdkRefusal {
    log(`SDK source refused: ${refusal.message}`);
    return refusal;
  }
}
