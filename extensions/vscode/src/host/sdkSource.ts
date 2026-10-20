import { randomBytes } from "node:crypto";
import { createWriteStream, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import * as vscode from "vscode";
import {
  bundledSource,
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
import { removeTree } from "./removeTree";
import { run } from "./run";

const EXTRACT_TIMEOUT_MS = 120_000;
const MAX_DOWNLOAD = 100 * 1024 * 1024;

export interface SdkSourceOptions {
  extensionPath: string;
  storage: string;
  // True in the Extension Development Host and tests, where the SDK checkout the extension runs from is the fallback.
  development: boolean;
  // The GitHub REST API's base; a local stand-in in tests.
  apiBase?: string;
  // The GitHub session; VS Code's sign-in by default, asked for only when the GitHub source is needed.
  getSession?: () => Promise<{ accessToken: string } | undefined>;
  // The largest tarball accepted, counted while it streams.
  maxDownload?: number;
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

// A cached SHA counts only when it is an SDK folder whose marker names that SHA.
function isComplete(folder: string, sha: string): boolean {
  return isSdkFolder(folder) && readCommit(join(folder, ".complete")) === sha;
}

async function vscodeSession(): Promise<{ accessToken: string } | undefined> {
  try {
    return await vscode.authentication.getSession("github", ["repo"], { createIfNone: true });
  } catch {
    return undefined;
  }
}

class TooLarge extends Error {}

// Resolves the SDK forge.py runs from: a local checkout, a GitHub commit cached per SHA, or the bundle. It runs no SDK
// code; it returns the folder, the SHA (or "local") and the label confirmations show.
//
// A cache entry is published in one rename of a folder that is already complete (its .complete marker is written
// before the rename), so a crash never leaves a half-published entry, and each download uses its own temporary names,
// so two windows, or two refs naming one commit, never touch each other's files. One download per SHA is in flight per
// window; another window losing the race uses the winner's entry.
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
      return this.refuse(choice);
    }
    if (choice.kind === "path") {
      log(`SDK source: local checkout ${choice.path}`);
      return { ok: true, folder: choice.path, sha: "local", label: choice.path };
    }
    if (choice.kind === "bundled") {
      const result = bundledSource(this.options.extensionPath, this.options.development, { isSdkFolder, readCommit, join });
      return "ok" in result ? (log(`SDK source: ${result.label} ${result.folder}`), result) : this.refuse(result);
    }
    return this.github(choice.repository, choice.ref, folder);
  }

  private async github(repository: string, ref: string, folder?: vscode.Uri): Promise<SdkSource | SdkRefusal> {
    const python = await this.python.python(folder);
    if (!python.ok || !canExtract(python.version)) {
      return this.refuse({
        state: "sdk-python-too-old",
        message: python.ok
          ? `Python ${python.version} cannot extract a GitHub source safely; it needs 3.11.4 or later (tarfile's data filter).`
          : `No usable Python to extract a GitHub source: ${python.message}`,
      });
    }
    const session = await (this.options.getSession ?? vscodeSession)();
    if (!session) {
      return this.refuse({ state: "github-signin", message: "GitHub sign-in was cancelled, so the GitHub source cannot be read." });
    }
    const base = this.options.apiBase ?? "https://api.github.com";
    const headers = { Authorization: `Bearer ${session.accessToken}`, "User-Agent": "conclave-vscode", "X-GitHub-Api-Version": "2022-11-28" };

    // One commit SHA first; everything after uses it. A connection that fails after the headers is offline too.
    let sha: string;
    try {
      const answer = await fetch(`${base}/repos/${repository}/commits/${encodeURIComponent(ref)}`, {
        headers: { ...headers, Accept: "application/vnd.github.sha" },
      });
      log(`SDK source: GET ${repository}/commits/${ref} -> ${answer.status}`);
      if (!answer.ok) {
        return this.refuse(githubRefusal(answer.status, Object.fromEntries(answer.headers), repository));
      }
      sha = (await answer.text()).trim();
    } catch {
      return this.refuse(githubRefusal(undefined, {}, repository));
    }
    if (!SHA.test(sha)) {
      return this.refuse({ state: "github-no-access", message: `GitHub did not answer ${ref} with a commit.` });
    }
    let call = this.inFlight.get(sha);
    if (!call) {
      call = this.fetchCommit(repository, sha, headers, python.command, python.prefix).finally(() => this.inFlight.delete(sha));
      this.inFlight.set(sha, call);
    }
    return call;
  }

  private async fetchCommit(repository: string, sha: string, headers: Record<string, string>, command: string,
    prefix: string[]): Promise<SdkSource | SdkRefusal> {
    const label = `${repository}@${sha.slice(0, 7)}`;
    const cache = join(this.options.storage, "sdk");
    const target = join(cache, sha);
    if (isComplete(target, sha)) {
      writeFileSync(join(target, ".used"), String(Date.now()));
      log(`SDK source: ${label} from the cache`);
      return { ok: true, folder: target, sha, label };
    }
    mkdirSync(cache, { recursive: true });
    // An entry that is not complete (left by an older build, or tampered with) is rebuilt, never trusted.
    if (existsSync(target) && !isComplete(target, sha)) {
      removeTree(target);
    }
    const unique = `${sha}.${process.pid}-${randomBytes(4).toString("hex")}`;
    const archive = join(cache, `${unique}.tar.gz.partial`);
    const partial = join(cache, `${unique}.partial`);
    try {
      try {
        const tarball = await fetch(`${base(this.options)}/repos/${repository}/tarball/${sha}`, { headers: { ...headers, Accept: "application/vnd.github+json" } });
        log(`SDK source: GET ${repository}/tarball/${sha.slice(0, 7)} -> ${tarball.status} (cache miss)`);
        if (!tarball.ok || !tarball.body) {
          return this.refuse(githubRefusal(tarball.status, Object.fromEntries(tarball.headers), repository));
        }
        const limit = this.options.maxDownload ?? MAX_DOWNLOAD;
        let received = 0;
        const counter = new Transform({
          transform(chunk: Buffer, _encoding, done) {
            received += chunk.length;
            done(received > limit ? new TooLarge() : null, chunk);
          },
        });
        await pipeline(Readable.fromWeb(tarball.body as import("node:stream/web").ReadableStream), counter, createWriteStream(archive));
      } catch (error) {
        return this.refuse(error instanceof TooLarge
          ? { state: "sdk-archive-refused", message: `The archive for ${label} is larger than ${(this.options.maxDownload ?? MAX_DOWNLOAD) / (1024 * 1024)} MB.` }
          : githubRefusal(undefined, {}, repository));
      }
      const extractor = join(this.options.extensionPath, "resources", "extract_sdk.py");
      const result = await run(command, [...prefix, "-I", extractor, archive, partial], EXTRACT_TIMEOUT_MS);
      let reply: { ok?: boolean; top?: string; error?: string } = {};
      try {
        reply = JSON.parse(result.stdout);
      } catch {
        reply = { ok: false, error: result.error ?? `the extractor exited ${result.code} with no answer` };
      }
      if (result.code !== 0 || !reply.ok || !reply.top) {
        return this.refuse({ state: "sdk-archive-refused", message: `The archive for ${label} was refused: ${reply.error ?? "no reason given"}.` });
      }
      const extracted = join(partial, reply.top);
      if (!isSdkFolder(extracted)) {
        return this.refuse({ state: "sdk-archive-refused", message: `The archive for ${label} holds no forge.py and kits/, so it is not a Conclave-SDK.` });
      }
      // .complete and .used are the cache's own markers: an archive that carries either name could pass for complete.
      if (existsSync(join(extracted, ".complete")) || existsSync(join(extracted, ".used"))) {
        return this.refuse({ state: "sdk-archive-refused", message: `The archive for ${label} holds .complete or .used, names the cache reserves.` });
      }
      try {
        writeFileSync(join(extracted, ".used"), String(Date.now()));
        writeFileSync(join(extracted, ".complete"), sha);
      } catch (error) {
        return this.refuse({ state: "sdk-archive-refused", message: `${label} could not be marked complete: ${String(error)}.` });
      }
      try {
        renameSync(extracted, target);
      } catch (error) {
        // Another window published the same commit first: its complete entry is as good as ours.
        if (!isComplete(target, sha)) {
          return this.refuse({ state: "sdk-archive-refused", message: `${label} could not be stored in the cache: ${String(error)}.` });
        }
      }
      this.evict(cache);
      log(`SDK source: ${label} extracted to the cache`);
      return { ok: true, folder: target, sha, label };
    } finally {
      rmSync(archive, { force: true });
      removeTree(partial);
    }
  }

  // Keeps the most recently used complete SHAs and deletes the rest.
  private evict(cache: string): void {
    const used = readdirSync(cache)
      .filter((name) => SHA.test(name) && isComplete(join(cache, name), name))
      .map((sha) => ({ sha, at: Number(readCommit(join(cache, sha, ".used"))) || 0 }));
    for (const sha of evictions(used)) {
      removeTree(join(cache, sha));
      log(`SDK source: removed ${sha.slice(0, 7)} from the cache`);
    }
  }

  private refuse(refusal: SdkRefusal): SdkRefusal {
    log(`SDK source refused: ${refusal.message}`);
    return refusal;
  }
}

function base(options: SdkSourceOptions): string {
  return options.apiBase ?? "https://api.github.com";
}
