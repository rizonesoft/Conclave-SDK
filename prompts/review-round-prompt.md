# Independent Review Round Prompt

Evaluate the candidate implementation for section `<DNN TNN §N>` at commit `<FULL_CANDIDATE_SHA>`.

## Inputs to inspect

1. The section contract via `python scripts/todo-graph.py resolve "<DNN TNN §N>"`.
2. The candidate diff via `git show <FULL_CANDIDATE_SHA>` (or commit range `<BASE_SHA>..<TIP_SHA>`).
3. Governing documents named in the TODO file's `## Inputs` (`AGENTS.md`, foundation plan, `design/SPEC.md`).

## Lenses required

Report a verdict (`approve`, `needs-attention`, or `advisory`) for each lens with `file:line` citations for any finding:

- `adversarial`: Hostile inputs, bounds, races, cancellation/abort paths, unsafe automation, unconfirmed links.
- `consistency`: Module boundaries, naming, shared controls, settings store, typed error handling.
- `integration`: Callers, consumers, actor/threading contracts, job queues, shell slots.
- `source-defect`: Accuracy against upstream specifications and `design/SPEC.md`.
- `design`: Rendered surface fidelity against `design/SPEC.md` and design tokens (for `Surface: yes` sections), verifying 100% of controls on the surface are working or deferred to a resolving owner.
- `record`: Honesty of quoted checkpoint outputs, deferral owners, and full completion of every micro-step's `Done when:` without taking the named `Cheaper substitute:`.
