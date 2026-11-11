## What changed

<!-- One or two sentences on what now works. Name the TODO section when there is one, for example D01 T01 §3. -->

## How it was tested

<!-- The commands you ran and their result. A code change needs a test that fails before it and passes after it. -->

- [ ] `python -m unittest discover -s tests` passes
- [ ] `python scripts/todo-graph.py validate` passes
- [ ] The full suite passes, when the change touches the stamp, the review dispatcher or the pin loader

## The rules it keeps

- [ ] Python standard library only, with atomic writes
- [ ] A kit file was changed in the kit, and `python forge.py self-sync` was run
- [ ] The Claude Code, Codex and Antigravity copies of a skill were changed together
- [ ] No em dashes or en dashes, one line per paragraph, table rows at or under 120 characters
- [ ] No secret in the diff

## What was left out

<!-- Anything found and not fixed here, and where it was filed. -->

Layer: <!-- the layer that owns the behaviour, the layer you changed, and any workaround -->
