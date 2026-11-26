# Base kit

Reusable starter overlay for adding Conclave-SDK agent instructions, skills and subagent configuration to a project across Google Antigravity (`.agents/`), Claude Code (`.claude/`), and OpenAI Codex (`.codex/`). This is the generic agent layer; Laravel and WordPress stacks are sibling kits under `kits/`.

## Contents

```text
templates/
  AGENTS.md
  GEMINI.md
  CLAUDE.md
  CODEX.md
  .agents/skills/
  .claude/agents/
  .claude/skills/
  .codex/skills/
  .conclave/
    local.example.toml
    .gitignore
  docs/
  scripts/
    design-lint.py
    tests/
      test_design_lint.py
    verify-agent-tiers.mjs
```

The template uses real files, not symlinks. Antigravity, Claude, and Codex skills may start aligned, but each tool gets its own copy so wording and metadata can diverge when model or tool behavior requires it.

## Install

```powershell
python forge.py kit /path/to/new-project base
```

The installer is additive-only: it copies missing files and preserves every existing file byte-for-byte, including locally tuned `.agents`, `.claude`, and `.codex` skills, subagents and project instructions. Preview the exact additions with `--dry-run`:

```powershell
python forge.py kit /path/to/new-project base --dry-run
```

There is no force/overwrite mode on kits. Before copying any file, the installer preflights the complete destination set and refuses a symlink target or any missing destination whose parent inside the target is a symlink or non-directory.

