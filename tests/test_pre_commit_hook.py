"""kits/todo scripts/hooks/pre-commit: a commit that stages TODO changes with a stale plan is refused before CI sees it."""
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import forge  # noqa: E402
from test_todo_graph import todo_file  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
KIT = REPO / "kits" / "todo" / "templates"
HOOK = "scripts/hooks/pre-commit"
# Where each installed file comes from: the todo kit, and the reviewer kit for the dispatcher stamping loads.
FILES = {"scripts/todo-graph.py": KIT / "scripts/todo-graph.py",
         "scripts/lib/todo_graph.py": KIT / "scripts/lib/todo_graph.py",
         "scripts/review-dispatch.py": REPO / "kits/reviewer/templates/scripts/review-dispatch.py",
         HOOK: KIT / HOOK}

class Scratch:
    """A throwaway folder that can still be removed after git marks its objects read-only."""

    def __init__(self):
        self.name = tempfile.mkdtemp()

    def cleanup(self):
        for path in pathlib.Path(self.name).rglob("*"):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        shutil.rmtree(self.name, ignore_errors=True)



@unittest.skipUnless(shutil.which("git"), "needs git (which runs the hook with its own shell)")
class PreCommitHook(unittest.TestCase):
    def setUp(self):
        self.tmp = Scratch()
        self.root = pathlib.Path(self.tmp.name)
        for rel, source in FILES.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, self.root / rel)
        (self.root / HOOK).chmod(0o755)  # git runs only an executable hook on Linux
        todo = self.root / "todo/00-workspace"
        todo.mkdir(parents=True)
        (todo / "TODO-01-a.md").write_text(todo_file([(1, "A", 0, "none", "--")]), encoding="utf-8")
        (todo / "INDEX.md").write_text("# Index\n- TODO-01-a.md\n", encoding="utf-8")
        (self.root / "todo/TODO-00-INDEX.md").write_text("# Index\n- 00-workspace/TODO-01-a.md\n", encoding="utf-8")
        self.sync()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"],
                     ["config", "core.autocrlf", "false"], ["add", "-A"], ["commit", "-qm", "seed"],
                     ["config", "core.hooksPath", "scripts/hooks"]):
            self.git(*args)

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, check=True)

    def sync(self):
        subprocess.run([sys.executable, str(self.root / "scripts/todo-graph.py"), "plan", "--sync"], check=True,
                       capture_output=True)

    def commit(self):
        return subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "tick"], capture_output=True, text=True)

    def tick(self):
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("- [ ] Work.", "- [x] Work."), encoding="utf-8")

    def test_a_todo_change_with_a_stale_plan_is_refused(self):
        self.tick()
        self.git("add", "todo/00-workspace/TODO-01-a.md")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("plan --sync", result.stderr)
        self.sync()
        self.git("add", "-A")
        self.assertEqual(self.commit().returncode, 0)

    def test_a_todo_change_with_a_synced_plan_is_accepted(self):
        self.tick()
        self.sync()
        self.git("add", "-A")
        result = self.commit()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unstaged_todo_changes_are_refused(self):
        self.tick()
        self.sync()
        self.git("add", "todo/00-workspace/TODO-01-a.md")  # the synced plan is left unstaged
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("todo/ has unstaged or untracked changes", result.stderr)

    def test_an_untracked_review_file_beside_a_todo_change_is_refused(self):
        self.tick()
        self.sync()
        (self.root / "docs/reviews").mkdir(parents=True)
        (self.root / "docs/reviews/d00-t01-s1.json").write_text("{}\n", encoding="utf-8")  # left out of the commit
        self.git("add", "todo")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("docs/reviews/ has unstaged or untracked changes", result.stderr)

    def test_an_ignored_review_file_beside_a_todo_change_is_refused(self):
        self.tick()
        self.sync()
        (self.root / "docs/reviews").mkdir(parents=True)
        (self.root / "docs/reviews/d00-t01-s1.json").write_text("{}\n", encoding="utf-8")
        (self.root / ".git/info/exclude").write_text("docs/reviews/\n", encoding="utf-8")
        self.git("add", "todo")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("docs/reviews/ has unstaged or untracked changes", result.stderr)

    def test_an_evidence_only_commit_that_breaks_the_graph_is_refused(self):
        (self.root / "docs/reviews").mkdir(parents=True)
        (self.root / "docs/reviews/legacy-receipts.json").write_text("not json\n", encoding="utf-8")
        self.git("add", "docs/reviews")  # no todo/ change staged
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)

    def configure(self, receipts):
        """D03 T01 §4: the receipts folder is todo/plan.json's layout.receipts; the hook reads it from the graph."""
        (self.root / "todo/plan.json").write_text('{"layout": {"receipts": "%s"}}\n' % receipts, encoding="utf-8")
        self.git("add", "todo/plan.json")
        result = self.commit()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_configured_receipts_folder_is_the_one_the_hook_watches(self):
        self.configure("reviews")
        (self.root / "reviews").mkdir()
        (self.root / "reviews/legacy-receipts.json").write_text("not json\n", encoding="utf-8")
        self.git("add", "reviews")  # evidence only, in the configured folder: checked, and the graph refuses it
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reviews/legacy-receipts.json is not JSON", result.stderr)
        self.git("rm", "-q", "--cached", "reviews/legacy-receipts.json")
        (self.root / "reviews/legacy-receipts.json").unlink()
        (self.root / "docs/reviews").mkdir(parents=True)
        (self.root / "docs/reviews/legacy-receipts.json").write_text("not json\n", encoding="utf-8")
        self.git("add", "docs/reviews")  # the default folder is no longer evidence here
        self.assertEqual(self.commit().returncode, 0)

    def test_an_untracked_file_in_the_configured_folder_beside_a_todo_change_is_refused(self):
        self.configure("reviews")
        self.tick()
        self.sync()
        (self.root / "reviews").mkdir()
        (self.root / "reviews/d00-t01-s1.json").write_text("{}\n", encoding="utf-8")  # left out of the commit
        self.git("add", "todo")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reviews/ has unstaged or untracked changes", result.stderr)
        (self.root / "reviews/d00-t01-s1.json").unlink()
        self.assertEqual(self.commit().returncode, 0, "the fully staged commit is accepted")

    def test_an_unstaged_layout_cannot_move_the_hook_off_the_committed_folder(self):
        # D03 T01 §4 round 1: the commit holds the staged todo/plan.json (none: docs/reviews), the working tree says
        # reviews; broken evidence staged in docs/reviews must still be checked, and refused until plan.json is staged.
        (self.root / "docs/reviews").mkdir(parents=True)
        (self.root / "docs/reviews/legacy-receipts.json").write_text("not json\n", encoding="utf-8")
        self.git("add", "docs/reviews")
        (self.root / "todo/plan.json").write_text('{"layout": {"receipts": "reviews"}}\n', encoding="utf-8")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("todo/ has unstaged or untracked changes", result.stderr)

    def configure_plan(self):
        """D03 T01 §7: the plan at todo/plan.json's layout.plan, docs/plan.md, committed in sync."""
        (self.root / "todo/plan.json").write_text('{"layout": {"plan": "docs/plan.md"}}\n', encoding="utf-8")
        (self.root / "todo/implementation-plan.md").unlink()
        self.sync()
        self.git("add", "-A")
        result = self.commit()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_commit_staging_only_a_corrupted_configured_plan_is_refused(self):
        self.configure_plan()
        with open(self.root / "docs/plan.md", "a", encoding="utf-8") as handle:
            handle.write("a line plan --sync did not write\n")
        self.git("add", "docs/plan.md")  # no todo/ change staged: the plan alone is evidence
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage docs/plan.md", result.stderr)

    def test_a_stale_staged_plan_beside_a_current_unstaged_one_is_refused(self):
        self.configure_plan()
        self.tick()
        self.git("add", "todo")  # the staged plan is the old one
        self.sync()  # the working tree's is current, and unstaged
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("docs/plan.md has unstaged or untracked changes", result.stderr)
        self.git("add", "docs/plan.md")
        self.assertEqual(self.commit().returncode, 0, "the fully staged commit is accepted")

    def test_a_layout_the_graph_cannot_read_is_refused(self):
        (self.root / "todo/plan.json").write_text('{"layout": {"receipts": "../out"}}\n', encoding="utf-8")
        (self.root / "notes.txt").write_text("x\n", encoding="utf-8")
        self.git("add", "notes.txt")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("todo/plan.json: layout receipts must be a folder inside the repository", result.stderr)

    def test_a_commit_without_todo_changes_is_not_checked(self):
        (self.root / "notes.txt").write_text("x\n", encoding="utf-8")
        (self.root / "todo/00-workspace/TODO-01-a.md").write_text("broken\n", encoding="utf-8")  # unstaged, untouched
        self.git("add", "notes.txt")
        self.assertEqual(self.commit().returncode, 0)


