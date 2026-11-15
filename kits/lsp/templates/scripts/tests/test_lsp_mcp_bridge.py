"""The MCP bridge: its wire format, each tool's outcomes, servers kept running, diagnostics never older than the
file, the read-only boundary, what a long-lived client holds, and that every server ends with the bridge.

The language servers are stubs: one Python program, written here, that behaves as its JSON configuration says and
logs what it receives. The bridge is run as a process and spoken to in MCP, as an agent does.
"""
import importlib.util
import io
import json
import os
import pathlib
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS / "lib"))
import lsp_client  # noqa: E402
import lsp_table  # noqa: E402

BRIDGE = SCRIPTS / "lsp-mcp-bridge.py"
spec = importlib.util.spec_from_file_location("lsp_mcp_bridge", BRIDGE)
bridge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge_module)

STUB = r'''
import json, os, subprocess, sys, threading, time

config = json.load(open(sys.argv[1], encoding="utf-8"))
lock = threading.Lock()
POSITION = ("textDocument/hover", "textDocument/definition", "textDocument/references")


def record(kind, value):
    with lock, open(config["log"], "a", encoding="utf-8") as log:
        log.write(json.dumps({"kind": kind, "value": value}) + "\n")


def send(message):
    body = json.dumps(message).encode("utf-8")
    with lock:
        sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        sys.stdout.buffer.flush()


def read():
    length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    return json.loads(sys.stdin.buffer.read(length)) if length else {}


def found(text):
    return [{"range": {"start": {"line": number, "character": 0}, "end": {"line": number, "character": 1}},
             "severity": 1, "code": "stub", "message": line.split("E:", 1)[1].strip()}
            for number, line in enumerate(text.splitlines()) if "E:" in line]


def publish(uri, items, version=None):
    params = {"uri": uri, "diagnostics": items}
    if version is not None:
        params["version"] = version
    send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics", "params": params})


record("started", {"pid": os.getpid(), "cwd": os.getcwd()})
if config.get("child"):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(config["pids"], "w", encoding="utf-8") as pids:
        pids.write(f"{os.getpid()} {child.pid}")
texts = {}
while True:
    message = read()
    if message is None:
        break
    method = message.get("method")
    if method:
        record("method", method)
    if method == "initialize":
        record("initialize", {"options": message["params"].get("initializationOptions"),
                              "root": message["params"].get("rootUri")})
        scratch = (message["params"].get("initializationOptions") or {}).get("storagePath")
        if isinstance(scratch, str):
            record("scratch", {"path": scratch, "exists": os.path.isdir(scratch)})
        if config.get("init") == "error":
            send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32002, "message": "no workspace here"}})
            continue
        send({"jsonrpc": "2.0", "id": message["id"], "result": {"capabilities": {"textDocumentSync": 1}}})
    elif method == "initialized":
        if config.get("stop_reading"):
            time.sleep(120)
    elif method == "workspace/didChangeConfiguration":
        record("settings", message["params"])
    elif method == "textDocument/didOpen":
        document = message["params"]["textDocument"]
        texts[document["uri"]] = document["text"]
        record("open", {"uri": document["uri"], "languageId": document["languageId"]})
        if config.get("apply_edit"):
            send({"jsonrpc": "2.0", "id": 7001, "method": "workspace/applyEdit", "params": {"edit": {"changes": {
                document["uri"]: [{"range": {"start": {"line": 0, "character": 0},
                                             "end": {"line": 0, "character": 0}}, "newText": "EDITED "}]}}}})
        if config.get("extra_uri"):
            publish(config["extra_uri"], found("E: for a document nobody opened"))
        if not config.get("no_answer"):
            publish(document["uri"], found(document["text"]), 1 if config.get("versions") else None)
    elif method == "textDocument/didChange":
        document = message["params"]["textDocument"]
        old, new = texts.get(document["uri"], ""), message["params"]["contentChanges"][0]["text"]
        texts[document["uri"]] = new
        record("change", {"uri": document["uri"], "version": document["version"]})
        mode = config.get("on_change", "answer")
        version = document["version"] if config.get("versions") else None
        if mode == "late_old":
            # The old text's diagnostics arrive late, then the new text's.
            threading.Timer(0.2, publish, (document["uri"], found(old), version - 1 if version else None)).start()
            threading.Timer(0.6, publish, (document["uri"], found(new), version)).start()
        elif mode == "old_only":
            threading.Timer(0.2, publish, (document["uri"], found(old), version - 1)).start()
        elif mode == "answer":
            publish(document["uri"], found(new), version)
    elif method == "textDocument/didClose":
        record("close", message["params"]["textDocument"]["uri"])
    elif method in POSITION:
        mode = config.get("position", "answer")
        place = message["params"]["position"]
        uri = message["params"]["textDocument"]["uri"]
        if mode == "silent":
            continue
        if mode in ("error", "unsupported"):
            code, text = (-32601, "Method not found") if mode == "unsupported" else (-32603, "boom")
            send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": code, "message": text}})
        elif mode == "empty":
            send({"jsonrpc": "2.0", "id": message["id"], "result": [] if method.endswith("references") else None})
        elif method.endswith("hover"):
            send({"jsonrpc": "2.0", "id": message["id"], "result": {"contents": {
                "kind": "plaintext", "value": f"{config['name']} at {place['line']}:{place['character']}"}}})
        else:
            spans = [(0, 4)] if method.endswith("definition") else [(0, 4), (2, 0)]
            send({"jsonrpc": "2.0", "id": message["id"], "result": [
                {"uri": uri, "range": {"start": {"line": line, "character": character},
                                       "end": {"line": line, "character": character + 1}}}
                for line, character in spans]})
        if config.get("exit_after_position"):
            sys.exit(0)
    elif method == "shutdown":
        send({"jsonrpc": "2.0", "id": message["id"], "result": None})
    elif method == "exit":
        break
    elif method is None and "id" in message:
        record("response", message)
    elif "id" in message:
        send({"jsonrpc": "2.0", "id": message["id"], "result": None})
'''


def alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def gone(pid, seconds=10):
    deadline = time.monotonic() + seconds
    while alive(pid):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.1)
    return True


class Running:
    """The bridge as a process, spoken to in MCP."""

    def __init__(self, project, timeout=20):
        windows = os.name == "nt"
        self.proc = subprocess.Popen([sys.executable, "-B", str(BRIDGE), "--root", str(project), "--timeout",
                                      str(timeout)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, start_new_session=not windows,
                                     creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
                                     if windows else 0)
        self.replies = queue.Queue()
        self.number = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.replies.put(json.loads(line))
        self.replies.put(None)

    def send(self, message):
        text = message if isinstance(message, str) else json.dumps(message)
        self.proc.stdin.write(text.encode("utf-8") + b"\n")
        self.proc.stdin.flush()

    def reply(self, seconds=60):
        return self.replies.get(timeout=seconds)

    def rpc(self, method, params=None, seconds=60):
        self.number += 1
        self.send({"jsonrpc": "2.0", "id": self.number, "method": method, **({"params": params} if params else {})})
        reply = self.reply(seconds)
        assert reply is not None and reply["id"] == self.number, reply
        return reply

    def call(self, tool, seconds=60, **arguments):
        reply = self.rpc("tools/call", {"name": tool, "arguments": arguments}, seconds)
        if "error" in reply:
            return reply["error"]
        result = reply["result"]
        assert [item["type"] for item in result["content"]] == ["text"], result
        return result["content"][0]["text"], result["isError"]

    def end(self):
        """Close the input, as an agent does when it is done: the exit code."""
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        return self.proc.wait(timeout=30)

    def cleanup(self):
        if self.proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.proc.wait(timeout=30)
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except OSError:
                pass


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name).resolve()
        self.project = self.dir / "project"
        (self.project / ".conclave").mkdir(parents=True)
        self.stub = self.dir / "stub-server.py"
        self.stub.write_text(STUB, encoding="utf-8")
        self.entries = []

    def server(self, name="stub", extensions=None, behaviour=None, **keys):
        config = self.dir / f"{name}.json"
        behaviour = dict(behaviour or {}, name=name, log=str(self.dir / f"{name}.log"),
                         pids=str(self.dir / f"{name}.pids"))
        config.write_text(json.dumps(behaviour), encoding="utf-8")
        self.entries.append({"name": name, "command": [sys.executable, str(self.stub), str(config)],
                             "extensions": extensions or {".py": "python"}, "install": f"install {name} by hand",
                             "settle": 1, **keys})
        self.write_table()

    def write_table(self):
        (self.project / lsp_table.TABLE).write_text(json.dumps({"schema_version": 1, "servers": self.entries}),
                                                    encoding="utf-8")

    def file(self, rel, text="clean\n"):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return rel

    def log(self, name="stub", kind=None):
        path = self.dir / f"{name}.log"
        if not path.is_file():
            return []
        items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        return [item["value"] for item in items if kind is None or item["kind"] == kind]

    def pids(self, name="stub"):
        path = self.dir / f"{name}.pids"
        deadline = time.monotonic() + 10
        while not (path.is_file() and len(path.read_text().split()) == 2):
            self.assertLess(time.monotonic(), deadline, "the stub never wrote its process ids")
            time.sleep(0.05)
        return [int(pid) for pid in path.read_text().split()]

    def bridge(self, timeout=20):
        running = Running(self.project, timeout)
        self.addCleanup(running.cleanup)
        return running

    def in_process(self, **options):
        """A Bridge object in this process, closed with the test."""
        options.setdefault("timeout", 20)
        bridge = bridge_module.Bridge(self.project, **options)
        self.addCleanup(bridge.close)
        return bridge


