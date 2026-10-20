// Which Conclave-SDK the extension runs forge.py from (plan R24, corrected 2026-10-20): the SDK bundled in the
// extension, or a local checkout in conclave.sdkPath, a developer override for working on the SDK itself. There is no
// other source (design/decisions.md, read-only kit view: no kit source is configured). The pure parts live here:
// precedence and the bundle's checks. Nothing here runs SDK code.

export interface SdkSettings {
  sdkPath: string;
}

export type SourceChoice = { kind: "path"; path: string } | { kind: "bundled" };

export type SdkRefusal =
  | { state: "sdk-path-invalid"; message: string }
  | { state: "sdk-bundle-missing"; message: string };

export interface SdkSource {
  ok: true;
  folder: string;
  // The 40-hex build commit for the bundled source; "local" for a checkout.
  sha: string;
  // What every log line names, for example "bundled Conclave-SDK@1a2b3c4".
  label: string;
}

export const SHA = /^[0-9a-f]{40}$/;

// Precedence: a set sdkPath wins, and an unusable one is a refusal, never a fall-through; otherwise the bundle.
export function chooseSource(settings: SdkSettings, isSdkFolder: (path: string) => boolean): SourceChoice | SdkRefusal {
  const path = settings.sdkPath.trim();
  if (path) {
    return isSdkFolder(path)
      ? { kind: "path", path }
      : { state: "sdk-path-invalid", message: "conclave.sdkPath is not a Conclave-SDK checkout." };
  }
  return { kind: "bundled" };
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
  return { state: "sdk-bundle-missing", message: "This build of the extension has no bundled SDK; reinstall it, or set conclave.sdkPath to a Conclave-SDK checkout." };
}
