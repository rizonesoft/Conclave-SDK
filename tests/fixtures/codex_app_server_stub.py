"""A stand-in for `codex app-server` in tests: JSON-RPC over stdio, answering from a scenario file.

The scenario (`CODEX_STUB_SCENARIO`, JSON) holds `listings`: the `hooks/list` result each server start answers, in
order (the last repeats), and optionally `"silent": true` to answer nothing. Every `config/value/write` is appended
to `<scenario>.writes.jsonl`, and the start count is kept in `<scenario>.starts`, so a test reads what was asked.
"""
import json
import os
import pathlib
import sys

# With no scenario the stub answers an empty listing, so a doctor run in any test never waits on a real Codex.
scenario_path = pathlib.Path(os.environ["CODEX_STUB_SCENARIO"]) if os.environ.get("CODEX_STUB_SCENARIO") else None
scenario = json.loads(scenario_path.read_text(encoding="utf-8")) if scenario_path else {}
start = 0
if scenario_path:
    starts_path = scenario_path.with_name(scenario_path.name + ".starts")
    start = int(starts_path.read_text()) if starts_path.exists() else 0
    starts_path.write_text(str(start + 1))
listings = scenario.get("listings") or [{"data": []}]
listing = listings[min(start, len(listings) - 1)]

for line in sys.stdin:
    try:
        message = json.loads(line)
    except ValueError:
        continue
    if "id" not in message or scenario.get("silent"):
        continue
    method = message.get("method")
    if method == "initialize":
        result = {"userAgent": "stub", "codexHome": "stub"}
    elif method == "hooks/list":
        result = listing
    elif method == "config/value/write" and scenario_path:
        with open(scenario_path.with_name(scenario_path.name + ".writes.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(message["params"]) + "\n")
        result = {"status": "ok"}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "error": {"message": f"no {method}"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
