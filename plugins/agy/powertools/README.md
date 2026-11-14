# Conclave Powertools (`agy-powertools`)

Antigravity engineering rigor bundle packaged for standalone global deployment via `global/deploy.py --agent agy`.

## Contents

| Component | Relative Path | Purpose |
| --------- | ------------- | ------- |
| Rules | `rules/AGENTS.md` | Owning-layer fixes, trunk hygiene, and safety |
| Hooks | `hooks.json` | Catastrophic guard, layer/launcher, NLP checks |
| `receiving-code-review` | `skills/receiving-code-review` | Evidence-based review intake and pushback |
| `systematic-debugging` | `skills/systematic-debugging` | Four-phase root-cause analysis at owning layer |
| `verification-before-completion` | `skills/verification-before-completion` | Fresh proving commands and diff checks |
| `test-driven-development` | `skills/test-driven-development` | Red-green-refactor cycle and process hygiene |
| `parallel-precheck` | `skills/parallel-precheck` | Parallel `run_workflow` pre-check and dispatch |
| `code-simplifier` | `skills/code-simplifier` | Post-change clarity pass keeping behavior |
| `improving-agent-configs` | `skills/improving-agent-configs` | Audits rules, skills, and plugin bundles |

## Installation

Deploy on Windows and WSL from this checkout without manually editing `~/.gemini/config/config.json`:

```powershell
python global/deploy.py --agent agy
```

Validate with Antigravity:

```powershell
agy plugin validate plugins/agy/powertools --strict
```
