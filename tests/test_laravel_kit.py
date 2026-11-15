"""D04 T01 section 4: the Laravel kit on the LSP kit's client and table.

The kit brings the lsp kit with it, adds the `laravel` preset to the project's table, checks the servers through
the table, and carries a project from before the LSP kit onto the shared client with a client and a hook that
work together at every step.
"""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock

SDK_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK_ROOT))
import forge  # noqa: E402

TABLE = ".conclave/lsp.json"
CLIENT = "scripts/lsp-diagnostics.py"
HOOK = "scripts/hooks/laravel-lsp-pre-push.sh"
LSP_KIT = SDK_ROOT / "kits/lsp/templates"
LARAVEL_KIT = SDK_ROOT / "kits/laravel/templates"
PRESET = ("laravel-lsp", "intelephense", "tailwindcss")

# The client and the hook the Laravel kit shipped before this section (commit 5edd3ea), byte for byte: what a
# project installed then still has.
BEFORE = SDK_ROOT / "tests/fixtures/laravel-before-lsp"
OLD_CLIENT = (BEFORE / "lsp-diagnostics.py").read_bytes()
OLD_HOOK = (BEFORE / "laravel-lsp-pre-push.sh").read_bytes()

# A language server for the hook and the Blade tests: it publishes one diagnostic for each line holding `E:` and
# appends each opened document's language id to the file named by its first argument.
STUB_SERVER = r'''
import json, sys


def send(message):
    body = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    sys.stdout.buffer.flush()


while True:
    length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            sys.exit(0)
        line = line.strip()
        if not line:
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    message = json.loads(sys.stdin.buffer.read(length))
    method = message.get("method")
    if method in ("initialize", "shutdown"):
        send({"jsonrpc": "2.0", "id": message["id"], "result": {"capabilities": {}} if method == "initialize" else None})
    elif method == "textDocument/didOpen":
        document = message["params"]["textDocument"]
        with open(sys.argv[1], "a", encoding="utf-8") as log:
            log.write(document["languageId"] + "\n")
        found = [{"range": {"start": {"line": number, "character": 0}, "end": {"line": number, "character": 1}},
                  "severity": 1, "message": line.split("E:", 1)[1].strip()}
                 for number, line in enumerate(document["text"].splitlines()) if "E:" in line]
        send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
              "params": {"uri": document["uri"], "diagnostics": found}})
    elif method == "exit":
        sys.exit(0)
'''


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = pathlib.Path(tmp.name).resolve()
        self.table_module = forge._lsp_table_module()

    def project(self, name="project", app="."):
        folder = self.work / name
        (folder / app).mkdir(parents=True)
        (folder / app / "artisan").write_bytes(b"<?php\n")
        return folder

    def servers(self, project):
        return {server["name"]: server for server in self.table_module.load_servers(project)}

    def record(self, project):
        return json.loads((project / ".conclave/kits.json").read_text(encoding="utf-8"))

    def snapshot(self, folder):
        return {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*") if path.is_file()}

    def stub_server(self, name="stub-server"):
        """(the command of a stub language server, the file it logs language ids to)."""
        script = self.work / f"{name}.py"
        script.write_text(STUB_SERVER, encoding="utf-8")
        log = self.work / f"{name}.log"
        return [sys.executable, str(script), str(log)], log


class InstallTests(Fixture):
    def test_a_fresh_install_brings_the_lsp_kit_and_records_each_file_under_its_own_kit(self):
        project = self.project()
        result = forge.apply_kit(project, "laravel")
        self.assertNotIn(CLIENT, result["installed"])
        self.assertIn(CLIENT, result["lsp"]["installed"])
        self.assertEqual(result["lsp"]["preserved"], [])
        self.assertFalse((LARAVEL_KIT / CLIENT).exists(), "the Laravel kit still ships a client of its own")
        for rel in (CLIENT, "scripts/lib/lsp_client.py", "scripts/lib/lsp_table.py"):
            self.assertEqual((project / rel).read_bytes(), (LSP_KIT / rel).read_bytes(), rel)
        self.assertTrue((project / TABLE).is_file())
        kits = forge.check_repo(project)["kits"]
        self.assertIn("laravel", kits)
        self.assertIn("lsp", kits)
        record = self.record(project)
        self.assertEqual(sorted(record["kits"]), ["laravel", "lsp"])
        owners = {rel: entry["kit"] for rel, entry in record["files"].items()}
        self.assertEqual((owners[CLIENT], owners["scripts/lib/lsp_client.py"], owners[TABLE]), ("lsp", "lsp", "lsp"))
        self.assertEqual((owners[HOOK], owners["docs/laravel-agent-tooling.md"]), ("laravel", "laravel"))
        self.assertEqual(result["lsp_servers"], {"added": list(PRESET), "kept": [], "replaced": [], "differs": []})
        self.assertEqual(result["merge_needed"], [])

    def test_a_second_install_changes_nothing_and_a_dry_run_writes_nothing(self):
        dry = self.project("dry")
        before = self.snapshot(dry)
        result = forge.apply_kit(dry, "laravel", dry_run=True)
        self.assertEqual(self.snapshot(dry), before)
        self.assertIn(CLIENT, result["lsp"]["installed"])
        self.assertIn(TABLE, result["lsp"]["installed"])
        self.assertEqual(result["lsp_servers"], {"added": list(PRESET), "kept": [], "replaced": [], "differs": []})
        project = self.project()
        forge.apply_kit(project, "laravel")
        before = self.snapshot(project)
        again = forge.apply_kit(project, "laravel")
        self.assertEqual(self.snapshot(project), before)
        self.assertEqual((again["installed"], again["lsp"]["installed"]), ([], []))
        self.assertEqual(again["lsp_servers"], {"added": [], "kept": list(PRESET), "replaced": [], "differs": []})

    def test_one_agent_gets_that_agents_files_of_both_kits(self):
        project = self.project()
        result = forge.apply_kit(project, "laravel", agent="claude")
        self.assertTrue((project / ".claude/skills/laravel-boost/SKILL.md").is_file())
        self.assertFalse((project / ".codex").exists())
        self.assertIn(CLIENT, result["lsp"]["installed"])
        self.assertEqual(sorted(self.servers(project)), sorted(PRESET))


class TableTests(Fixture):
    def test_the_preset_is_rooted_at_the_folder_that_holds_artisan(self):
        for app in (".", "platform"):
            with self.subTest(app=app):
                project = self.project(f"app-{app.strip('.') or 'root'}", app)
                forge.apply_kit(project, "laravel")
                servers = self.servers(project)
                self.assertEqual(list(servers), list(PRESET))
                self.assertEqual({server["root"] for server in servers.values()}, {app})
                self.assertEqual(servers["laravel-lsp"]["requires"], "artisan")
                self.assertEqual(servers["tailwindcss"]["extensions"][".blade.php"], "blade")

    def test_the_lsp_kit_first_and_the_laravel_kit_second_give_the_same_table(self):
        fresh = self.project("fresh")
        forge.apply_kit(fresh, "laravel")
        project = self.project()
        forge.apply_kit(project, "lsp")
        self.assertEqual(self.servers(project), {})
        result = forge.apply_kit(project, "laravel")
        self.assertEqual(result["lsp_servers"]["added"], list(PRESET))
        self.assertEqual((project / TABLE).read_bytes(), (fresh / TABLE).read_bytes())
        # And the lsp kit installed again later (a table the project deleted) is filled for the Laravel kit too.
        (project / TABLE).unlink()
        result = forge.apply_kit(project, "lsp")
        self.assertEqual(result["lsp_servers"]["added"], list(PRESET))
        self.assertEqual((project / TABLE).read_bytes(), (fresh / TABLE).read_bytes())

    def web_project(self, name):
        project = self.project(name)
        (project / "composer.json").write_text("{}", encoding="utf-8")
        (project / "package.json").write_text("{}", encoding="utf-8")
        return project

    def test_the_web_kit_first_then_the_laravel_kit_ends_with_the_laravel_entries_and_blade_reaches_the_server(self):
        project = self.web_project("web-first")
        forge.apply_kit(project, "lsp")
        forge.apply_kit(project, "toolchain-web")
        before = self.servers(project)
        self.assertEqual(sorted(before), ["intelephense", "tailwindcss", "typescript"])
        self.assertNotIn(".blade.php", before["tailwindcss"]["extensions"])   # the web preset has no Blade
        result = forge.apply_kit(project, "laravel")
        self.assertEqual(result["lsp_servers"], {"added": ["laravel-lsp"], "kept": ["typescript"],
                                                 "replaced": ["intelephense", "tailwindcss"], "differs": []})
        self.assertEqual(result["merge_needed"], [])
        names = [entry["name"] for entry in json.loads((project / TABLE).read_text(encoding="utf-8"))["servers"]]
        self.assertEqual(sorted(names), ["intelephense", "laravel-lsp", "tailwindcss", "typescript"])   # each once
        fresh = self.project("fresh")
        forge.apply_kit(fresh, "laravel")
        servers, wanted = self.servers(project), self.servers(fresh)
        for name in ("tailwindcss", "intelephense"):
            self.assertEqual(servers[name], wanted[name], f"{name} is not the Laravel preset's entry")
        self.assertEqual(servers["tailwindcss"]["extensions"][".blade.php"], "blade")
        self.assertEqual(servers["tailwindcss"]["settings"]["tailwindCSS"]["includeLanguages"]["blade"], "html")
        self.assertEqual(servers["intelephense"]["init"]["storagePath"], "${scratch}")
        self.assertEqual(servers["typescript"], before["typescript"])

        # The effective entry at work: a Blade file reaches the server as `blade` and its diagnostic comes back.
        command, log = self.stub_server()
        document = json.loads((project / TABLE).read_text(encoding="utf-8"))
        for entry in document["servers"]:
            if entry["name"] == "tailwindcss":
                entry["command"] = command
                entry["settle"] = 1
        (project / TABLE).write_text(json.dumps(document), encoding="utf-8")
        (project / "resources/css").mkdir(parents=True)
        (project / "resources/css/app.css").write_text("@tailwind base;\n", encoding="utf-8")
        (project / "resources/views").mkdir(parents=True)
        (project / "resources/views/home.blade.php").write_text("<div>\nE: conflicting classes\n</div>\n",
                                                                encoding="utf-8")
        ran = subprocess.run([sys.executable, "-B", str(project / CLIENT), "--server", "tailwindcss",
                              "resources/views/home.blade.php", "--json"], capture_output=True, text=True, timeout=120,
                             cwd=self.work, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(ran.returncode, 1, ran.stderr)
        report = json.loads(ran.stdout)
        self.assertEqual([(row["file"], row["line"], row["message"]) for row in report["diagnostics"]],
                         [("resources/views/home.blade.php", 2, "conflicting classes")])
        self.assertEqual(log.read_text(encoding="utf-8").split(), ["blade"])

    def test_the_laravel_kit_first_then_the_web_kit_leaves_the_laravel_entries(self):
        project = self.web_project("laravel-first")
        forge.apply_kit(project, "laravel")
        before = self.servers(project)
        result = forge.apply_kit(project, "toolchain-web")
        self.assertEqual(result["lsp_servers"], {"added": ["typescript"], "kept": list(PRESET), "replaced": [],
                                                 "differs": []})
        after = self.servers(project)
        for name in PRESET:
            self.assertEqual(after[name], before[name])
        # Either order ends with the same servers.
        other = self.web_project("web-first")
        forge.apply_kit(other, "lsp")
        forge.apply_kit(other, "toolchain-web")
        forge.apply_kit(other, "laravel")
        self.assertEqual(self.servers(other), after)

    def test_an_entry_the_project_changed_is_kept_and_listed_under_differs(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        own = {"name": "intelephense", "command": ["intelephense", "--stdio"], "extensions": {".php": "php"},
               "install": "npm install -g intelephense", "severity": "warning", "note": "the project's own"}
        (project / TABLE).write_text(json.dumps({"schema_version": 1, "servers": [own]}), encoding="utf-8")
        result = forge.apply_kit(project, "laravel")
        self.assertEqual(result["lsp_servers"], {"added": ["laravel-lsp", "tailwindcss"], "kept": ["intelephense"],
                                                 "replaced": [], "differs": ["intelephense"]})
        stored = json.loads((project / TABLE).read_text(encoding="utf-8"))["servers"]
        self.assertEqual(stored[0], own)
        self.assertEqual([entry["name"] for entry in stored], ["intelephense", "laravel-lsp", "tailwindcss"])
        # The same entry rooted elsewhere, or with one key changed, is the project's too.
        for change in ({"root": "api"}, {"settle": 9}):
            with self.subTest(change=change):
                other = self.web_project("changed-" + next(iter(change)))
                (other / "api").mkdir()
                forge.apply_kit(other, "lsp")
                forge.apply_kit(other, "toolchain-web")
                document = json.loads((other / TABLE).read_text(encoding="utf-8"))
                for entry in document["servers"]:
                    if entry["name"] == "tailwindcss":
                        entry.update(change)
                (other / TABLE).write_text(json.dumps(document), encoding="utf-8")
                kept = self.servers(other)["tailwindcss"]
                result = forge.apply_kit(other, "laravel")
                self.assertEqual((result["lsp_servers"]["replaced"], result["lsp_servers"]["differs"]),
                                 (["intelephense"], ["tailwindcss"]))
                self.assertEqual(self.servers(other)["tailwindcss"], kept)

    def test_a_table_that_does_not_load_is_reported_and_left_as_it_was(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        (project / TABLE).write_text('{"schema_version": 1, "servers": [{"name": "x"}]}', encoding="utf-8")
        before = (project / TABLE).read_bytes()
        result = forge.apply_kit(project, "laravel")
        self.assertIn("server 'x': missing key", result["lsp_servers"]["refused"])
        self.assertEqual(result["merge_needed"], [TABLE])
        self.assertEqual((project / TABLE).read_bytes(), before)

    def test_a_write_that_fails_leaves_the_table_as_it_was_and_the_retry_succeeds(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        before = (project / TABLE).read_bytes()

        def replace(*args, **kwargs):
            raise PermissionError(13, "Permission denied")

        # Only the table module's own replacement fails: forge's record is written through the real one.
        failing = types.SimpleNamespace(**{name: getattr(os, name) for name in dir(os) if not name.startswith("__")})
        failing.replace = replace
        module = forge._lsp_table_module()
        module.os = failing
        with unittest.mock.patch.object(forge, "_lsp_table_module", lambda: module):
            result = forge.apply_kit(project, "laravel")
        self.assertEqual(result["lsp_servers"], {
            "failed": f"{TABLE}: cannot be written (Permission denied)",
            "retry": f"python forge.py kit {project.as_posix()} laravel"})
        self.assertEqual(result["merge_needed"], [TABLE])
        self.assertEqual((project / TABLE).read_bytes(), before)
        self.assertEqual([path.name for path in (project / ".conclave").iterdir() if path.name.endswith(".tmp")], [])
        again = forge.apply_kit(project, "laravel")
        self.assertEqual((again["lsp_servers"]["added"], again["merge_needed"]), (list(PRESET), []))
        self.assertEqual(sorted(self.servers(project)), sorted(PRESET))


class DoctorTests(Fixture):
    def setUp(self):
        super().setUp()
        self.bin = self.work / "bin"
        self.bin.mkdir()
        env = {"PATH": str(self.bin), **({"PATHEXT": ".CMD;.EXE"} if os.name == "nt" else {})}
        patch = unittest.mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)

    def program(self, name):
        if os.name == "nt":
            path = self.bin / f"{name}.cmd"
            path.write_text("@exit /b 0\r\n", encoding="utf-8")
        else:
            path = self.bin / name
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        return path

    def test_the_servers_are_checked_through_the_table_once_in_the_named_and_the_bare_form(self):
        project = self.project()
        forge.apply_kit(project, "laravel")
        found = self.program("laravel-lsp")
        for report in (forge.doctor_repo(project, "laravel"), forge.doctor_repo(project)):
            self.assertEqual(report["kit"], "laravel")
            self.assertNotIn("also", report)
            names = [check["name"] for check in report["checks"]]
            checks = {check["name"]: check for check in report["checks"]}
            for name in ("artisan", "server-table", CLIENT, TABLE, *[f"server:{server}" for server in PRESET]):
                self.assertEqual(names.count(name), 1, name)
            self.assertEqual(checks["server-table"]["detail"], f"{TABLE}: {', '.join(PRESET)}")
            self.assertEqual(checks["server:laravel-lsp"]["status"], "ok")
            self.assertTrue(os.path.samefile(checks["server:laravel-lsp"]["detail"], found))
            self.assertEqual(checks["server:tailwindcss"],
                             {"name": "server:tailwindcss", "status": "setup_required",
                              "detail": self.servers(project)["tailwindcss"]["install"]})
            self.assertEqual(checks["server:intelephense"]["status"], "setup_required")
            # No check is named after a binary any more, and none after the client's old name.
            for old in ("laravel-lsp", "tailwindcss-language-server", "intelephense", "lsp-diagnostics.py"):
                self.assertNotIn(old, names)

    def test_a_project_without_the_lsp_kit_is_told_what_is_missing(self):
        project = self.project()
        forge.apply_kit(project, "laravel")
        (project / TABLE).unlink()
        (project / CLIENT).unlink()
        checks = {check["name"]: check for check in forge.doctor_repo(project, "laravel")["checks"]}
        self.assertEqual((checks[CLIENT]["status"], checks[TABLE]["status"]), ("missing", "missing"))
        self.assertEqual(checks["server-table"]["status"], "missing")


class DocumentTests(unittest.TestCase):
    def test_the_hook_and_the_documents_name_only_servers_the_table_names(self):
        table = forge._lsp_table_module()
        preset = {entry["name"] for entry in table.resolve_preset(SDK_ROOT, "laravel", ".")}
        self.assertEqual(preset, set(PRESET))
        hook = (LARAVEL_KIT / HOOK).read_text(encoding="utf-8")
        new, old = re.findall(r"servers=\((.*)\)", hook)
        self.assertEqual(re.findall(r"--server (\S+)", new), ["laravel-lsp", "tailwindcss"])
        self.assertEqual(re.findall(r"--server (\S+)", old), ["laravel", "tailwind"])   # for a client from before
        self.assertLess(hook.index("grep -q 'lsp_client'"), hook.index(new))
        self.assertIn("SKIPPED", hook)
        documents = [LARAVEL_KIT / "docs/laravel-agent-tooling.md", SDK_ROOT / "kits/laravel/README.md",
                     *[LARAVEL_KIT / agent / "skills/laravel-boost/SKILL.md"
                       for agent in (".agents", ".claude", ".codex")]]
        named = 0
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for server in re.findall(r"--server ([a-z0-9-]+)", text):
                named += 1
                self.assertIn(server, preset, f"{document.name} names a server the table does not hold")
            self.assertIn(TABLE, text, f"{document.name} does not name the table")
        self.assertGreater(named, 4)
        tooling = documents[0].read_text(encoding="utf-8")
        for server in PRESET:
            self.assertIn(f"`server:{server}`", tooling)
        readme = documents[1].read_text(encoding="utf-8")
        for word in ("`added`", "`replaced`", "`kept`", "`differs`", "`project-only`", "`kit-newer`", "--kit-new",
                     "`lsp_client`"):
            self.assertIn(word, readme)
        self.assertNotIn(f"| `{CLIENT}` |", readme)   # no longer one of the kit's own files


class Migration(Fixture):
    """A Laravel project installed before the LSP kit: the client and the hook of that time, the Laravel kit's
    record, and nothing of the lsp kit."""

    def old_project(self, name="old"):
        project = self.project(name)
        forge.apply_kit(project, "laravel")
        # Back to what that install left: no file and no record of the lsp kit, and the retired client and hook,
        # recorded as the Laravel kit's with the digests of those bytes.
        record = self.record(project)
        for rel in [rel for rel, entry in record["files"].items() if entry["kit"] == "lsp"]:
            (project / rel).unlink()
            del record["files"][rel]
        del record["kits"]["lsp"]
        (project / CLIENT).write_bytes(OLD_CLIENT)
        (project / HOOK).write_bytes(OLD_HOOK)
        record["files"][HOOK]["sha256"] = forge.file_digest(OLD_HOOK)
        record["files"][CLIENT] = dict(record["files"][HOOK], sha256=forge.file_digest(OLD_CLIENT))
        (project / ".conclave/kits.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        kits = forge.check_repo(project)["kits"]
        self.assertIn("laravel", kits)
        self.assertNotIn("lsp", kits)
        return project

    def migrated(self, name="old"):
        """An old project after `forge.py kit <project> laravel`: the lsp kit beside the old client and hook."""
        project = self.old_project(name)
        result = forge.apply_kit(project, "laravel")
        self.assertIn(CLIENT, result["lsp"]["preserved"])
        self.assertIn(TABLE, result["lsp"]["installed"])
        self.assertIn(HOOK, result["preserved"])
        return project

    def left(self, result):
        """What an update left, by path, without what every Laravel project has there: the table the install
        filled (the project's from then on), the generated .mcp.json, and the retired client under `laravel`."""
        usual = {(TABLE, "project-changed"), (".mcp.json", "generated"), (CLIENT, "project-only")}
        return {item["path"]: item for item in result["left"] if (item["path"], item["state"]) not in usual}

    def states(self, project, kit):
        return {item["path"]: item["state"] for item in forge.diff_project(project, kit)["kits"][kit]["files"]}


class MigrationTests(Migration):
    def test_the_fixtures_are_the_retired_files(self):
        # The client and the hook the Laravel kit shipped until this section (commit 5edd3ea), byte for byte: their
        # git blob ids.
        def blob(data):
            return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()

        self.assertEqual(blob(OLD_CLIENT), "0092efff2cdb21773da313c09d4b780d2f4487d3")
        self.assertEqual(blob(OLD_HOOK), "d521590f90de4776e084263850ce407a596c8f2e")
        self.assertNotIn(b"lsp_client", OLD_CLIENT)
        self.assertIn(b'choices=tuple(SERVERS)', OLD_CLIENT)

    def test_bringing_the_lsp_kit_keeps_the_old_client_and_hook_and_fills_the_table(self):
        project = self.old_project()
        result = forge.apply_kit(project, "laravel")
        self.assertEqual(result["installed"], [])
        self.assertIn(HOOK, result["preserved"])
        self.assertEqual(result["lsp"]["preserved"], [CLIENT])
        for rel in (TABLE, "scripts/lib/lsp_client.py", "scripts/lib/lsp_table.py", "scripts/lsp-servers.py"):
            self.assertIn(rel, result["lsp"]["installed"])
        self.assertEqual(result["lsp_servers"]["added"], list(PRESET))
        self.assertEqual(((project / CLIENT).read_bytes(), (project / HOOK).read_bytes()), (OLD_CLIENT, OLD_HOOK))
        # The retired client is the Laravel kit's no longer, and the lsp kit's version of that file is newer.
        self.assertEqual(self.states(project, "laravel")[CLIENT], "project-only")
        self.assertEqual(self.states(project, "laravel")[HOOK], "kit-newer")
        self.assertEqual(self.states(project, "lsp")[CLIENT], "kit-newer")

    def test_update_replaces_an_unchanged_pair_hook_first(self):
        project = self.migrated()
        order = []
        real = forge._write_recorded

        def recording(target, record, kit, *args, **kwargs):
            order.append(kit)
            return real(target, record, kit, *args, **kwargs)

        with unittest.mock.patch.object(forge, "_write_recorded", recording):
            result = forge.update_project(project)
        self.assertLess(order.index("laravel"), order.index("lsp"), "the client was replaced before the hook")
        self.assertEqual(sorted(result["written"]), [HOOK, CLIENT])
        self.assertEqual(self.left(result), {})
        self.assertEqual((project / CLIENT).read_bytes(), (LSP_KIT / CLIENT).read_bytes())
        self.assertEqual((project / HOOK).read_bytes(), (LARAVEL_KIT / HOOK).read_bytes())
        self.assertEqual(self.record(project)["files"][CLIENT]["kit"], "lsp")
        self.assertEqual(self.states(project, "lsp")[CLIENT], "identical")
        # A dry run of the same update names both and writes neither.
        other = self.migrated("dry")
        before = self.snapshot(other)
        self.assertEqual(sorted(forge.update_project(other, dry_run=True)["written"]), [HOOK, CLIENT])
        self.assertEqual(self.snapshot(other), before)

    def test_an_update_stopped_between_the_two_leaves_a_pair_that_works_together(self):
        # Found by the review round: with the client replaced first, a stop there left the old hook calling a
        # client that refuses its names.
        project = self.migrated()
        real = forge._write_recorded

        def stopped(target, record, kit, *args, **kwargs):
            if kit == "lsp":
                raise OSError(28, "No space left on device")
            return real(target, record, kit, *args, **kwargs)

        with unittest.mock.patch.object(forge, "_write_recorded", stopped):
            with self.assertRaises(OSError):
                forge.update_project(project)
        # The new hook, which serves either client, beside the old client.
        self.assertEqual((project / HOOK).read_bytes(), (LARAVEL_KIT / HOOK).read_bytes())
        self.assertEqual((project / CLIENT).read_bytes(), OLD_CLIENT)
        result = forge.update_project(project)
        self.assertEqual(result["written"], [CLIENT])
        self.assertEqual((project / CLIENT).read_bytes(), (LSP_KIT / CLIENT).read_bytes())

    def test_a_changed_client_is_left_for_a_merge_beside_the_new_hook(self):
        project = self.migrated()
        changed = OLD_CLIENT + b"# the project's own change\n"
        (project / CLIENT).write_bytes(changed)
        result = forge.update_project(project)
        self.assertEqual(result["written"], [HOOK])
        self.assertEqual({path: item["state"] for path, item in self.left(result).items()}, {CLIENT: "both-changed"})
        self.assertEqual((project / CLIENT).read_bytes(), changed)
        self.assertEqual((project / HOOK).read_bytes(), (LARAVEL_KIT / HOOK).read_bytes())
        # The merge copy comes from `update --kit-new`.
        self.assertFalse((project / (CLIENT + ".kit-new")).exists())
        result = forge.update_project(project, kit_new=True)
        self.assertEqual(result["kit_new"], [CLIENT + ".kit-new"])
        self.assertEqual((project / (CLIENT + ".kit-new")).read_bytes(), (LSP_KIT / CLIENT).read_bytes())

    def test_a_changed_hook_holds_the_client_back_until_the_hook_is_merged(self):
        project = self.migrated()
        (project / HOOK).write_bytes(OLD_HOOK + b"# the project's own change\n")
        result = forge.update_project(project)
        self.assertEqual(result["written"], [])
        left = self.left(result)
        self.assertEqual(left[HOOK]["state"], "both-changed")
        self.assertEqual((left[CLIENT]["state"], left[CLIENT]["hint"]), ("kit-newer", forge.UPDATE_HINT_HELD))
        self.assertIn("--kit-new", forge.UPDATE_HINT_HELD)
        self.assertEqual((project / CLIENT).read_bytes(), OLD_CLIENT, "the client was replaced under a hook that "
                                                                      "still passes the old names")
        # A dry run and a run for the lsp kit alone say the same and write nothing.
        dry = forge.update_project(project, dry_run=True)
        self.assertEqual((dry["written"], self.left(dry)[CLIENT]["hint"]), ([], forge.UPDATE_HINT_HELD))
        alone = forge.update_project(project, "lsp")
        self.assertEqual((alone["written"], self.left(alone)[CLIENT]["hint"]), ([], forge.UPDATE_HINT_HELD))
        # Merged: the project's hook now passes the table's names (here, the kit's own bytes). The client follows.
        (project / HOOK).write_bytes((LARAVEL_KIT / HOOK).read_bytes())
        result = forge.update_project(project)
        self.assertEqual(result["written"], [CLIENT])
        self.assertEqual((project / CLIENT).read_bytes(), (LSP_KIT / CLIENT).read_bytes())

    def test_every_way_a_hook_passes_the_old_names_holds_the_client(self):
        # Found by the review round: `--server=laravel` and a quoted name work with the old client as well.
        call = b'python3 "$client" --server laravel --server tailwind --staged'
        self.assertEqual(OLD_HOOK.count(call), 1)
        forms = (b'python3 "$client" --server=laravel --server=tailwind --staged',
                 b'python3 "$client" --server "laravel" --server "tailwind" --staged',
                 b"python3 \"$client\" --server 'laravel' --staged",
                 b'python3 "$client" --staged --server tailwind',
                 b'python3 "$client" --server php "$@"')
        for number, form in enumerate(forms):
            with self.subTest(form=form):
                project = self.migrated(f"form-{number}")
                (project / HOOK).write_bytes(OLD_HOOK.replace(call, form))
                result = forge.update_project(project)
                self.assertEqual(result["written"], [])
                self.assertEqual(self.left(result)[CLIENT]["hint"], forge.UPDATE_HINT_HELD)
                self.assertEqual((project / CLIENT).read_bytes(), OLD_CLIENT)

    def test_a_hook_that_passes_the_tables_names_holds_nothing(self):
        for number, extra in enumerate((b"# the project's own line\n", b'echo "checked"\n')):
            project = self.migrated(f"own-{number}")
            (project / HOOK).write_bytes((LARAVEL_KIT / HOOK).read_bytes() + extra)
            self.assertEqual(forge.update_project(project)["written"], [CLIENT])
        # A hook with no server name at all (the project calls the client elsewhere) holds nothing either.
        bare = self.migrated("bare")
        (bare / HOOK).write_bytes(b"#!/bin/sh\nexit 0\n")
        self.assertEqual(forge.update_project(bare)["written"], [CLIENT])
        # Outside the selection the hook is not replaced in this run, so the old one holds the client back.
        other = self.migrated("selected")
        result = forge.update_project(other, only=[CLIENT])
        self.assertEqual(result["written"], [])
        self.assertEqual({path: item.get("hint") for path, item in self.left(result).items()},
                         {CLIENT: forge.UPDATE_HINT_HELD})
        self.assertEqual(sorted(forge.update_project(other)["written"]), [HOOK, CLIENT])


@unittest.skipUnless(os.name == "posix" and shutil.which("bash") and shutil.which("git") and shutil.which("python3"),
                     "the hook is a shell script that calls python3")
class HookRunTests(Migration):
    """The installed hook, run: with the LSP kit's client and stub servers, and with the retired client in each
    state a migration passes through."""

    def repository(self, project):
        """A git repository in the project, and an environment whose PATH starts with a folder of stub programs."""
        self.bin = self.work / "bin"
        self.bin.mkdir(exist_ok=True)
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                   PATH=str(self.bin) + os.pathsep + os.environ["PATH"])
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
            subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True, env=env)
        return env

    def stage(self, project, env, name, text):
        (project / name).write_text(text, encoding="utf-8")
        subprocess.run(["git", "-C", str(project), "add", name], check=True, capture_output=True, env=env)

    def push(self, project, env):
        ran = subprocess.run(["bash", str(project / HOOK)], cwd=project, capture_output=True, text=True, timeout=180,
                             env=env)
        return ran.returncode, ran.stdout, ran.stderr

    def stub_table(self, project, command=None):
        """The table with the hook's two servers as stubs (or as programs that are not installed)."""
        servers = [{"name": name, "command": command or [f"no-such-{name}-anywhere"], "extensions": {".php": "php"},
                    "install": f"install {name}", "settle": 1} for name in ("laravel-lsp", "tailwindcss")]
        (project / TABLE).write_text(json.dumps({"schema_version": 1, "servers": servers}), encoding="utf-8")

    def laravel_lsp_on_path(self):
        """A stub language server on PATH under the name the retired client starts: `laravel-lsp`."""
        command, log = self.stub_server("old-laravel-lsp")
        program = self.bin / "laravel-lsp"
        program.write_text("#!/bin/sh\nexec " + " ".join(f'"{part}"' for part in command) + ' "$@"\n', encoding="utf-8")
        program.chmod(0o755)
        return log

    def test_the_hook_runs_the_tables_two_servers_on_the_staged_files(self):
        project = self.project()
        forge.apply_kit(project, "laravel")
        env = self.repository(project)
        command, log = self.stub_server()
        self.stub_table(project, command)
        self.stage(project, env, "clean.php", "<?php\n")
        code, out, err = self.push(project, env)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(log.read_text(encoding="utf-8").split(), ["php", "php"])   # both servers were asked
        self.stage(project, env, "broken.php", "<?php\nE: undefined route\n")
        code, out, err = self.push(project, env)
        self.assertEqual(code, 1, out + err)
        self.assertIn("broken.php:2:1  error       undefined route", out)
        # Neither server installed: a skip that says so, never a pass in silence.
        self.stub_table(project)
        code, out, err = self.push(project, env)
        self.assertEqual(code, 0)
        self.assertIn("laravel-lsp-pre-push: SKIPPED (language servers not installed)", err)

    def test_the_retired_pair_goes_on_working_after_the_lsp_kit_is_brought(self):
        project = self.migrated()
        env = self.repository(project)
        log = self.laravel_lsp_on_path()
        self.stage(project, env, "routes.php", "<?php\nE: Route [home] not found\n")
        code, out, err = self.push(project, env)
        self.assertEqual(code, 1, out + err)
        self.assertIn("Route [home] not found", out)
        self.assertEqual(log.read_text(encoding="utf-8").split(), ["php"])

    def test_the_new_hook_beside_a_changed_old_client_is_a_working_check(self):
        project = self.migrated()
        env = self.repository(project)
        log = self.laravel_lsp_on_path()
        (project / CLIENT).write_bytes(OLD_CLIENT + b"# the project's own change\n")
        forge.update_project(project)
        self.assertEqual((project / HOOK).read_bytes(), (LARAVEL_KIT / HOOK).read_bytes())
        self.stage(project, env, "routes.php", "<?php\nE: Route [home] not found\n")
        code, out, err = self.push(project, env)
        self.assertEqual(code, 1, out + err)   # the old client's diagnostic, not its refusal of a name (2)
        self.assertIn("Route [home] not found", out)
        self.assertEqual(log.read_text(encoding="utf-8").split(), ["php"])

    def test_a_changed_old_hook_goes_on_working_with_the_client_held_back(self):
        project = self.migrated()
        env = self.repository(project)
        self.laravel_lsp_on_path()
        (project / HOOK).write_bytes(OLD_HOOK + b"# the project's own change\n")
        forge.update_project(project)
        self.stage(project, env, "routes.php", "<?php\nE: Route [home] not found\n")
        code, out, err = self.push(project, env)
        self.assertEqual(code, 1, out + err)
        self.assertIn("Route [home] not found", out)
        # Had the client been replaced under it, the hook would have ended as a refusal.
        (project / CLIENT).write_bytes((LSP_KIT / CLIENT).read_bytes())
        code, out, err = self.push(project, env)
        self.assertEqual(code, 2)
        self.assertIn("no server named 'laravel'", err)


if __name__ == "__main__":
    unittest.main()
