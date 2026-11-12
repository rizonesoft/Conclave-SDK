"""The run guard steps in the Antigravity and Codex copies of process-plan, walked through: each copy's documented
commands are extracted, filled in and run in order against a scratch todo-kit workspace, so a step that is missing,
out of order or short of an argument fails here, not in an unattended run."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = REPO / "kits" / "todo" / "templates"
SESSION = "a6396662-d187-46c4-b3f8-f666a13f38dc"
OTHER = "99999999-8888-7777-6666-555555555555"
COPIES = {".agents": "ANTIGRAVITY_CONVERSATION_ID", ".codex": "CODEX_THREAD_ID"}
FAKE_GRAPH = "import json\nprint(json.dumps([{'ref': 'D00 T01 \\u00a71', 'title': 'Walkthrough row', 'phase': 0}]))\n"


def guard_section(agent):
    text = (TEMPLATES / agent / "skills" / "process-plan" / "SKILL.md").read_text(encoding="utf-8")
    return text.split("### Run guard", 1)[1].split("\n## ", 1)[0]


def commands(agent, part):
    """The campaign_guard commands of one `#### <part>` subsection, in order, from its fenced `sh` blocks."""
    body = guard_section(agent).split(f"#### {part}", 1)[1].split("\n#### ", 1)[0]
    blocks = re.findall(r"```sh\n(.*?)```", body, re.S)
    return [line.strip() for block in blocks for line in block.splitlines()
            if line.strip().startswith("python scripts/campaign_guard.py")]


def heartbeat_commands(agent):
    body = guard_section(agent).split("#### Heartbeat", 1)[1]
    return re.findall(r"`(python scripts/campaign_guard\.py [^`]+)`", body)


class Walkthrough(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "ws"
        (self.ws / "scripts").mkdir(parents=True)
        shutil.copyfile(TEMPLATES / "scripts" / "campaign_guard.py", self.ws / "scripts" / "campaign_guard.py")
        (self.ws / "scripts" / "todo-graph.py").write_text(FAKE_GRAPH, encoding="utf-8")
        (self.ws / "docs" / "phase-runs").mkdir(parents=True)
        for n in (1, 2):
            (self.ws / f"docs/phase-runs/2099-01-01-phase-{n}.md").write_text(f"# Phase run {n}\n", encoding="utf-8")
        (self.ws / ".gitignore").write_text("build/\n", encoding="utf-8")
        for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                     ["config", "commit.gpgsign", "false"], ["add", "-A"], ["commit", "-qm", "seed"]):
            subprocess.run(["git", *args], cwd=self.ws, capture_output=True, check=True)

    def fill(self, command, variable, session=SESSION, **values):
        for placeholder, value in values.items():
            command = command.replace(f"<{placeholder.replace('_', ' ')}>", value)
        command = command.replace(f'"${variable}"', session)
        self.assertNotRegex(command, r"<[a-z ]+>|\$[A-Z_]", f"an unfilled placeholder in {command}")
        return command

    def run_guard(self, command):
        args = command.split()[2:]  # after `python scripts/campaign_guard.py`
        args = args[:1] + ["--root", str(self.ws)] + args[1:] if args[0] not in ("--self-test",) else args
        proc = subprocess.run([sys.executable, str(self.ws / "scripts" / "campaign_guard.py"), *args],
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, (proc.stdout + proc.stderr).strip()

    def start(self, agent, variable, phase="1", run_file="docs/phase-runs/2099-01-01-phase-1.md", session=SESSION):
        steps = commands(agent, "Startup")
        self.assertTrue(steps[0].startswith("python scripts/campaign_guard.py whoami"), "no ownership check first")
        self.assertIn("python scripts/campaign_guard.py mint-generation", steps)
        acquire = next(s for s in steps if " acquire " in s)
        for flag in ("--session", "--phase", "--run-file", "--cron-id", "--generation", "--scope"):
            self.assertIn(flag, acquire, f"{agent} acquire lacks {flag}")
        generation, outputs = None, []
        for step in steps:
            if step.endswith("mint-generation"):
                code, generation = self.run_guard(step)
                self.assertEqual(code, 0)
                continue
            code, out = self.run_guard(self.fill(step, variable, session, N=phase, run_file=run_file,
                                                 generation=generation or "", timer_id="timer-1"))
            outputs.append((step, code, out))
        return generation, outputs

    def test_each_copy_starts_reads_back_and_refuses_a_second_session(self):
        for agent, variable in COPIES.items():
            with self.subTest(agent):
                shutil.rmtree(self.ws / "build", ignore_errors=True)
                generation, outputs = self.start(agent, variable)
                self.assertEqual(outputs[0][2], "NO GUARD")
                self.assertTrue(outputs[1][2].startswith("acquire: guard created"), outputs)
                self.assertTrue(outputs[-1][2].startswith("OWNER run="), outputs)
                guard = json.loads((self.ws / "build/claude-campaign-guard.json").read_text(encoding="utf-8"))
                self.assertEqual((guard["session_id"], guard["generation"]), (SESSION, generation))
                _gen, other = self.start(agent, variable, session=OTHER)
                self.assertEqual(other[0][2], "NOT THE OWNER", "the ownership check let another session through")
                self.assertNotEqual(other[1][1], 0, "a second session acquired the guard")

    def test_a_phase_change_re_points_the_guard(self):
        for agent, variable in COPIES.items():
            with self.subTest(agent):
                shutil.rmtree(self.ws / "build", ignore_errors=True)
                self.start(agent, variable)
                generation = None
                for step in commands(agent, "Phase change"):
                    if step.endswith("mint-generation"):
                        generation = self.run_guard(step)[1]
                        continue
                    code, out = self.run_guard(self.fill(step, variable, N="2", run_file="docs/phase-runs/2099-01-01-phase-2.md",
                                                         generation=generation or "", timer_id="timer-2"))
                    self.assertEqual(code, 0, out)
                guard = json.loads((self.ws / "build/claude-campaign-guard.json").read_text(encoding="utf-8"))
                self.assertEqual((guard["phase"], guard["run_file"], guard["generation"]),
                                 (2, "docs/phase-runs/2099-01-01-phase-2.md", generation))

    def test_every_end_path_leaves_no_guard_or_state(self):
        for agent, variable in COPIES.items():
            for reason in ("operator-stop", "closeout", "park"):
                with self.subTest(agent=agent, reason=reason):
                    shutil.rmtree(self.ws / "build", ignore_errors=True)
                    self.start(agent, variable)
                    run_id = json.loads((self.ws / "build/claude-campaign-guard.json").read_text(encoding="utf-8"))["run_id"]
                    run_file = self.ws / "docs/phase-runs/2099-01-01-phase-1.md"
                    run_file.write_text("# Phase run 1\n", encoding="utf-8")
                    if reason == "closeout":
                        run_file.write_text(f"# Phase run 1\n\n## Closeout run={run_id}\n", encoding="utf-8")
                    if reason == "park":
                        run_file.write_text(f"# Phase run 1\n\nPARKED 2099-01-01T00:00:00Z run={run_id} blocked\n", encoding="utf-8")
                    steps = commands(agent, "End")
                    self.assertTrue(any("cancel-confirmed" in s for s in steps), "no cancellation confirmed")
                    outs = [self.run_guard(self.fill(s, variable, reason=reason,
                                                     timer_id="timer-1" if agent == ".agents" else "none")) for s in steps]
                    self.assertTrue(all(code == 0 for code, _ in outs), outs)
                    self.assertEqual(outs[-1][1], "NO GUARD")
                    self.assertFalse((self.ws / "build/claude-campaign-guard.json").exists())
                    self.assertFalse((self.ws / "build/claude-campaign-state.json").exists())

    def test_the_antigravity_no_timer_branch_acquires_and_releases_with_none(self):
        body = guard_section(".agents").split("#### Startup", 1)[1].split("\n#### ", 1)[0]
        fallback = [line.strip() for block in re.findall(r"```bash\n(.*?)```", body, re.S)
                    for line in block.splitlines() if line.strip().startswith("python scripts/campaign_guard.py")]
        self.assertEqual([line.split()[2] for line in fallback], ["acquire", "end", "cancel-confirmed"])
        code, generation = self.run_guard("python scripts/campaign_guard.py mint-generation")
        variable = COPIES[".agents"]
        outs = [self.run_guard(self.fill(line, variable, N="1", run_file="docs/phase-runs/2099-01-01-phase-1.md",
                                         generation=generation, reason="operator-stop")) for line in fallback]
        self.assertTrue(all(c == 0 for c, _ in outs), outs)
        self.assertIn("job none", outs[0][1])
        self.assertFalse((self.ws / "build/claude-campaign-guard.json").exists())
        pending = self.ws / "build/claude-campaign-pending-cancel.json"
        self.assertFalse(pending.exists() and json.loads(pending.read_text(encoding="utf-8")), "a cancellation was left")

    def heartbeat_steps(self):
        """The heartbeat prompt's numbered steps, each with the campaign_guard commands it names, in order."""
        prompt = guard_section(".agents").split("#### Heartbeat", 1)[1].split("```text", 1)[1].split("```", 1)[0]
        steps = re.findall(r"(?m)^(\d+)\. (.*)$", prompt)
        return [(int(n), re.findall(r"`(python scripts/campaign_guard\.py [^`]+)`", text), text) for n, text in steps]

    def run_heartbeat(self, generation):
        """Walk the prompt as the agent would: step 1's answer chooses the branch; returns the commands run."""
        variable, ran = COPIES[".agents"], []
        steps = self.heartbeat_steps()
        first_number, first_commands, _ = steps[0]
        self.assertEqual(first_number, 1)
        self.assertTrue(first_commands[0].split()[2] == "whoami", "the heartbeat does not check ownership first")
        answer = self.run_guard(self.fill(first_commands[0], variable, generation=generation))[1]
        ran.append(("whoami", answer))
        if answer in ("NOT THE OWNER", "NOT THE CURRENT JOB"):
            return ran  # the prompt: cancel this timer, change nothing else
        for number, found, text in steps[1:]:
            for command in found:
                name = command.split()[2]
                if name == "reset-state" and answer != "NO GUARD":
                    continue  # step 4 is for a released run only
                if name in ("heartbeat-still",) and answer == "NO GUARD":
                    continue  # a released run stops at step 4
                if name == "cancel-confirmed":
                    continue  # needs a timer the pending-cancel step named
                if "--ack" in command:
                    continue  # only after hook-error printed a line
                code, out = self.run_guard(self.fill(command, variable, generation=generation))
                ran.append((name, out))
        return ran

    def test_the_heartbeat_steps_run_in_order_for_an_owner_a_stale_timer_and_a_released_run(self):
        generation, _ = self.start(".agents", COPIES[".agents"])
        state = self.ws / "build/claude-campaign-state.json"
        ran = self.run_heartbeat(generation)
        self.assertEqual([name for name, _ in ran], ["whoami", "hook-error", "pending-cancel", "heartbeat-still"])
        self.assertIn("progress", ran[-1][1])
        before = state.read_bytes()
        stale = self.run_heartbeat("0" * 12)
        self.assertEqual(stale, [("whoami", "NOT THE CURRENT JOB")], "a stale timer went past the ownership check")
        self.assertEqual(state.read_bytes(), before, "a stale timer wrote the run's state")
        self.run_guard(self.fill(commands(".agents", "End")[0], COPIES[".agents"], reason="operator-stop"))
        released = self.run_heartbeat(generation)
        self.assertEqual([name for name, _ in released], ["whoami", "hook-error", "pending-cancel", "reset-state"])
        self.assertEqual(released[0][1], "NO GUARD")

    def test_the_antigravity_heartbeat_prompt_runs_for_an_owner_a_stale_timer_and_a_released_run(self):
        steps = heartbeat_commands(".agents")
        for needed in ("whoami", "hook-error", "pending-cancel", "reset-state", "heartbeat-still"):
            self.assertTrue(any(f"campaign_guard.py {needed}" in s for s in steps), f"the heartbeat lacks {needed}")
        whoami = next(s for s in steps if " whoami " in s)
        still = next(s for s in steps if " heartbeat-still " in s)
        generation, _ = self.start(".agents", COPIES[".agents"])
        fill = lambda s, g: self.fill(s, COPIES[".agents"], generation=g)
        self.assertTrue(self.run_guard(fill(whoami, generation))[1].startswith("OWNER run="))
        self.assertEqual(self.run_guard(fill(whoami, "0" * 12))[1], "NOT THE CURRENT JOB")
        self.assertIn("progress", self.run_guard(fill(still, generation))[1])
        self.assertIn("still 1 of", self.run_guard(fill(still, generation))[1])
        self.run_guard(self.fill(commands(".agents", "End")[0], COPIES[".agents"], reason="operator-stop"))
        self.assertEqual(self.run_guard(fill(whoami, generation))[1], "NO GUARD")
        reset = next(s for s in steps if " reset-state " in s)
        self.assertEqual(self.run_guard(fill(reset, generation))[0], 0)

    def test_the_heartbeat_reaches_a_stall_with_its_documented_notes_written(self):
        """Two trips, with the prompt's own note written after the first: the note must not pass for progress."""
        prompt = guard_section(".agents").split("#### Heartbeat", 1)[1]
        template = re.search(r"If it printed `trip 1`, append `([^`]+)`", prompt)
        self.assertIsNotNone(template, "the heartbeat does not say how it logs the first trip")
        still = next(s for s in heartbeat_commands(".agents") if " heartbeat-still " in s)
        generation, _ = self.start(".agents", COPIES[".agents"])
        run_file = self.ws / "docs/phase-runs/2099-01-01-phase-1.md"
        line = ""
        for _ in range(1 + 6):  # the baseline, then six stills: the first trip
            line = self.run_guard(self.fill(still, COPIES[".agents"], generation=generation))[1]
        self.assertIn("trip 1", line)
        note = template.group(1).replace("<that line>", line).replace("<UTC>", "2099-01-01T00:00:00Z")
        with open(run_file, "a", encoding="utf-8") as fh:
            fh.write(note + "\n")  # one line, as the agent appends it
        for _ in range(6):
            line = self.run_guard(self.fill(still, COPIES[".agents"], generation=generation))[1]
        self.assertIn("end: stall", line, "the heartbeat's own note reset the breaker")
        self.assertFalse((self.ws / "build/claude-campaign-guard.json").exists())

    def test_each_copy_names_its_own_session_and_no_claude_code_tool(self):
        for agent, variable in COPIES.items():
            section = guard_section(agent)
            self.assertIn(f"${variable}", section)
            self.assertIn(f"$env:{variable}", section, "no PowerShell spelling")
            for foreign in ("CronCreate", "CronList", "CronDelete"):
                self.assertNotIn(foreign, section, f"{agent} names Claude Code's {foreign}")
            hook_file = {".agents": ".agents/hooks.json", ".codex": ".codex/hooks.json"}[agent]
            self.assertIn(hook_file, section)
            self.assertIn("scripts/unattended-run.py", section)
            self.assertIn("is not a released run", section)
            guard_commands = set(re.findall(r'argv\[0\] (?:==|in) \(?"([a-z-]+)"', (TEMPLATES / "scripts" / "campaign_guard.py").read_text(encoding="utf-8")))
            for named in re.findall(r"campaign_guard\.py ([a-z-]+)", section):
                self.assertIn(named, guard_commands | {"reconcile", "health"}, f"{agent} names a command the guard lacks: {named}")
        codex = guard_section(".codex")
        self.assertIn("scripts/codex-campaign-hook.py", codex)
        self.assertIn("scripts/codex-hook-trust.py", codex)
        self.assertIn("CLAUDE_CODE_SESSION_ID", codex, "no warning against the inherited Claude Code variable")


if __name__ == "__main__":
    unittest.main()