@unittest.skipUnless(shutil.which("git"), "needs git (which runs the hook with its own shell)")
class InstallAndDoctor(unittest.TestCase):
    """D01 T02 section 7: `forge.py kit <project> todo` enables the hook where nothing else owns the repository's
    hooks, and `forge.py doctor <project> todo` says what is left. Every fixture is set up by the installer alone:
    no hand copy of the hook, no chmod, no `git config core.hooksPath` unless the test is about another owner."""

    CONFLICT = "would stop those hooks"

    def setUp(self):
        self.tmp = Scratch()
        self.addCleanup(self.tmp.cleanup)
        self.work = pathlib.Path(self.tmp.name).resolve()
        # The host's own git settings are not the fixture's (a global core.hooksPath would own every repository),
        # and the todo kit's install asks Codex to approve its Stop hook: a stub answers, never the real one.
        stub = json.dumps([sys.executable, str(REPO / "tests/fixtures/codex_app_server_stub.py")])
        env = unittest.mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                                                    "CODEX_HOOK_TRUST_SERVER": stub})
        env.start()
        self.addCleanup(env.stop)

    def git(self, folder, *args, check=True):
        return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True, check=check)

    def repository(self, name="project"):
        folder = self.work / name
        folder.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"],
                     ["config", "core.autocrlf", "false"]):
            self.git(folder, *args)
        return folder

    def hooks_path(self, folder):
        return self.git(folder, "config", "--get", "core.hooksPath", check=False).stdout.strip()

    def check(self, project):
        (found,) = [c for c in forge.doctor_repo(project, "todo")["checks"] if c["name"] == "pre-commit-hook"]
        return found["status"], found["detail"]

    def test_a_fresh_repository_has_the_hook_enabled_and_a_second_install_says_so(self):
        project = self.repository()
        self.assertEqual(forge.apply_kit(project, "todo")["pre_commit_hook"], "enabled")
        self.assertEqual(self.hooks_path(project), "scripts/hooks")
        self.assertEqual(self.check(project), ("ok", "core.hooksPath is scripts/hooks"))
        self.assertEqual(forge.apply_kit(project, "todo")["pre_commit_hook"], "already enabled")
        self.assertEqual(self.hooks_path(project), "scripts/hooks")

    def test_a_real_commit_with_a_stale_plan_is_refused_once_the_kit_is_installed(self):
        project = self.repository()
        forge.apply_kit(project, "reviewer")  # the dispatcher the graph loads when it reads receipts
        self.assertEqual(forge.apply_kit(project, "todo")["pre_commit_hook"], "enabled")
        self.assert_git_refuses_a_stale_plan(project)

    def test_a_fresh_install_with_no_todo_file_yet_commits_its_findings(self):
        """A just-installed tree has no TODO file and no generated plan, so there is no graph to hold to the gates:
        the install itself and a finding filed before any section exists commit, while a stale plan is still refused
        once the first file is written."""
        project = self.repository()
        forge.apply_kit(project, "reviewer")
        self.assertEqual(forge.apply_kit(project, "todo")["pre_commit_hook"], "enabled")
        self.git(project, "add", "-A")
        installed = self.git(project, "commit", "-qm", "install", check=False)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        findings = project / "todo/findings.md"
        findings.write_text(findings.read_text(encoding="utf-8") + "\n- scripts/x.py:1 a finding.\n", encoding="utf-8")
        self.git(project, "add", "todo/findings.md")
        filed = self.git(project, "commit", "-qm", "finding", check=False)
        self.assertEqual(filed.returncode, 0, filed.stderr)
        # The first TODO file, committed before its plan is generated, ends the fresh state and is refused.
        todo = project / "todo/00-workspace"
        todo.mkdir(parents=True)
        (todo / "TODO-01-a.md").write_text(todo_file([(1, "A", 0, "none", "--")]), encoding="utf-8")
        self.git(project, "add", "-A")
        first = self.git(project, "commit", "-qm", "first", check=False)
        self.assertNotEqual(first.returncode, 0, "the first TODO file went through with no generated plan")
        self.assertIn("plan --sync", first.stderr + first.stdout)
        # A note below a domain folder is not a TODO file the graph reads, so the tree is still fresh.
        shutil.rmtree(todo)
        (project / "todo/01-work/examples").mkdir(parents=True)
        (project / "todo/01-work/examples/TODO-sample.md").write_text("a sample\n", encoding="utf-8")
        self.git(project, "add", "-A")
        sample = self.git(project, "commit", "-qm", "sample", check=False)
        self.assertEqual(sample.returncode, 0, sample.stderr)
        self.assert_git_refuses_a_stale_plan(project)

    def test_an_empty_tree_beside_a_generated_plan_is_still_checked(self):
        """Removing the last TODO file while its generated plan stays is not a fresh tree: the gates still run."""
        project = self.repository()
        forge.apply_kit(project, "reviewer")
        forge.apply_kit(project, "todo")
        (project / "todo/implementation-plan.md").write_text("stale\n", encoding="utf-8")
        self.git(project, "add", "-A")
        refused = self.git(project, "commit", "-qm", "install", check=False)
        self.assertNotEqual(refused.returncode, 0, "a plan with no TODO file behind it went through")

    def assert_git_refuses_a_stale_plan(self, project):
        """One real `git commit` with a stale plan is refused, and goes through once the plan is synced: git ran the
        kit's hook, whichever way the repository reaches it."""
        todo = project / "todo/00-workspace"
        todo.mkdir(parents=True)
        (todo / "TODO-01-a.md").write_text(todo_file([(1, "A", 0, "none", "--")]), encoding="utf-8")
        (todo / "INDEX.md").write_text("# Index\n- TODO-01-a.md\n", encoding="utf-8")
        (project / "todo/TODO-00-INDEX.md").write_text("# Index\n- 00-workspace/TODO-01-a.md\n", encoding="utf-8")

        def sync():
            subprocess.run([sys.executable, str(project / "scripts/todo-graph.py"), "plan", "--sync"], check=True,
                           capture_output=True, cwd=project)

        sync()
        self.git(project, "add", "-A")
        seeded = self.git(project, "commit", "-qm", "seed", check=False)
        self.assertEqual(seeded.returncode, 0, seeded.stderr)
        path = todo / "TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("- [ ] Work.", "- [x] Work."), encoding="utf-8")
        self.git(project, "add", "todo/00-workspace/TODO-01-a.md")
        refused = self.git(project, "commit", "-qm", "tick", check=False)
        self.assertNotEqual(refused.returncode, 0, "git ran no hook: the commit with a stale plan went through")
        self.assertIn("plan --sync", refused.stderr + refused.stdout)
        sync()
        self.git(project, "add", "-A")
        accepted = self.git(project, "commit", "-qm", "tick", check=False)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_a_project_with_hooks_of_its_own_keeps_them_and_is_told_how_to_join_the_two(self):
        for name in ("pre-commit", "pre-push"):
            with self.subTest(own=name):
                project = self.repository(f"own-{name}")
                own = project / ".git/hooks" / name
                own.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                left = forge.apply_kit(project, "todo")["pre_commit_hook"]
                self.assertTrue(left.startswith("left: ") and name in left, left)
                self.assertEqual(self.hooks_path(project), "")
                status, detail = self.check(project)
                self.assertEqual(status, "setup_required")
                self.assertIn(self.CONFLICT, detail)
                self.assertIn(f"({name})", detail)
                self.assertIn("Call scripts/hooks/pre-commit from", detail)
                joined = project / ".git/hooks/pre-commit"
                # Naming the kit's hook in a comment is not calling it (found by the round of D01 T02 section 7).
                joined.write_text("#!/bin/sh\n# TODO: call scripts/hooks/pre-commit\nexit 0\n", encoding="utf-8")
                joined.chmod(0o755)
                self.assertEqual(self.check(project)[0], "setup_required")
                self.assertIn(self.CONFLICT, self.check(project)[1])
                # Once a command line of the project's pre-commit hook names the kit's, nothing is left to set up;
                # the doctor says it read the hook, since it runs nothing.
                joined.write_text('#!/bin/sh\n"$(git rev-parse --show-toplevel)/scripts/hooks/pre-commit" || exit 1\n',
                                  encoding="utf-8")
                if os.name != "nt":
                    # A hook file git will not run is not a hook, whatever it says (same round).
                    joined.chmod(0o644)
                    self.assertEqual(self.check(project), ("setup_required", f"chmod +x {joined.as_posix()}: git runs "
                                                                             "only an executable hook"))
                joined.chmod(0o755)
                self.assertEqual(self.check(project), (
                    "ok", f"{joined.as_posix()} names scripts/hooks/pre-commit on a command line (read, not run)"))

    def test_a_projects_own_hook_that_calls_the_kits_refuses_a_real_commit_with_a_stale_plan(self):
        project = self.repository()
        own = project / ".git/hooks/pre-commit"
        own.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        own.chmod(0o755)
        forge.apply_kit(project, "reviewer")
        self.assertTrue(forge.apply_kit(project, "todo")["pre_commit_hook"].startswith("left: "))
        own.write_text('#!/bin/sh\n"$(git rev-parse --show-toplevel)/scripts/hooks/pre-commit" || exit 1\n',
                       encoding="utf-8")
        own.chmod(0o755)
        self.assertEqual(self.check(project)[0], "ok")
        self.assertEqual(self.hooks_path(project), "")
        self.assert_git_refuses_a_stale_plan(project)

    def test_an_empty_hooks_path_is_a_choice_the_install_keeps(self):
        # Found by the round of D01 T02 section 7: `git config core.hooksPath ""` is set, not unset.
        project = self.repository()
        self.git(project, "config", "core.hooksPath", "")
        left = forge.apply_kit(project, "todo")["pre_commit_hook"]
        self.assertEqual(left, "left: core.hooksPath is set to an empty value")
        listed = self.git(project, "config", "--get-all", "core.hooksPath", check=False)
        self.assertEqual((listed.returncode, listed.stdout), (0, "\n"))
        status, detail = self.check(project)
        self.assertEqual(status, "setup_required")
        self.assertTrue(detail.startswith("core.hooksPath is set to an empty value: "), detail)
        self.assertIn("replace it on purpose with git config core.hooksPath scripts/hooks", detail)

    def test_another_hooks_path_is_left_and_the_doctor_never_tells_it_to_be_overwritten_blindly(self):
        project = self.repository()
        (project / ".husky").mkdir()
        (project / ".husky/pre-commit").write_text("#!/bin/sh\nnpx lint-staged\n", encoding="utf-8")
        self.git(project, "config", "core.hooksPath", ".husky")
        left = forge.apply_kit(project, "todo")["pre_commit_hook"]
        self.assertEqual(left, "left: core.hooksPath is .husky")
        self.assertEqual(self.hooks_path(project), ".husky")
        status, detail = self.check(project)
        self.assertEqual(status, "setup_required")
        self.assertTrue(detail.startswith("core.hooksPath is .husky: "), detail)
        self.assertIn(self.CONFLICT, detail)
        self.assertIn("or replace that setup on purpose", detail)
        with (project / ".husky/pre-commit").open("a", encoding="utf-8") as hook:
            hook.write("sh scripts/hooks/pre-commit\n")
        (project / ".husky/pre-commit").chmod(0o755)  # git runs only an executable hook on Linux
        self.assertEqual(self.check(project)[0], "ok")
        # A hooks path that names a folder with no pre-commit hook in it is still another owner.
        self.git(project, "config", "core.hooksPath", "elsewhere")
        self.assertEqual(self.check(project)[0], "setup_required")
        self.assertIn(self.CONFLICT, self.check(project)[1])

    def test_no_scripts_installs_no_hook_and_enables_none(self):
        project = self.repository()
        result = forge.provision(project, with_todo=True, include_scripts=False)
        (todo,) = [kit for kit in result["kits"] if kit["kit"] == "todo"]
        self.assertTrue(todo["pre_commit_hook"].startswith("left: scripts/hooks/pre-commit is not installed"), todo)
        self.assertEqual(self.hooks_path(project), "")
        status, detail = self.check(project)
        self.assertEqual(status, "missing")
        self.assertIn("scripts/hooks/pre-commit is not installed", detail)

    def test_a_dry_run_sets_nothing(self):
        project = self.repository()
        self.assertNotIn("pre_commit_hook", forge.apply_kit(project, "todo", dry_run=True))
        self.assertEqual(self.hooks_path(project), "")

    def test_a_folder_in_no_repository_has_no_commit_to_check(self):
        project = self.work / "plain"
        project.mkdir()
        self.assertEqual(forge.apply_kit(project, "todo")["pre_commit_hook"], "left: not a git repository")
        self.assertEqual(self.check(project), ("ok", "not a git repository: no commit to check"))

    def test_a_project_nested_in_its_repository_is_reported_and_given_no_setting(self):
        top = self.repository("top")
        project = top / "app"
        project.mkdir()
        left = forge.apply_kit(project, "todo")["pre_commit_hook"]
        self.assertTrue(left.startswith("left: the project is a subfolder of the repository at "), left)
        self.assertEqual(self.hooks_path(top), "")
        status, detail = self.check(project)
        self.assertEqual(status, "setup_required")
        self.assertIn("cannot check a nested project", detail)
        self.assertIn("python scripts/todo-graph.py validate", detail)
        self.assertIn("plan --check", detail)
        self.assertNotIn("git config", detail)

    def test_a_machine_where_git_does_not_run_is_reported(self):
        project = self.repository()
        with unittest.mock.patch.object(forge, "_git_answer", return_value=None):
            left = forge.apply_kit(project, "todo")["pre_commit_hook"]
            status, detail = self.check(project)
        self.assertTrue(left.startswith("left: git cannot be run here"), left)
        self.assertEqual(status, "setup_required")
        self.assertIn("git cannot be run here", detail)
        self.assertEqual(self.hooks_path(project), "")

    def test_an_enabled_hook_that_is_gone_or_cannot_run_is_not_ok(self):
        project = self.repository()
        forge.apply_kit(project, "todo")
        hook = project / "scripts/hooks/pre-commit"
        if os.name != "nt":
            hook.chmod(0o644)
            self.assertEqual(self.check(project), ("setup_required", "chmod +x scripts/hooks/pre-commit: git runs only "
                                                                     "an executable hook"))
            hook.chmod(0o755)
        self.assertEqual(self.check(project)[0], "ok")
        kept = hook.read_bytes()
        hook.unlink()
        status, detail = self.check(project)
        self.assertEqual(status, "missing")
        self.assertIn("scripts/hooks/pre-commit is not installed", detail)
        hook.write_bytes(kept)
        hook.chmod(0o755)
        (project / "scripts/todo-graph.py").unlink()
        status, detail = self.check(project)
        self.assertEqual(status, "missing")
        self.assertIn("scripts/todo-graph.py is not installed", detail)

    def test_a_failed_write_of_the_setting_is_reported_and_a_retry_works(self):
        project = self.repository()
        lock = project / ".git/config.lock"
        lock.write_text("", encoding="utf-8")  # what a git config still running, or one that was killed, leaves
        result = forge.apply_kit(project, "todo")
        self.assertTrue(result["pre_commit_hook"].startswith("left: git config failed: "), result["pre_commit_hook"])
        self.assertIn("scripts/hooks/pre-commit", result["installed"])  # the install itself stands
        lock.unlink()
        self.assertEqual(self.hooks_path(project), "")
        self.assertEqual(self.check(project), ("setup_required", "git config core.hooksPath scripts/hooks"))
        self.assertEqual(forge.apply_kit(project, "todo")["pre_commit_hook"], "enabled")
        self.assertEqual(self.hooks_path(project), "scripts/hooks")

    def test_pre_commit_blocks_staged_design_lint_violation_and_passes_when_tokenized(self):
        project = self.repository()
        forge.apply_kit(project, "todo")
        shutil.copyfile(REPO / "kits/base/templates/scripts/design-lint.py", project / "scripts/design-lint.py")
        (project / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
        (project / "src/ui").mkdir(parents=True)
        panel = project / "src/ui/panel.css"
        panel.write_text(".bad {\n  color: #ff0000;\n}\n", encoding="utf-8")
        self.git(project, "add", "DESIGN.md", "src/ui/panel.css", "scripts/design-lint.py")
        bad = subprocess.run(["git", "-C", str(project), "commit", "-qm", "bad ui"], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0, bad.stdout + bad.stderr)
        self.assertIn("color-literal", bad.stdout + bad.stderr)

        panel.write_text(".good {\n  color: var(--ink);\n}\n", encoding="utf-8")
        self.git(project, "add", "src/ui/panel.css")
        good = subprocess.run(["git", "-C", str(project), "commit", "-qm", "good ui"], capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)


class HookFile(unittest.TestCase):
    def test_the_hook_is_tracked_as_executable(self):
        if not shutil.which("git"):
            self.skipTest("needs git")
        listed = subprocess.run(["git", "-C", str(REPO), "ls-files", "-s", "--", str(KIT / HOOK)],
                                capture_output=True, text=True, check=True).stdout.split()
        if not listed:
            self.skipTest("the kit's pre-commit hook is not tracked yet")
        self.assertEqual(listed[0], "100755")

    def test_the_hook_has_lf_line_endings(self):
        self.assertNotIn(b"\r\n", (KIT / HOOK).read_bytes(), "sh cannot run a hook with CRLF line endings")


if __name__ == "__main__":
    unittest.main()
