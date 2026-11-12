"""A stand-in for `codex app-server` in tests: JSON-RPC over stdio, answering from a scenario file.

The scenario (`CODEX_STUB_SCENARIO`, JSON) holds `listings`: the `hooks/list` result each server start answers, in
order (the last repeats). Options:

- `"silent": true` answers nothing; `"spawn_and_exit": true` starts a grandchild (its pid in `<scenario>.child`) and
  exits at once.
- `"apply_writes": true` reads back what earlier writes recorded: a listed hook whose key was written with its own
  `currentHash` reads `trusted`, as real Codex does, so a skipped or wrong write is visible to the next listing.
- `"refuse_after": N` answers the write after the Nth with an error; `"silent_after": N` stops answering after N.

Every `config/value/write` is appended to `<scenario>.writes.jsonl`, the start count is kept in `<scenario>.starts`,
and each start's `CODEX_HOME` is appended to `<scenario>.homes`, so a test reads what was asked and where.
"""
import json
import os
import pathlib
import sys

# With no scenario the stub answers an empty listing, so a doctor run in any test never waits on a real Codex.
scenario_path = pathlib.Path(os.environ["CODEX_STUB_SCENARIO"]) if os.environ.get("CODEX_STUB_SCENARIO") else None
scenario = json.loads(scenario_path.read_text(encoding="utf-8")) if scenario_path else {}
start = 0
writes_path = None
if scenario_path:
    starts_path = scenario_path.with_name(scenario_path.name + ".starts")
    start = int(starts_path.read_text()) if starts_path.exists() else 0
    starts_path.write_text(str(start + 1))
    with open(scenario_path.with_name(scenario_path.name + ".homes"), "a", encoding="utf-8") as fh:
        fh.write(os.environ.get("CODEX_HOME", "") + "\n")
    writes_path = scenario_path.with_name(scenario_path.name + ".writes.jsonl")

if scenario.get("spawn_and_exit") and scenario_path:
    # A launcher that starts the real server and exits: the grandchild must not outlive the client's close().
    import subprocess
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    scenario_path.with_name(scenario_path.name + ".child").write_text(str(child.pid))
    sys.exit(0)
listings = scenario.get("listings") or [{"data": []}]
listing = listings[min(start, len(listings) - 1)]


def written():
    if not writes_path or not writes_path.exists():
        return []
    return [json.loads(line) for line in writes_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def applied(listing):
    approvals = {}
    for write in written():
        if write.get("keyPath") == "hooks.state":
            for key, value in write.get("value", {}).items():
                approvals[key] = value.get("trusted_hash")
    for entry in listing.get("data", []):
        for hook in entry.get("hooks", []):
            if approvals.get(hook.get("key")) == hook.get("currentHash"):
                hook["trustStatus"] = "trusted"
    return listing


for line in sys.stdin:
    try:
        message = json.loads(line)
    except ValueError:
        continue
    if "id" not in message or scenario.get("silent"):
        continue
    method = message.get("method")
    count = len(written())
    if "silent_after" in scenario and method == "config/value/write" and count >= scenario["silent_after"]:
        continue
    if method == "initialize":
        result = {"userAgent": "stub", "codexHome": os.environ.get("CODEX_HOME", "stub")}
    elif method == "hooks/list":
        result = applied(listing) if scenario.get("apply_writes") else listing
    elif method == "config/value/write" and writes_path:
        if "refuse_after" in scenario and count >= scenario["refuse_after"]:
            print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "error": {"message": "stub refused"}}), flush=True)
            continue
        with open(writes_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(message["params"]) + "\n")
        result = {"status": "ok"}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "error": {"message": f"no {method}"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
