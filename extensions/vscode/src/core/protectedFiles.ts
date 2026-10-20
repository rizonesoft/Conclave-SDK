// Project files a kit operation must never change (plan R32): every install, update and init proves by hash that they
// are byte-identical before and after, unless forge reported writing them. Paths are relative, with "/" separators.
export const PROTECTED_FILES = [
  "AGENTS.md", "GEMINI.md", "CLAUDE.md", "CODEX.md", ".conclave/reviewers.toml", ".conclave/automations/tasks.json",
  ".conclave/automations/README.md", ".claude/settings.json",
] as const;
// Every file under these folders is protected.
export const PROTECTED_FOLDERS = ["todo", "docs"] as const;

// The protected files that existed before and changed or disappeared, which forge did not report writing.
export function protectedChanges(before: Map<string, string>, after: Map<string, string>, written: string[]): string[] {
  const reported = new Set(written.map((w) => w.replace(/\\/g, "/")));
  return [...before].filter(([path, hash]) => !reported.has(path) && after.get(path) !== hash).map(([path]) => path).sort();
}
