# PHP and Node toolchain kit

Additive overlay for a PHP or Node project, the Laravel and WordPress kits' projects among them: it pins the runtimes, the package managers and the static tools the project wants, tells the operator which are missing or too old, and never installs a tool.

| File | What it is |
| --- | --- |
| `.conclave/toolchain-web.json` | The pin file: each tool, the commands that satisfy it, the least version |
| `scripts/toolchain-check.py` | Reads the pin file and reports each tool; installs and writes nothing |
| `scripts/tests/test_toolchain_check.py` | The check's own tests, with stub tools |
| `docs/toolchain-web.md` | The project's document: every command, and what is left to the project |
| `.claude/skills/web-toolchain/SKILL.md` | The `web-toolchain` skill, for Claude Code |
| `.agents/skills/web-toolchain/SKILL.md` | The same skill, for Antigravity |
| `.codex/skills/web-toolchain/SKILL.md` | The same skill, for Codex |
| `.codex/skills/web-toolchain/agents/openai.yaml` | Codex's interface file for the skill |

The skill tells an agent to check before an install or a build fails mysteriously, never to install or upgrade a runtime or a package manager or change a pin to fit the machine, never to loosen `require.php` or `engines.node`, and to run the project's own tools from `vendor/bin` and `node_modules/.bin`. Its three copies say the same; an install for one agent gets that agent's copy only.

The check script and its tests are the same files the C and C++ kit ships, byte for byte; a project with both kits has them once. The pin file is the project's own from the first install: `forge.py` never changes one the project has changed. There is one exception, for a file that is not yet the project's: a pin file that is still the kit's seed byte for byte, in a project whose app is not at the root, is given its `root` (see Install).

## Install

```powershell
python forge.py kit /path/to/project toolchain-web [--dry-run]
python forge.py doctor /path/to/project toolchain-web [--strict]
```

`python forge.py init /path/to/project --kit toolchain-web` installs it with the base kit. The SDK does not install this kit in itself.

The install looks for the app: the folder holding `composer.json` or `package.json` is the project root, else `platform/`, else the first other first-level folder in name order. The result's `app_root` names it. When the app is not at the root and the project has no pin file yet, the install writes the pin file once, with that folder as its `root`: there is never a moment when the file exists without it, and if that write fails the command exits 1 with the reason and the next install completes. It is recorded like every installed file, with the digest of the bytes written, and `forge.py diff` and `forge.py update` compare it with the same thing: the seed carrying this project's `root`. A pin file the project has changed in any way is never touched: to move its app's folder, edit its `root`. The exception is a pin file that is still exactly the kit's seed while the app is not at the root, which is what an install stopped part way left behind before the single write existed: the next install gives it its `root` and lists it under `repaired`, never under `preserved` or `installed`.

## The pins

| Tool | Commands, in order of preference | Least version | Optional |
| --- | --- | --- | --- |
| `php` | `php` | 8.2 | no |
| `composer` | `composer` | 2.5 | no |
| `node` | `node` | 20 | no |
| `package-manager` | `pnpm`, then `npm` | 9, 9 | no |
| `phpstan` | `phpstan` | 1.10 | yes |
| `pint` | `pint` | 1.0 | yes |
| `phpcs` | `phpcs` | 3.7 | yes |

Two keys at the top of the pin file say where the project keeps tools of its own, which no `PATH` reaches:

```json
{
  "schema_version": 1,
  "root": "platform",
  "search": ["vendor/bin", "node_modules/.bin"],
  "tools": []
}
```

`root` is the app's folder inside the project (`.` when left out). `search` lists folders inside it: a command is looked for in `vendor/bin` and `node_modules/.bin` of the app first, then on `PATH`, and never in the working directory. That is how `phpstan`, `pint`, `phpcs` and a project's own `pnpm` are found, as the `.bat` or `.cmd` launcher on Windows.

To change a pin, edit `.conclave/toolchain-web.json`: raise a `min_version`, set `optional` to `false` for a tool the project cannot do without, or add a tool. The format and its rules are those of the C and C++ kit (`kits/toolchain-cpp/README.md`): each command has its own version arguments, pattern and minimum. The loader is the same file in both kits, so it also accepts the C and C++ kit's optional `compdb` key (where a compile database is); this kit has no check that reads it.

Intelephense is not pinned here. It is a language server with no version command; the LSP kit's doctor reports it as `server:intelephense`.

```powershell
python scripts/toolchain-check.py --pins .conclave/toolchain-web.json [--json] [--root <project>]
```

## Doctor

`python forge.py doctor <project> toolchain-web` reports:

- each file the kit installs, `ok` or `missing`;
- `tool-pins`: `ok` with the tools the project's pin file names, `missing` with the refusal when it does not load;
- `tool:<name>` for each pinned tool: `ok` with the path found and its version, `setup_required` for a required tool that is not ok, `optional` (shown, never counted) for an optional one;
- `constraint:php` and `constraint:node`, when the app's `composer.json` states `require.php` or its `package.json` states `engines.node` and the pin file has a tool of that name: `ok` with the constraint and the pin's minimum, or `unexpected` when the pin accepts a version the project's own manifest refuses, naming the pin to raise.

- `constraint:package-manager`, when the app names a package manager (`packageManager` in `package.json`, or a lock file: `pnpm-lock.yaml`, `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`, `bun.lock`, `bun.lockb`) and the pin file has a `package-manager` tool: `ok` when that manager is the pin's first command; `unexpected`, naming the command to put first or to add, when it is not, because the check reports the first installed command and would name pnpm for an npm project on a machine with both; `unexpected` as well when the app names two managers.

The lowest version a constraint allows is read from `^8.3`, `~8.3.0`, `>=8.3`, `8.3.*`, `20.x`, `>=8.2 <8.5` and alternatives joined by `||` (or Composer's `|`). A constraint of another form is `ok` and said to be not compared. A manifest that cannot be used (unreadable, not JSON, not an object) is `unexpected` with the reason, and the other checks are still reported.

The doctor starts each pinned tool to ask its version, so `python forge.py doctor <project>` with no kit named does not run these checks: name the kit.

## Sources

The pin format and the check are the C and C++ kit's, which generalise RasterFold's `toolchain.json` (`b33493346141f96b6b304cd3e0c393595382f056`); see `kits/toolchain-cpp/README.md`. Nothing else here was taken from RasterFold or Impossible OS (`17a762d39ccd1958cbe711901f645fd9b042e939`), which are C projects: the seed's seven tools, the project's own tool folders (`root` and `search`), the comparison with `composer.json` and `package.json`, the document and the skill are new.

## Language servers

When the project has the LSP kit's table (`.conclave/lsp.json`), installing this kit adds the stack's servers to it: the `php` preset (Intelephense) for an app with `composer.json`, the `web` preset (TypeScript and Tailwind) for one with `package.json`, each with the app's folder as its `root`. Only servers the table lacks are added; one the project already has by that name is never changed. The result's `lsp_servers` lists what was added and kept.

The order of the two installs does not matter: installing the `lsp` kit into a project that already has this one fills the table the same way. Without the LSP kit nothing is written, and the result names the one command that installs the table and fills it. A table that does not load, or cannot be written, is reported and left as it was.
