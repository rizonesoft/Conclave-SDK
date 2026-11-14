# Root Cause Tracing

Fix faults at the source that produces invalid state rather than guarding every downstream caller.

## Tracing backward

1. Capture the exact failing value and stack frame where the error surfaces.
2. Inspect what passed that value into the failing function.
3. Walk upward frame by frame until you reach the first boundary where the value originated or silently mutated (config loader, parser, serializer, subprocess wrapper, database query, or event payload).
4. Fix that origin boundary so bad values cannot enter the pipeline, and add defense-in-depth validation only at trust boundaries when callers are external.

## Multi-component boundary check

When a system crosses boundaries (for example Antigravity hook -> Python script -> state JSON -> transcript parser, or frontend -> API -> worker):

1. Log or inspect the exact payload entering and leaving each boundary in one pass.
2. Compare field names, casing (`camelCase` vs `snake_case`), relative vs absolute paths, and line endings across boundaries.
3. Remove temporary diagnostic logs and scratch files once the broken boundary is identified and covered by a permanent test.
