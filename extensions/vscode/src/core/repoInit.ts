// Setting up a new repository through `forge.py init` (plan R31). Pure: the argv and the target checks.

export const AGENTS = ["all", "agy", "gemini", "claude", "codex"] as const;
export const MODES = ["isolated", "copy", "hybrid", "inherit"] as const;
export const WORDPRESS_HOSTS = ["pressable", "wpcom"] as const;
// The entry docs init writes into an empty folder and skips in one that has them (it is never run with --force).
export const ENTRY_DOCS = ["AGENTS.md", "GEMINI.md", "CLAUDE.md", "CODEX.md"] as const;

export interface InitChoice {
  folder: string;
  agent: (typeof AGENTS)[number];
  mode: (typeof MODES)[number];
  // Kits beyond base, which init always installs.
  kits: string[];
  // The WordPress kit's host; only passed when the WordPress kit is chosen.
  wordpressHost?: (typeof WORDPRESS_HOSTS)[number];
}

// The argv after forge.py: `init <folder> --agent <agent> --mode <mode>`, one `--kit` per kit, and `--wp-host` with the
// WordPress kit. It is built from the choice's own fields only, so no input can add an option, and never --force: an
// existing AGENTS.md, GEMINI.md, CLAUDE.md or CODEX.md is never overwritten.
export function initArgs(choice: InitChoice): string[] {
  // forge's argument parser reads anything starting with "-" as an option, so a folder named "--force" would be one.
  if (choice.folder === "" || choice.folder.startsWith("-")) {
    throw new Error(`the folder must be a path, not ${JSON.stringify(choice.folder)}`);
  }
  if (!(AGENTS as readonly string[]).includes(choice.agent)) {
    throw new Error(`unknown agent ${JSON.stringify(choice.agent)}`);
  }
  if (!(MODES as readonly string[]).includes(choice.mode)) {
    throw new Error(`unknown mode ${JSON.stringify(choice.mode)}`);
  }
  const kits = [...new Set(choice.kits.filter((k) => k !== "base"))];
  for (const kit of kits) {
    if (!/^[a-z][a-z0-9-]*$/.test(kit)) {
      throw new Error(`a kit name must be lowercase letters, digits and dashes: ${JSON.stringify(kit)}`);
    }
  }
  const args = ["init", choice.folder, "--agent", choice.agent, "--mode", choice.mode, ...kits.flatMap((k) => ["--kit", k])];
  if (kits.includes("wordpress") && choice.wordpressHost) {
    if (!(WORDPRESS_HOSTS as readonly string[]).includes(choice.wordpressHost)) {
      throw new Error(`unknown WordPress host ${JSON.stringify(choice.wordpressHost)}`);
    }
    args.push("--wp-host", choice.wordpressHost);
  }
  return args;
}

export interface TargetDeps {
  // Absolute and normalised, the platform's way (path.resolve).
  resolve: (path: string) => string;
  sep: string;
  // Whether paths differ only in case on this platform (Windows).
  caseInsensitive: boolean;
}

// Why a folder cannot be set up, or undefined: one inside a repository's .git folder (set up there, the files would
// land in git's own data), or the SDK source folder itself (init would write the kits' copies over their source).
export function refuseTarget(target: string, sdkFolder: string, deps: TargetDeps): string | undefined {
  const fold = (p: string) => (deps.caseInsensitive ? p.toLowerCase() : p);
  const resolved = deps.resolve(target);
  const parts = resolved.split(/[\\/]/);
  if (parts.some((p) => fold(p) === ".git")) {
    return `${resolved} is inside a .git folder`;
  }
  if (fold(resolved) === fold(deps.resolve(sdkFolder))) {
    return `${resolved} is the Conclave-SDK source folder itself`;
  }
  return undefined;
}