class ProtocolTests(Fixture):
    def test_the_lifecycle_and_the_tool_list_are_as_the_specification_writes_them(self):
        self.server()
        bridge = self.bridge()
        reply = bridge.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                          "clientInfo": {"name": "test", "version": "0"}})
        self.assertEqual(reply["jsonrpc"], "2.0")
        result = reply["result"]
        self.assertEqual(result["protocolVersion"], "2025-03-26")   # a version the bridge speaks is agreed to
        self.assertEqual(result["capabilities"], {"tools": {"listChanged": False}})
        self.assertEqual(result["serverInfo"], {"name": "conclave-lsp", "version": "1.0.0"})
        # A notification gets no reply: the next thing on the wire answers the ping.
        bridge.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(bridge.rpc("ping")["result"], {})
        tools = bridge.rpc("tools/list")["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["diagnostics", "definition", "references", "hover"])
        for tool in tools:
            self.assertTrue(tool["description"])
            schema = tool["inputSchema"]
            self.assertEqual((schema["type"], schema["additionalProperties"]), ("object", False))
            self.assertEqual(schema["required"], list(schema["properties"]))
            self.assertEqual(schema["properties"]["file"]["type"], "string")
        self.assertEqual(list(tools[0]["inputSchema"]["properties"]), ["file"])
        self.assertEqual(list(tools[1]["inputSchema"]["properties"]), ["file", "line", "column"])
        self.assertEqual(tools[1]["inputSchema"]["properties"]["line"], {
            "type": "integer", "minimum": 1, "description": "The line, counted from 1."})
        self.assertEqual(bridge.end(), 0)

    def test_a_version_the_bridge_does_not_know_is_answered_with_its_latest(self):
        self.server()
        bridge = self.bridge()
        self.assertEqual(bridge.rpc("initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"],
                         "2025-06-18")
        self.assertEqual(bridge_module.VERSIONS[0], "2025-06-18")

    def test_a_bad_line_an_unknown_method_and_arguments_that_do_not_fit_are_errors_and_the_bridge_goes_on(self):
        self.server()
        rel = self.file("a.py")
        bridge = self.bridge()
        bridge.send("this is not json")
        self.assertEqual(bridge.reply()["error"]["code"], -32700)
        bridge.send("[1, 2]")
        self.assertEqual(bridge.reply()["error"]["code"], -32600)
        self.assertEqual(bridge.rpc("resources/list")["error"]["code"], -32601)
        cases = [("rename", {"file": rel, "line": 1, "column": 1, "newName": "x"}, "Unknown tool: rename"),
                 ("diagnostics", {}, "diagnostics: file must be a path"),
                 ("diagnostics", {"file": rel, "fix": True}, "diagnostics: unknown argument 'fix'"),
                 ("hover", {"file": rel, "line": 0, "column": 1}, "hover: line must be a whole number from 1"),
                 ("hover", {"file": rel, "line": 1, "column": "2"}, "hover: column must be a whole number from 1"),
                 ("hover", {"file": rel, "line": True, "column": 1}, "hover: line must be a whole number from 1"),
                 ("definition", {"file": rel, "line": 1}, "definition: column must be a whole number from 1")]
        for tool, arguments, message in cases:
            with self.subTest(tool=tool, arguments=arguments):
                self.assertEqual(bridge.call(tool, **arguments), {"code": -32602, "message": message})
        # A tool that fails is a result with isError, not a protocol error.
        self.assertEqual(bridge.call("diagnostics", file="../outside.py"), ("../outside.py is outside the project", True))
        self.assertEqual(bridge.call("diagnostics", file="absent.py"), ("absent.py is not a file of the project", True))
        self.assertEqual(bridge.call("diagnostics", file=rel), ("stub: clean", False))   # and it still answers
        self.assertEqual(self.log(kind="started").__len__(), 1)


class ToolTests(Fixture):
    def test_diagnostics_definition_references_and_hover_are_read_back_as_project_places(self):
        self.server()
        rel = self.file("src/app.py", "name = 1\nE: undefined name\nprint(name)\n")
        bridge = self.bridge()
        self.assertEqual(bridge.call("diagnostics", file=rel),
                         ("stub: 1 diagnostic(s)\n  src/app.py:2:1  error  undefined name [stub]", False))
        self.assertEqual(bridge.call("definition", file=rel, line=3, column=7), ("stub:\n  src/app.py:1:5", False))
        self.assertEqual(bridge.call("references", file=rel, line=3, column=7),
                         ("stub:\n  src/app.py:1:5\n  src/app.py:3:1", False))
        # The place is sent to the server counted from 0.
        self.assertEqual(bridge.call("hover", file=rel, line=3, column=7), ("stub:\n  stub at 2:6", False))
        opened = self.log(kind="open")
        self.assertEqual([(pathlib.Path(item["uri"]).name, item["languageId"]) for item in opened],
                         [("app.py", "python")])
        self.assertEqual(bridge.end(), 0)

    def test_a_column_is_sent_in_the_units_the_protocol_counts(self):
        self.server()
        rel = self.file("wide.py", "s = '\U0001f600é'; name\n")   # one character outside the basic plane
        bridge = self.bridge()
        # Column 12 is the `n` of name: 11 characters before it, one of them two UTF-16 units.
        self.assertEqual(bridge.call("hover", file=rel, line=1, column=12), ("stub:\n  stub at 0:12", False))
        # A place past the end of the file is still asked, as given.
        self.assertEqual(bridge.call("hover", file=rel, line=9, column=3), ("stub:\n  stub at 8:2", False))

    def test_a_server_is_started_once_and_a_changed_file_is_sent_again(self):
        self.server()
        rel = self.file("a.py", "x = 1\n")
        other = self.file("b.py", "E: in the second file\n")
        bridge = self.bridge()
        self.assertEqual(bridge.call("diagnostics", file=rel), ("stub: clean", False))
        self.assertEqual(bridge.call("hover", file=rel, line=1, column=1)[1], False)
        self.assertEqual(bridge.call("diagnostics", file=other)[0].splitlines()[0], "stub: 1 diagnostic(s)")
        started = self.log(kind="started")
        self.assertEqual(len(started), 1, "the server was started for more than one call")
        # Edited between two calls: the diagnostics follow the edit, by a change and not a new server.
        self.file("a.py", "x = 1\nE: added since\n")
        self.assertEqual(bridge.call("diagnostics", file=rel),
                         ("stub: 1 diagnostic(s)\n  a.py:2:1  error  added since [stub]", False))
        self.file("a.py", "x = 2\n")
        self.assertEqual(bridge.call("diagnostics", file=rel), ("stub: clean", False))   # an error fixed reads clean
        self.assertEqual([item["version"] for item in self.log(kind="change")], [2, 3])
        self.assertEqual(len(self.log(kind="started")), 1)
        # An unchanged file is answered from what the server last said of it, with nothing sent.
        sent = len(self.log(kind="method"))
        self.assertEqual(bridge.call("diagnostics", file=rel), ("stub: clean", False))
        self.assertEqual(len(self.log(kind="method")), sent)

    def test_a_server_that_ended_is_started_again_by_the_next_call(self):
        self.server(behaviour={"exit_after_position": True})
        rel = self.file("a.py")
        bridge = self.bridge()
        self.assertEqual(bridge.call("hover", file=rel, line=1, column=1), ("stub:\n  stub at 0:0", False))
        self.assertEqual(bridge.call("hover", file=rel, line=1, column=2), ("stub:\n  stub at 0:1", False))
        pids = [item["pid"] for item in self.log(kind="started")]
        self.assertEqual(len(set(pids)), 2, "the ended server was not started again")

    def test_a_changed_entry_starts_the_server_again_with_it(self):
        self.server(init={"mode": "first"})
        rel = self.file("a.py")
        bridge = self.bridge()
        bridge.call("diagnostics", file=rel)
        self.entries[0]["init"] = {"mode": "second"}
        self.write_table()
        bridge.call("diagnostics", file=rel)
        self.assertEqual([item["options"] for item in self.log(kind="initialize")], [{"mode": "first"},
                                                                                    {"mode": "second"}])


class OutcomeTests(Fixture):
    def two(self, first, **keys):
        """Two servers for .py files: `first` behaving as given, `second` answering."""
        self.server("first", behaviour=first, **keys)
        self.server("second")
        return self.file("a.py", "E: found by both\n")

    def test_a_later_server_is_asked_when_an_earlier_one_fails_or_answers_nothing(self):
        cases = [({"init": "error"}, "first: failed: refused initialize: no workspace here"),
                 ({"position": "empty"}, "first: no definition at a.py:1:1"),
                 ({"position": "error"}, "first: answered with an error: boom"),
                 ({"position": "unsupported"}, "first: does not support textDocument/definition"),
                 ({"position": "silent"}, "first: not answered within 2 seconds")]
        for number, (behaviour, outcome) in enumerate(cases):
            with self.subTest(first=behaviour):
                self.entries = []
                for name in ("first", "second"):
                    (self.dir / f"{name}.log").unlink(missing_ok=True)
                rel = self.two(behaviour)
                bridge = self.bridge(timeout=2)
                self.assertEqual(bridge.call("definition", file=rel, line=1, column=1),
                                 (f"second:\n  a.py:1:5\n({outcome})", False))
                bridge.end()

    def test_a_server_that_is_missing_or_skipped_is_named_and_the_next_is_asked(self):
        self.entries.append({"name": "absent", "command": ["no-such-language-server-anywhere"],
                             "extensions": {".py": "python"}, "install": "npm install -g absent"})
        self.server("needy", requires="pyproject.toml")
        self.server("second")
        rel = self.file("a.py", "E: wrong\n")
        bridge = self.bridge()
        missing = "absent: missing: not installed. Install: npm install -g absent"
        skipped = "needy: skipped: requires pyproject.toml"
        self.assertEqual(bridge.call("hover", file=rel, line=1, column=1),
                         (f"second:\n  second at 0:0\n({missing})\n({skipped})", False))
        self.assertEqual(bridge.call("diagnostics", file=rel),
                         (f"{missing}\n{skipped}\nsecond: 1 diagnostic(s)\n  a.py:1:1  error  wrong [stub]", False))
        self.assertEqual(self.log("needy"), [], "a skipped server was started")

    def test_no_server_able_to_answer_is_an_error_and_every_server_answering_nothing_is_not(self):
        rel = self.two({"init": "error"})
        self.entries[1]["command"] = ["no-such-language-server-anywhere"]
        self.write_table()
        bridge = self.bridge()
        text, failed = bridge.call("references", file=rel, line=1, column=1)
        self.assertTrue(failed)
        self.assertEqual(text, "No references found at a.py:1:1.\n"
                               "first: failed: refused initialize: no workspace here\n"
                               "second: missing: not installed. Install: install second by hand")
        text, failed = bridge.call("diagnostics", file=rel)
        self.assertTrue(failed)
        self.assertEqual(text.splitlines()[0], "first: failed: refused initialize: no workspace here")
        bridge.end()
        self.entries = []
        self.server("first", behaviour={"position": "empty"})
        self.server("second", behaviour={"position": "empty"})
        bridge = self.bridge()
        self.assertEqual(bridge.call("hover", file=rel, line=1, column=1),
                         ("No hover found at a.py:1:1.\nfirst: no hover at a.py:1:1\nsecond: no hover at a.py:1:1",
                          False))

    def test_a_file_no_server_serves_an_empty_table_and_a_broken_table_each_have_their_own_answer(self):
        self.server()
        notes = self.file("notes.txt")
        self.file("a.py")
        bridge = self.bridge()
        self.assertEqual(bridge.call("diagnostics", file=notes), ("No server of .conclave/lsp.json serves notes.txt.",
                                                                  False))
        self.assertEqual(bridge.call("hover", file=notes, line=1, column=1)[1], False)
        self.assertEqual(self.log(), [], "a server was started for a file it does not serve")
        (self.project / "folder.py").mkdir()
        self.assertEqual(bridge.call("diagnostics", file="folder.py"), ("folder.py is not a file of the project", True))
        self.entries = []
        self.write_table()
        self.assertEqual(bridge.call("diagnostics", file="a.py"),
                         (".conclave/lsp.json holds no server: add a stack's with python scripts/lsp-servers.py add "
                          "<preset>", True))
        (self.project / lsp_table.TABLE).write_text('{"schema_version": 1, "servers": [{"name": "x"}]}',
                                                    encoding="utf-8")
        text, failed = bridge.call("definition", file="a.py", line=1, column=1)
        self.assertTrue(failed)
        self.assertTrue(text.startswith(".conclave/lsp.json: server 'x': missing key"), text)

    def test_a_file_that_cannot_be_read_is_an_error_naming_it(self):
        self.server()
        rel = self.file("locked.py")
        bridge = self.in_process()
        real = pathlib.Path.read_text

        def read_text(path, *args, **kwargs):
            if path.name == "locked.py":
                raise PermissionError(13, "Permission denied")
            return real(path, *args, **kwargs)

        with unittest.mock.patch.object(pathlib.Path, "read_text", read_text):
            self.assertEqual(bridge.call("diagnostics", {"file": rel}),
                             ("locked.py cannot be read (Permission denied)", True))
        self.assertEqual(self.log(), [])


class FreshnessTests(Fixture):
    def test_a_late_answer_for_the_old_text_is_overtaken_by_the_one_for_the_new(self):
        for versions in (False, True):
            with self.subTest(server_gives_versions=versions):
                self.entries = []
                (self.dir / "stub.log").unlink(missing_ok=True)
                self.server(behaviour={"on_change": "late_old", "versions": versions})
                rel = self.file("a.py", "E: in the old text\n")
                bridge = self.bridge()
                self.assertEqual(bridge.call("diagnostics", file=rel)[0].splitlines()[1],
                                 "  a.py:1:1  error  in the old text [stub]")
                self.file("a.py", "fine\nE: in the new text\n")
                self.assertEqual(bridge.call("diagnostics", file=rel),
                                 ("stub: 1 diagnostic(s)\n  a.py:2:1  error  in the new text [stub]", False))
                bridge.end()

    def test_a_server_that_publishes_nothing_for_the_new_text_is_not_answered_never_its_earlier_result(self):
        # With versions the late publication is known to be for the old text; without, no publication at all.
        for behaviour in ({"on_change": "old_only", "versions": True}, {"on_change": "silent"}):
            with self.subTest(behaviour=behaviour):
                self.entries = []
                (self.dir / "stub.log").unlink(missing_ok=True)
                self.server(behaviour=behaviour)
                rel = self.file("a.py", "E: in the old text\n")
                bridge = self.bridge(timeout=3)
                self.assertEqual(bridge.call("diagnostics", file=rel)[0].splitlines()[0], "stub: 1 diagnostic(s)")
                self.file("a.py", "fixed\n")
                self.assertEqual(bridge.call("diagnostics", file=rel), ("stub: not answered within 3 seconds", True))
                bridge.end()


class StartupTests(Fixture):
    def test_a_server_is_started_for_the_bridge_as_for_a_check(self):
        self.server(root="app", init={"mode": "strict", "storagePath": "${scratch}"},
                    settings={"stub": {"lint": True}}, requires="marker")
        rel = self.file("app/src/main.py", "E: wrong\n")
        bridge = self.bridge()
        self.assertEqual(bridge.call("diagnostics", file=rel), ("stub: skipped: requires app/marker", True))
        self.assertEqual(self.log(), [])
        self.file("app/marker", "")
        self.assertEqual(bridge.call("diagnostics", file=rel)[0].splitlines()[1],
                         "  app/src/main.py:1:1  error  wrong [stub]")
        (started,) = self.log(kind="started")
        self.assertTrue(os.path.samefile(started["cwd"], self.project / "app"))
        (initialize,) = self.log(kind="initialize")
        self.assertEqual(initialize["root"], (self.project / "app").resolve().as_uri())
        self.assertEqual(initialize["options"]["mode"], "strict")
        (settings,) = self.log(kind="settings")
        self.assertEqual(settings, {"settings": {"stub": {"lint": True}}})
        (scratch,) = self.log(kind="scratch")
        folder = pathlib.Path(scratch["path"])
        self.assertTrue(scratch["exists"])
        self.assertTrue(folder.is_dir(), "the scratch folder is gone while the server still runs")
        self.assertNotIn(self.project, [folder, *folder.parents])
        self.assertEqual(bridge.end(), 0)
        self.assertFalse(folder.exists(), "the scratch folder outlived the bridge")


class BoundsTests(Fixture):
    def test_a_server_holds_no_more_open_documents_than_the_cap_and_nothing_of_one_nobody_opened(self):
        foreign = "file:///nobody/opened.py"
        self.server(behaviour={"extra_uri": foreign})
        bridge = self.in_process(open_documents=3)
        names = [self.file(f"f{number}.py", f"E: file {number}\n") for number in range(5)]
        for rel in names:
            text, failed = bridge.call("diagnostics", {"file": rel})
            self.assertEqual((text.splitlines()[0], failed), ("stub: 1 diagnostic(s)", False))
            session = bridge.sessions["stub"]
            self.assertLessEqual(len(session.documents), 3)
            self.assertEqual(set(session.client.keep), set(session.documents))
            self.assertLessEqual(len(session.client.diagnostics), 3)
        closed = [pathlib.Path(uri).name for uri in self.log(kind="close")]
        self.assertEqual(closed, ["f0.py", "f1.py"])   # the ones used longest ago
        session = bridge.sessions["stub"]
        self.assertNotIn(foreign, session.client.diagnostics)
        self.assertNotIn(foreign, session.client.published)
        # A closed document is opened again when it is asked for, and is answered.
        self.assertEqual(bridge.call("diagnostics", {"file": "f0.py"})[0].splitlines()[1],
                         "  f0.py:1:1  error  file 0 [stub]")
        self.assertEqual(bridge_module.OPEN_DOCUMENTS, 64)

    def test_a_server_that_stops_reading_is_ended_and_started_again_by_the_next_call(self):
        self.server(behaviour={"stop_reading": True, "child": True})
        big = self.file("big.py", "value = 1\n" * 60_000)   # 600 kB: more than may wait to be written
        bridge = self.in_process(timeout=5, outbox_limit=256 * 1024)
        text, failed = bridge.call("diagnostics", {"file": big})
        self.assertTrue(failed)
        self.assertEqual(text, "stub: failed: was stopped: it stopped reading (more than 262144 bytes were waiting to "
                               "be written to it)")
        self.assertEqual(bridge.sessions, {})
        for pid in self.pids():
            self.assertTrue(gone(pid), f"process {pid} outlived the server that stopped reading")
        (self.dir / "stub.pids").unlink()
        bridge.call("diagnostics", {"file": big})
        self.assertEqual(len(self.log(kind="started")), 2, "the next call did not start the server again")
        self.assertEqual(bridge_module.OUTBOX_LIMIT, 64 * 1024 * 1024)

    def test_a_long_lived_client_is_not_ended_by_the_cap_of_one_check(self):
        self.server()
        (entry,) = lsp_table.load_servers(self.project)
        path = self.project / self.file("a.py", "E: wrong\n")
        for limit, survives in ((200, False), (None, True)):
            with self.subTest(read_limit=limit):
                status, _reason, client, _scratch, _stderr = lsp_client.start_server(entry, self.project,
                                                                                     read_limit=limit)
                if status != "ok":
                    self.assertFalse(survives)
                    continue
                try:
                    uri = client.open(path, "python")
                    deadline = time.monotonic() + 10
                    while uri not in client.diagnostics and client.alive and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertEqual(uri in client.diagnostics, survives)
                    self.assertEqual(client.failure is None, survives)
                finally:
                    client.close()
        # The cap on one message stays whatever the cap on the whole.
        status, reason, _client, _scratch, _stderr = lsp_client.start_server(entry, self.project, read_limit=None,
                                                                             message_limit=20)
        self.assertEqual(status, "failed")
        self.assertIn("over the 20 byte limit", reason)

    def test_a_response_that_arrives_after_its_request_was_given_up_is_not_kept(self):
        self.server(behaviour={"position": "silent"})
        (entry,) = lsp_table.load_servers(self.project)
        status, _reason, client, _scratch, _stderr = lsp_client.start_server(entry, self.project, read_limit=None)
        self.assertEqual(status, "ok")
        place = {"textDocument": {"uri": "file:///a.py"}, "position": {"line": 0, "character": 0}}
        try:
            self.assertIsNone(client.request("textDocument/hover", place, timeout=0.2))
            self.assertTrue(client.alive)
            number = client._id
            self.assertIn(number, client._abandoned)
            client._dispatch({"jsonrpc": "2.0", "id": number, "result": {"late": True}})   # it comes after all
            self.assertEqual(client.responses, {})
            self.assertEqual(client._abandoned, set())
            stop = threading.Event()
            stop.set()
            started = time.monotonic()
            self.assertIsNone(client.request("textDocument/hover", place, timeout=30, stop=stop))
            self.assertLess(time.monotonic() - started, 5, "a stopped wait went on waiting")
        finally:
            client.close()


class ReadOnlyTests(Fixture):
    EDITING = ("textDocument/rename", "textDocument/formatting", "textDocument/rangeFormatting",
               "textDocument/codeAction", "workspace/executeCommand", "workspace/applyEdit",
               "textDocument/willSaveWaitUntil", "workspace/willRenameFiles")

    def test_nothing_that_edits_can_be_asked_of_a_server(self):
        self.server()
        rel = self.file("a.py", "name = 1\n")
        before = (self.project / rel).read_bytes()
        running = self.bridge()
        self.assertEqual(running.call("rename", file=rel, line=1, column=1, newName="other"),
                         {"code": -32602, "message": "Unknown tool: rename"})
        running.end()
        bridge = self.in_process()
        bridge.call("diagnostics", {"file": rel})
        session = bridge.sessions["stub"]
        for method in self.EDITING:
            with self.subTest(method=method):
                with self.assertRaises(bridge_module.Forbidden):
                    bridge.lsp_request(session, method, {"textDocument": {"uri": "file:///x"}, "newName": "other"})
        # The allow-list is the whole of what can be sent, and holds nothing that edits.
        self.assertEqual(bridge_module.READ_ONLY_REQUESTS,
                         {"initialize", "shutdown", "textDocument/hover", "textDocument/definition",
                          "textDocument/references"})
        self.assertFalse(set(self.EDITING) & bridge_module.READ_ONLY_REQUESTS)
        bridge.close()
        received = set(self.log(kind="method"))
        self.assertFalse(received & set(self.EDITING), "an editing request reached the server")
        self.assertEqual((self.project / rel).read_bytes(), before)

    def test_a_server_that_asks_for_an_edit_is_told_it_was_not_made(self):
        self.server(behaviour={"apply_edit": True})
        rel = self.file("a.py", "name = 1\n")
        bridge = self.bridge()
        self.assertEqual(bridge.call("diagnostics", file=rel), ("stub: clean", False))
        bridge.end()
        (response,) = self.log(kind="response")
        self.assertEqual((response["id"], response["result"]),
                         (7001, {"applied": False, "failureReason": "this client is read-only"}))
        self.assertEqual((self.project / rel).read_bytes(), b"name = 1\n")


class ShutdownTests(Fixture):
    def waiting(self, timeout=120):
        """A bridge in the middle of a call that waits on a server which never answers: (bridge, the pids)."""
        self.server(behaviour={"no_answer": True, "child": True})
        rel = self.file("a.py")
        bridge = self.bridge(timeout=timeout)
        bridge.number += 1
        bridge.send({"jsonrpc": "2.0", "id": bridge.number, "method": "tools/call",
                     "params": {"name": "diagnostics", "arguments": {"file": rel}}})
        pids = self.pids()
        deadline = time.monotonic() + 10
        while not self.log(kind="open"):
            self.assertLess(time.monotonic(), deadline, "the call never reached the server")
            time.sleep(0.05)
        return bridge, pids

    def ended(self, bridge, pids, code=0):
        started = time.monotonic()
        self.assertEqual(bridge.proc.wait(timeout=15), code)
        for pid in pids:
            self.assertTrue(gone(pid), f"process {pid} outlived the bridge")
        self.assertLess(time.monotonic() - started, 10)

    def test_the_end_of_input_ends_an_idle_bridge_and_its_servers(self):
        self.server(behaviour={"child": True})
        rel = self.file("a.py")
        bridge = self.bridge()
        self.assertEqual(bridge.call("diagnostics", file=rel), ("stub: clean", False))
        pids = self.pids()
        bridge.proc.stdin.close()
        self.ended(bridge, pids)

    def test_the_end_of_input_during_a_call_ends_the_bridge_and_its_servers(self):
        bridge, pids = self.waiting()
        bridge.proc.stdin.close()
        self.ended(bridge, pids)

    @unittest.skipUnless(os.name == "posix", "signals that ask a process to stop are POSIX's")
    def test_a_signal_during_a_call_ends_the_bridge_and_its_servers(self):
        for number in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=number.name):
                self.entries = []
                for name in ("stub.log", "stub.pids"):
                    (self.dir / name).unlink(missing_ok=True)
                bridge, pids = self.waiting()
                os.kill(bridge.proc.pid, number)
                self.ended(bridge, pids)

    @unittest.skipUnless(os.name == "nt", "the job object is how Windows ends a server whose bridge was killed")
    def test_a_bridge_killed_outright_leaves_no_server(self):
        bridge, pids = self.waiting()
        bridge.proc.kill()   # no handler runs: the system closes the job's last handle
        bridge.proc.wait(timeout=15)
        for pid in pids:
            self.assertTrue(gone(pid), f"process {pid} outlived a bridge that was killed")

    def test_an_error_nobody_expected_ends_the_bridge_with_its_servers_closed(self):
        self.server(behaviour={"child": True})
        rel = self.file("a.py")
        bridge = self.in_process()

        def explode(tool, arguments):
            raise RuntimeError("a defect in a handler")

        bridge.position = explode
        lines = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "diagnostics", "arguments": {"file": rel}}}),
                 json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                             "params": {"name": "hover", "arguments": {"file": rel, "line": 1, "column": 1}}}),
                 json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"})]
        sink = io.BytesIO()
        held = threading.Event()
        self.addCleanup(held.set)

        def source():
            """The three messages, then an input that stays open, as an agent's does."""
            yield from (line.encode("utf-8") + b"\n" for line in lines)
            held.wait(60)

        with unittest.mock.patch.object(sys, "stderr", io.StringIO()) as errors:
            code = bridge_module.serve(bridge, source(), sink)
        self.assertEqual(code, 1)
        replies = [json.loads(line) for line in sink.getvalue().decode("utf-8").splitlines()]
        self.assertEqual([reply["id"] for reply in replies], [1, 2])   # nothing is answered after the error
        self.assertEqual(replies[1]["error"], {"code": -32603,
                                               "message": "Internal error: RuntimeError: a defect in a handler"})
        self.assertIn("stopped by an error", errors.getvalue())
        self.assertEqual(bridge.sessions, {})
        for pid in self.pids():
            self.assertTrue(gone(pid), f"process {pid} outlived the bridge")


if __name__ == "__main__":
    unittest.main()
