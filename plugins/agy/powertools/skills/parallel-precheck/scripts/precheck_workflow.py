"""Parallel read-only pre-flight review workflow for Antigravity run_workflow.

Runs four same-family read-only research lenses concurrently to polish a diff
before dispatching independent cross-family review. Never counts as final sign-off.
"""
from __future__ import annotations

import json

LENS_SCHEMA = {
    "type": "object",
    "properties": {
        "lens": {"type": "string"},
        "status": {"type": "string", "enum": ["clean", "findings"]},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["P1", "P2", "P3"]},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "summary": {"type": "string"},
                    "evidence": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["severity", "file", "summary", "evidence"],
            },
        },
    },
    "required": ["lens", "status", "findings"],
}

LENSES = [
    (
        "silent-failure-hunter",
        "Silent Failure Hunter",
        "Hunt silent failures in the changed code: swallowed exceptions, empty catch/except blocks, broad fallbacks hiding real bugs, suppressed stderr/exit codes, and missing error context.",
    ),
    (
        "code-simplifier",
        "Code Simplifier",
        "Inspect the changed code for unnecessary complexity: deep nesting, duplicated logic, premature abstractions, dead code, and unclear control flow that can be flattened without changing behavior.",
    ),
    (
        "type-design-analyzer",
        "Type Design Analyzer",
        "Audit data structures, schemas, interfaces, and module boundaries introduced or modified: check invariant enforcement, stringly typed parameters, boundary validation, and mismatch risks.",
    ),
    (
        "layer-and-test-critic",
        "Layer and Test Critic",
        "Check whether every change fixes behavior at its owning layer (never masking downstream), verify matching regression and edge-case tests exist, and check subprocess/timeout/resource cleanup.",
    ),
]

cwd = (args.get("cwd") if isinstance(args, dict) else None) or (WORKSPACES[0] if WORKSPACES else ".")
base = (args.get("base") if isinstance(args, dict) else None) or "HEAD"
explicit_files = (args.get("files") if isinstance(args, dict) else None) or []
purpose = (args.get("purpose") if isinstance(args, dict) else None) or ""

phase("Collect Scope")
status_text = ""
diff_files = list(explicit_files)
if not diff_files:
    try:
        status_text = await call_tool(
            "run_command",
            CommandLine=f'git -C "{cwd}" status --short && git -C "{cwd}" diff --name-only {base}',
            WaitMsBeforeAsync=5000,
            toolSummary="Inspect changed files for pre-check",
        )
    except Exception as exc:
        log(f"Could not inspect git status automatically: {exc}")

scope_note = (
    f"Repository: {cwd}\n"
    f"Base ref: {base}\n"
    + (f"Purpose: {purpose}\n" if purpose else "")
    + (f"Target files: {', '.join(diff_files)}\n" if diff_files else f"Git scope output:\n{status_text[:6000]}\n")
)
log("Starting 4 read-only pre-flight lenses (polish only, never final sign-off).")

phase("Parallel Pre-check Lenses")


def make_prompt(lens_name: str, directive: str) -> str:
    return (
        f"You are running pre-flight lens `{lens_name}` (read-only analysis; do not edit files).\n\n"
        f"{scope_note}\n"
        f"Lens directive: {directive}\n\n"
        "Instructions:\n"
        "1. Inspect the changed files in the repository directly (`read_file`, search, or read-only `git diff`).\n"
        "2. Report ONLY concrete defects grounded in file paths and line numbers you actually read.\n"
        "3. Mark realistic runtime/contract bugs P1 or P2, and minor polish P3.\n"
        "4. Return JSON matching the required schema via `finish`."
    )


results = await parallel(
    LENSES,
    lambda item: agent(
        make_prompt(item[0], item[2]),
        schema=LENS_SCHEMA,
        role=item[1],
        type_name="research",
    ),
)

phase("Aggregate")
all_findings = []
for item, res in zip(LENSES, results):
    lens_name = item[0]
    findings = res.get("findings", []) if isinstance(res, dict) else []
    log(f"{lens_name}: {len(findings)} finding(s)")
    for f in findings:
        entry = dict(f)
        entry.setdefault("lens", lens_name)
        all_findings.append(entry)

severity_rank = {"P1": 0, "P2": 1, "P3": 2}
all_findings.sort(key=lambda x: (severity_rank.get(x.get("severity", "P3"), 9), x.get("file", ""), x.get("line", 0)))

report = {
    "note": "Pre-flight self-check only; still run independent cross-family review before shipping.",
    "total_findings": len(all_findings),
    "findings": all_findings,
}
print(json.dumps(report, indent=2))