After installing, adapt `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, and skill descriptions to the target project.

`AGENTS.md` holds, in order: Goal (one placeholder line, which `python forge.py init <project> --goal "<goal>"` replaces with the project's goal), Working rules, Operating directive (seven rules for acting without waiting to be told, the unattended case among them), Safety (the one list of what needs the operator), Git (main branch, staging, cleanup), Skills and Subagents. Each agent's rule file under `.agents/rules/`, `.claude/rules/` and `.codex/rules/` points at the Operating directive.

## Local settings

No kit file names a machine's folder, an owner's address or a vault item. Those live in `.conclave/local.toml`, which `.conclave/.gitignore` keeps out of git: copy `.conclave/local.example.toml` to it and fill it in. Every key is optional and keeps the default the example shows.

Local ops and deploy secrets (the optional local fallback when 1Password is unavailable or rate-limited) live in `.conclave/.env.local`, which `.conclave/.gitignore` keeps out of git, with a committed `.conclave/.env.example` template whenever a project needs local secret fallback. Keeping ops secrets under `.conclave/` prevents collisions with an app's or live site's root `.env`. Precedence is always process environment (CI) -> `.conclave/.env.local` -> 1Password `Conclave` vault.

| Key | Read by | Default |
| --- | ------- | ------- |
| `paths.scratch` | The agent rules (temporary files and full logs) | The system temporary folder |
| `vault.cli` | The WordPress and automations kits | `conclave-op` on `PATH` |
| `vault.name` | The WordPress kit | `Conclave` |
| `alert.sender`, `alert.to`, `alert.key_item` | The automations kit's failure email | None: it refuses to send |
| `wordpress.reference`, `wordpress.port_source` | The `wordpress-connect` skill | None: the skill stands alone |

The template `docs/` folder holds the skill/rule structure document. Under `scripts/`, `verify-agent-tiers.mjs` checks that every Claude agent definition in `.claude/agents/` pins an explicit model, that no agent can edit files (an explicit `tools:` list with no edit tools), that an elevated tier records why, and that a Haiku agent meets every condition of the near-mechanical allowance in `AGENTS.md` (reading frontmatter as a closed subset of YAML: flat `key: value` pairs plus one skipped `hooks:` block, refusing everything else), and `design-lint.py` (tested by `scripts/tests/test_design_lint.py`) enforces the two-tier static design token and theme check (`strict` zero-raw-literal mode on custom token-system repositories, `theme-only` raw-color mode on accepted-look native repositories, `off` when no design contract exists) backed by a shrink-only `.conclave/design-lint-baseline.json`.

## Subagents across the three writers

Claude Code receives five read-only subagent definitions under `.claude/agents/` (`code-explorer`, `debug-evidence`, `git-runner`, `mutation-tester`, `test-runner`). Codex has no project subagent definitions (the base kit ships no `.codex/agents/` folder) and runs mechanical subtasks in the main session.

Google Antigravity (`agy`) runs Gemini 4 Neon (`gemini-4-neon-medium`) at an explicit `--effort` instead of custom `.agents/agents/*.md` files or wrapper scripts:

- **Single-session workflow:** `gemini-4-neon-medium` plans and builds each TODO section in one session without mode handoffs, checking the section's `stamp` and `ci_status.py` before taking the next ready row.
- **Built-in subagents (`<subagents>`):** Every session natively includes built-in `self`, `research`, and `image-generator` subagents invoked via `invoke_subagent`. Shipping custom `.agents/agents/*.md` wrappers is redundant and can override native model routing, so fresh `--agent agy` installs ship zero `.agents/agents/` files and no `scripts/agy-subagent.py`.
- **Effort and model selection:** Start interactive or campaign sessions with `agy --model gemini-4-neon-medium --effort=medium` (passing `--effort` explicitly). Compatibility: projects that still name `gemini-pro-orchestrator` or `gemini-pro-orchestrator-*` continue to work by omitting `--effort`.

### Moving Antigravity to Gemini 4 Neon

Projects moving from Orchestrator (`gemini-pro-orchestrator`) to Gemini 4 Neon (`gemini-4-neon-medium`) switch their Antigravity launch command to `agy --model gemini-4-neon-medium --effort=medium`. If the project also installs `kits/unattended`, update `"model": "gemini-4-neon-medium"` and `"effort": "medium"` together in `.conclave/unattended.json` (Orchestrator profiles reject a non-null effort, so never change `effort` while leaving `gemini-pro-orchestrator` as `model`). Only edit `.conclave/reviewers.toml` (using TOML syntax such as `model = "gemini-4-neon-medium"` and `effort = "medium"`) if the project also intends to change its Antigravity reviewer pin. Projects that still pin `gemini-pro-orchestrator` remain supported without `--effort`.

Because `forge.py update <project> base` is additive-only and preserves deleted kit files as `project-only` (so local edits are never lost), existing projects updated from older `base` kit releases retain the retired Antigravity wrappers and remain discoverable by `agy` until cleaned up:

- `.agents/agents/code-explorer.md`
- `.agents/agents/debug-evidence.md`
- `.agents/agents/git-runner.md`
- `.agents/agents/mutation-tester.md`
- `.agents/agents/test-runner.md`
- `scripts/agy-subagent.py`

Follow this reversible cleanup after `python forge.py update <project> base`:

1. Inspect retired files with `python forge.py diff <project> base` (each retired file reports `project-only`). Compare against `.conclave/kits.json` or `git diff`: copy any local customizations you still need from a retired file into a retained project-custom file (for example `.agents/agents/preserved-code-explorer.md`), and leave existing project-custom `.agents/agents/<custom>.md` files untouched.
2. Commit your pre-cleanup repository state, anchor a durable recovery ref (`git branch pre-orchestrator-migration`, or record `git rev-parse HEAD`), and save a raw byte-preserving archive of only the seven paths cleanup touches before deleting anything (works from any subdirectory and in linked worktrees; refuses symlinks or Windows junctions on any parent or target component; cleans up its unique temporary file in `finally`; if `pre-orchestrator-migration.zip` already exists on a retry, reuse it instead of overwriting it):

```python
import os, pathlib, subprocess, tempfile, zipfile

top = pathlib.Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
dst = pathlib.Path(subprocess.check_output(["git", "rev-parse", "--git-path", "pre-orchestrator-migration.zip"], text=True).strip())
if dst.exists():
    raise FileExistsError(dst)
allow = (
    ".agents/agents/code-explorer.md",
    ".agents/agents/debug-evidence.md",
    ".agents/agents/git-runner.md",
    ".agents/agents/mutation-tester.md",
    ".agents/agents/test-runner.md",
    "scripts/agy-subagent.py",
    ".conclave/kits.json",
)
def check_no_links(rel: str) -> None:
    cur = top
    for part in pathlib.Path(rel).parts:
        cur = cur / part
        if cur.is_symlink() or (hasattr(cur, "is_junction") and cur.is_junction()) or (hasattr(os.path, "isjunction") and os.path.isjunction(cur)):
            raise ValueError(f"link not allowed: {cur}")
for r in allow:
    check_no_links(r)
found = [r for r in allow if (top / r).is_file()]
if not found:
    raise RuntimeError("no retired paths found")
fd, tmp_s = tempfile.mkstemp(dir=dst.parent, prefix=".pre-orchestrator-migration.", suffix=".tmp")
os.close(fd)
tmp = pathlib.Path(tmp_s)
try:
    with zipfile.ZipFile(tmp, "w") as z:
        for r in found:
            z.write(top / r, arcname=r)
    with zipfile.ZipFile(tmp) as z:
        bad = z.testzip()
        if bad is not None:
            raise zipfile.BadZipFile(bad)
    os.link(tmp, dst)
finally:
    tmp.unlink(missing_ok=True)
```

Because a committed deletion removes those paths from later `HEAD` commits and Windows Git `core.autocrlf=true` alters LF or CRLF bytes during `git add` and `git checkout`, rollback after committed cleanup sets `RECOVERY_REF` (`pre-orchestrator-migration` or the recorded `git rev-parse HEAD` SHA) and restores only the allowlisted paths present in that recovery ref from the repository root (works from any subdirectory, preserves retained custom agents, and refuses symlinks or Windows junctions on any parent or target component):

```python
import os, pathlib, subprocess, zipfile

ref = os.environ.get("RECOVERY_REF", "pre-orchestrator-migration")
top = pathlib.Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
src = pathlib.Path(subprocess.check_output(["git", "rev-parse", "--git-path", "pre-orchestrator-migration.zip"], text=True).strip())
allow = (
    ".agents/agents/code-explorer.md",
    ".agents/agents/debug-evidence.md",
    ".agents/agents/git-runner.md",
    ".agents/agents/mutation-tester.md",
    ".agents/agents/test-runner.md",
    "scripts/agy-subagent.py",
    ".conclave/kits.json",
)
def check_no_links(rel: str) -> None:
    cur = top
    for part in pathlib.Path(rel).parts:
        cur = cur / part
        if cur.is_symlink() or (hasattr(cur, "is_junction") and cur.is_junction()) or (hasattr(os.path, "isjunction") and os.path.isjunction(cur)):
            raise ValueError(f"link not allowed: {cur}")
for r in allow:
    check_no_links(r)
present = subprocess.check_output(["git", "-C", str(top), "ls-tree", "-r", "--name-only", ref, "--", *allow], text=True).splitlines()
if present:
    subprocess.run(["git", "-C", str(top), "-c", "core.autocrlf=false", "checkout", ref, "--", *present], check=True)
with zipfile.ZipFile(src) as z:
    for m in z.namelist():
        if m in allow:
            check_no_links(m)
            target = top / m
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(m))
```
3. Remove only the six retired SDK paths (and `.agents/agents` only if it is now empty; keep migrated `.agents/agents/preserved-*.md` and custom `.agents/agents/<custom>.md` files), remove their retired entries from `.conclave/kits.json` if desired, and commit the cleanup.
4. Switch interactive and CLI Antigravity launches to `agy --model gemini-4-neon-medium --effort=medium` (or keep `--model gemini-pro-orchestrator` without `--effort` if staying on Orchestrator compatibility).
5. Verify native operation: confirm none of the five SDK wrappers remain in `.agents/agents/`, confirm `agy --model gemini-4-neon-medium --effort=medium` lists built-in `self`, `research`, and `image-generator` in `<subagents>`, and confirm a single-session edit and test run finishes cleanly.

### Historical live verification (Orchestrator, `agy` 1.5.8, 2026-11-14)

Historical evidence from 2026-11-14 verifying built-in subagents and Orchestrator compatibility against installed `agy` `1.5.8` with `CONCLAVE_LIVE_AGY=1 python -m unittest -v tests.test_agy_agents` (`Ran 14 tests in 381.924s OK`):

- **Built-in `<subagents>` listing (Orchestrator evidence):** Initiated `gemini-pro-orchestrator` in a fresh `--kit base --agent agy` workspace with zero `.agents/agents` directory and confirmed native `self`, `research`, and `image-generator` subagents are available.
- **Real `invoke_subagent` delegation (Orchestrator evidence):** Delegated a known-answer lookup (`def halve` in `calc.py`) to `TypeName='research'` with parent direct-inspection tools forbidden, observed `step_type: "subagent"` (`invoke_subagent`) launch plus post-launch `system_message` wakeup in `stream-json`, matched subagent `send_message` and parent `SYSTEM_MESSAGE` (`sender=<subagent_conversation_id>`) transcript attribution, and independently confirmed the reported answer (line `5`, returning `n / 2`) in both `delegated_replies` and `assistant_text`.
- **Two-phase `exit_plan_mode` execution (Orchestrator compatibility evidence):** Invoked `gemini-pro-orchestrator` to fix buggy `add(a, b)` in `calc.py`, observed planning, `exit_plan_mode` (`Plan mode is off.`), `edit_file`, and `python -m unittest tests.test_calc` (`Ran 2 tests ... OK`) exit `0`.

## Maintenance

This kit is the only source of these files. When improving shared operating behavior:

1. Change the file in this kit's `templates/` for each agent it applies to (`.agents/`, `.claude/`, `.codex/`).
2. Run `python forge.py self-sync` to refresh the SDK's own `.agents/`, `.claude/`, `.codex/` and `scripts/`; `tests/test_forge.py` fails until they match.
3. Projects are not updated: each owns the copy it took. Port the change into a project by hand only when that project wants it.

Do not use symlinks between `.agents`, `.claude`, and `.codex`.
