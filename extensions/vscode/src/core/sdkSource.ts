// Which Conclave-SDK the extension runs forge.py from (plan R24, design spec section 8): a local checkout in
// conclave.sdkPath, a GitHub commit through conclave.sdkRef, or the SDK bundled in the extension. The pure parts live
// here: precedence, validation, mapping GitHub's answers to states, and the cache's eviction. Nothing here touches the
// network or runs SDK code.

export const DEFAULT_REPOSITORY = "rizonetech/Conclave-SDK";
export const CACHE_KEEP = 3;

export interface SdkSettings {
  sdkPath: string;
  sdkRepository: string;
  sdkRef: string;
}

export type SourceChoice =
  | { kind: "path"; path: string }
  | { kind: "github"; repository: string; ref: string }
  | { kind: "bundled" };

export type SdkRefusal =
  | { state: "sdk-path-invalid"; message: string }
  | { state: "sdk-bundle-missing"; message: string }
  | { state: "sdk-settings-invalid"; message: string }
  | { state: "github-signin"; message: string }
  | { state: "github-no-access"; message: string }
  | { state: "github-rate-limited"; message: string; reset?: string }
  | { state: "github-offline"; message: string }
  | { state: "sdk-python-too-old"; message: string }
  | { state: "sdk-archive-refused"; message: string };

export interface SdkSource {
  ok: true;
  folder: string;
  // A 40-hex commit for a bundled or GitHub source; "local" for a checkout.
  sha: string;
  // What every confirmation names, for example "bundled Conclave-SDK@1a2b3c4".
  label: string;
}

const REPOSITORY = /^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/;
export const SHA = /^[0-9a-f]{40}$/;

export function validRepository(repository: string): boolean {
  return REPOSITORY.test(repository) && !repository.split("/")[1].startsWith(".") && !repository.includes("..");
}

// A ref git would accept and a URL path segment cannot be bent by: no "..", no leading "-" or "/", no whitespace,
// control characters or the characters git forbids (~ ^ : ? * [ \), and not ending in "/", "." or ".lock".
export function validRef(ref: string): boolean {
  const control = [...ref].some((c) => c.charCodeAt(0) < 0x20 || c.charCodeAt(0) === 0x7f);
  return ref.length > 0 && ref.length <= 255 && !control && !/[\s~^:?*[\\]/.test(ref) && !ref.includes("..")
    && !ref.includes("@{") && !ref.includes("//") && !/^[-/.]/.test(ref) && !/(\/|\.|\.lock)$/.test(ref)
    && !/\/\./.test(ref);
}

// Precedence: a set sdkPath wins (and an unusable one is a refusal, never a fall-through); then a set sdkRef selects
// GitHub; otherwise the bundle.
export function chooseSource(settings: SdkSettings, isSdkFolder: (path: string) => boolean): SourceChoice | SdkRefusal {
  const path = settings.sdkPath.trim();
  if (path) {
    return isSdkFolder(path)
      ? { kind: "path", path }
      : { state: "sdk-path-invalid", message: "conclave.sdkPath is not a Conclave-SDK checkout." };
  }
  const ref = settings.sdkRef.trim();
  if (ref) {
    const repository = settings.sdkRepository.trim() || DEFAULT_REPOSITORY;
    if (!validRepository(repository)) {
      return { state: "sdk-settings-invalid", message: `conclave.sdkRepository ${JSON.stringify(repository)} is not owner/name.` };
    }
    if (!validRef(ref)) {
      return { state: "sdk-settings-invalid", message: `conclave.sdkRef ${JSON.stringify(ref)} is not a git ref name.` };
    }
    return { kind: "github", repository, ref };
  }
  return { kind: "bundled" };
}

// A GitHub answer that is not a success, as a refusal state. An internal repository answers 404 to a non-member.
export function githubRefusal(status: number | undefined, headers: Record<string, string | undefined>, repository: string): SdkRefusal {
  if (status === undefined) {
    return { state: "github-offline", message: "GitHub could not be reached." };
  }
  if (status === 401 || status === 404) {
    return { state: "github-no-access", message: `This GitHub account has no access to ${repository}, or the ref does not exist there.` };
  }
  if ((status === 403 || status === 429) && headers["x-ratelimit-remaining"] === "0") {
    const reset = headers["x-ratelimit-reset"];
    const at = reset && /^\d+$/.test(reset) ? new Date(Number(reset) * 1000).toISOString() : undefined;
    return { state: "github-rate-limited", message: `GitHub's rate limit is used up${at ? ` until ${at}` : ""}.`, reset: at };
  }
  return { state: "github-no-access", message: `GitHub answered ${status} for ${repository}.` };
}

// The cached SHAs to delete after a new one is complete: all but the CACHE_KEEP most recently used.
export function evictions(used: { sha: string; at: number }[]): string[] {
  return [...used].sort((a, b) => b.at - a.at).slice(CACHE_KEEP).map((entry) => entry.sha);
}

export interface FolderProbe {
  // True for a folder holding a forge.py file and a kits/ folder (types checked, not just names).
  isSdkFolder: (path: string) => boolean;
  // The bundle's SDK_COMMIT, or undefined when there is none.
  readCommit: (path: string) => string | undefined;
  join: (...parts: string[]) => string;
}

// The bundled source: <extensionPath>/sdk with forge.py, kits/ and SDK_COMMIT; in the Extension Development Host or a
// test, with no bundle, the SDK checkout the extension runs from (two folders up); a packaged build without its
// bundle is the refusal sdk-bundle-missing.
export function bundledSource(extensionPath: string, development: boolean, probe: FolderProbe): SdkSource | SdkRefusal {
  const bundle = probe.join(extensionPath, "sdk");
  const commit = probe.readCommit(probe.join(bundle, "SDK_COMMIT"));
  if (probe.isSdkFolder(bundle) && commit && SHA.test(commit)) {
    return { ok: true, folder: bundle, sha: commit, label: `bundled Conclave-SDK@${commit.slice(0, 7)}` };
  }
  const checkout = probe.join(extensionPath, "..", "..");
  if (development && probe.isSdkFolder(checkout)) {
    return { ok: true, folder: checkout, sha: "local", label: "local Conclave-SDK (development)" };
  }
  return { state: "sdk-bundle-missing", message: "This build of the extension has no bundled SDK; set conclave.sdkPath or conclave.sdkRef." };
}

// Python 3.11.4 added tarfile's data filter, the extraction's second layer.
export function canExtract(version: string): boolean {
  const [major, minor, patch] = version.split(".").map(Number);
  return major > 3 || (major === 3 && (minor > 11 || (minor === 11 && patch >= 4)));
}
