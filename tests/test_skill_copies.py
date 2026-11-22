"""`forge.py skill-copies`: the Antigravity and Codex copy of each skill file is its Claude file plus a declared patch.

D01 T02 section 5. The fixture is a scratch `kits/` tree, never the repository's own kits; section 6 holds the
committed copies to the generator's output.
"""
import contextlib
import hashlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
import unittest.mock

SDK_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK_ROOT))
import forge  # noqa: E402

ALPHA = b"# Alpha\n\nRun it with `--writer claude`.\n\nOnly Claude Code has this block.\n\nThe end.\n"
ALPHA_AGENTS = b"# Alpha\n\nRun it with `--writer agy`.\n\nOnly Claude Code has this block.\n\nThe end.\n"
ALPHA_CODEX = b"# Alpha\n\nRun it with `--writer codex`.\n\nThe end.\n"
NOTE = b"A reference file no patch touches.\n"
BETA = b"# Beta\n\nThe same for every agent.\n"
# CRLF line endings and text outside ASCII: both are kept byte for byte.
GAMMA = "# Gamma\r\n\r\nCafé → naïve, for Claude.\r\n".encode("utf-8")
GAMMA_CODEX = "# Gamma\r\n\r\nCafé → naïve, for Codex.\r\n".encode("utf-8")
DELTA = b"# Delta\n\nA host overlay's skill, for Claude.\n"
DELTA_AGENTS = b"# Delta\n\nA host overlay's skill, for Antigravity.\n"
OPENAI_YAML = b"interface:\n  display_name: Alpha\n"


def patch_text(*pairs):
    return json.dumps({"schema_version": 1, "replace": [{"find": find, "with": with_} for find, with_ in pairs]})


def digests(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name).resolve()
        self.demo = self.root / "kits/demo"
        self.host = self.root / "kits/wordpress/hosts/demo-host"
        self.write(self.demo / "templates/.claude/skills/alpha/SKILL.md", ALPHA)
        self.write(self.demo / "templates/.claude/skills/alpha/references/note.md", NOTE)
        self.write(self.demo / "templates/.claude/skills/beta/SKILL.md", BETA)
        self.write(self.demo / "templates/.claude/skills/gamma/SKILL.md", GAMMA)
        self.write(self.demo / "templates/.codex/skills/alpha/agents/openai.yaml", OPENAI_YAML)
        self.write(self.demo / "skill-patches/agents/alpha/SKILL.md.json",
                   patch_text(("`--writer claude`", "`--writer agy`")))
        self.write(self.demo / "skill-patches/codex/alpha/SKILL.md.json",
                   patch_text(("`--writer claude`", "`--writer codex`"), ("Only Claude Code has this block.\n\n", "")))
        self.write(self.demo / "skill-patches/codex/gamma/SKILL.md.json",
                   patch_text(("for Claude.\r\n", "for Codex.\r\n")))
        self.write(self.host / "templates/.claude/skills/delta/SKILL.md", DELTA)
        self.write(self.host / "skill-patches/agents/delta/SKILL.md.json", patch_text(("Claude", "Antigravity")))

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path

    # What the generator must write, spelled out here and never read back from the generator.
    EXPECTED = {
        "kits/demo/templates/.agents/skills/alpha/SKILL.md": ALPHA_AGENTS,
        "kits/demo/templates/.agents/skills/alpha/references/note.md": NOTE,
        "kits/demo/templates/.agents/skills/beta/SKILL.md": BETA,
        "kits/demo/templates/.agents/skills/gamma/SKILL.md": GAMMA,
        "kits/demo/templates/.codex/skills/alpha/SKILL.md": ALPHA_CODEX,
        "kits/demo/templates/.codex/skills/alpha/references/note.md": NOTE,
        "kits/demo/templates/.codex/skills/beta/SKILL.md": BETA,
        "kits/demo/templates/.codex/skills/gamma/SKILL.md": GAMMA_CODEX,
        "kits/wordpress/hosts/demo-host/templates/.agents/skills/delta/SKILL.md": DELTA_AGENTS,
        "kits/wordpress/hosts/demo-host/templates/.codex/skills/delta/SKILL.md": DELTA,
    }


class PatchFileTests(Fixture):
    def test_a_patch_loads_as_its_replacements_in_order(self):
        path = self.demo / "skill-patches/codex/alpha/SKILL.md.json"
        patch = forge.load_skill_patch(path)
        self.assertEqual(patch["file"], path)
        self.assertEqual(patch["replace"], [("`--writer claude`", "`--writer codex`"),
                                            ("Only Claude Code has this block.\n\n", "")])

    def test_a_malformed_patch_is_refused_naming_the_file(self):
        path = self.demo / "skill-patches/agents/alpha/SKILL.md.json"
        one = {"find": "a", "with": "b"}
        cases = {
            "not JSON": "{",
            "not an object": "[]",
            "not UTF-8": b"\xff\xfe",
            "no schema_version": json.dumps({"replace": [one]}),
            "wrong schema_version": json.dumps({"schema_version": 2, "replace": [one]}),
            "schema_version true": json.dumps({"schema_version": True, "replace": [one]}),
            "no replace": json.dumps({"schema_version": 1}),
            "unknown key": json.dumps({"schema_version": 1, "replace": [one], "note": "x"}),
            "replace not a list": json.dumps({"schema_version": 1, "replace": one}),
            "entry not an object": json.dumps({"schema_version": 1, "replace": ["a"]}),
            "unknown entry key": json.dumps({"schema_version": 1, "replace": [dict(one, count=2)]}),
            "missing with": json.dumps({"schema_version": 1, "replace": [{"find": "a"}]}),
            "find not a string": json.dumps({"schema_version": 1, "replace": [{"find": 7, "with": "b"}]}),
            "with not a string": json.dumps({"schema_version": 1, "replace": [{"find": "a", "with": None}]}),
            "empty find": json.dumps({"schema_version": 1, "replace": [{"find": "", "with": "b"}]}),
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.write(path, text)
                with self.assertRaises(forge.SkillCopyError) as caught:
                    forge.load_skill_patch(path)
                self.assertIn(path.as_posix(), str(caught.exception))

    def test_an_empty_replace_list_is_a_patch_that_changes_nothing(self):
        path = self.write(self.demo / "skill-patches/agents/beta/SKILL.md.json", patch_text())
        self.assertEqual(forge.generate_copy("text", forge.load_skill_patch(path)), "text")


class GenerateCopyTests(unittest.TestCase):
    FILE = pathlib.Path("kits/demo/skill-patches/codex/alpha/SKILL.md.json")

    def patch(self, *pairs):
        return {"file": self.FILE, "replace": list(pairs)}

    def test_one_replacement(self):
        self.assertEqual(forge.generate_copy("for claude here", self.patch(("claude", "codex"))), "for codex here")

    def test_an_empty_with_removes_the_block(self):
        self.assertEqual(forge.generate_copy("keep\nblock\nkeep\n", self.patch(("block\n", ""))), "keep\nkeep\n")

    def test_replacements_apply_in_order_each_to_the_result_of_the_one_before(self):
        # "middle" is only in the text once the first replacement has run: applied independently it is missing.
        self.assertEqual(forge.generate_copy("start", self.patch(("start", "middle"), ("middle", "end"))), "end")
        # And the first must not see what the second writes.
        self.assertEqual(forge.generate_copy("a b", self.patch(("a", "x"), ("b", "a"))), "x a")

    def test_a_find_that_is_missing_is_refused_naming_the_patch_and_the_text(self):
        with self.assertRaises(forge.SkillCopyError) as caught:
            forge.generate_copy("for claude", self.patch(("for gemini", "x")))
        self.assertIn(self.FILE.as_posix(), str(caught.exception))
        self.assertIn("'for gemini'", str(caught.exception))
        self.assertIn("0 times", str(caught.exception))

    def test_a_find_that_occurs_twice_is_refused(self):
        # str.replace with no count check would write "codex and codex": a patch that hits two places is a wrong copy.
        with self.assertRaises(forge.SkillCopyError) as caught:
            forge.generate_copy("claude and claude", self.patch(("claude", "codex")))
        self.assertIn(self.FILE.as_posix(), str(caught.exception))
        self.assertIn("2 times", str(caught.exception))

    def test_a_find_that_matches_at_two_overlapping_places_is_refused(self):
        # Found by the round of D01 T02 section 5: str.count sees one `---` in `----`, where there are two.
        for source, find, times in (("Heading\n----\n", "---", 2), ("aaaa", "aa", 3), ("abab ab", "ab", 3)):
            with self.subTest(source=source):
                with self.assertRaises(forge.SkillCopyError) as caught:
                    forge.generate_copy(source, self.patch((find, "***")))
                self.assertIn(f"{times} times", str(caught.exception))
        self.assertEqual(forge.generate_copy("Heading\n---\n", self.patch(("---", "***"))), "Heading\n***\n")

    def test_no_patch_is_the_source_unchanged(self):
        self.assertEqual(forge.generate_copy("as it is\r\n", None), "as it is\r\n")


class SkillCopiesTests(Fixture):
    def copies(self):
        return {rel: (self.root / rel).read_bytes() for rel in self.EXPECTED if (self.root / rel).is_file()}

    def test_both_copies_are_generated_as_the_bytes_the_patches_declare(self):
        written = forge.skill_copies(root=self.root)
        self.assertEqual(written, sorted(self.EXPECTED))
        self.assertEqual(self.copies(), self.EXPECTED)
        self.assertEqual(forge.skill_copies(check=True, root=self.root), [])
        self.assertEqual(forge.skill_copies(root=self.root), [])  # a second run has nothing to write

    def test_check_returns_a_deleted_and_a_changed_copy_and_a_run_restores_them(self):
        forge.skill_copies(root=self.root)
        deleted = "kits/demo/templates/.agents/skills/beta/SKILL.md"
        changed = "kits/demo/templates/.codex/skills/gamma/SKILL.md"
        (self.root / deleted).unlink()
        self.write(self.root / changed, GAMMA_CODEX.replace(b"\r\n", b"\n", 1))  # one line ending
        self.assertEqual(forge.skill_copies(check=True, root=self.root), sorted([deleted, changed]))
        self.assertEqual(forge.skill_copies(root=self.root), sorted([deleted, changed]))
        self.assertEqual(self.copies(), self.EXPECTED)

    def test_check_writes_nothing(self):
        forge.skill_copies(root=self.root)
        missing = self.root / "kits/demo/templates/.agents/skills/beta/SKILL.md"
        missing.unlink()
        self.write(self.root / "kits/demo/templates/.codex/skills/beta/SKILL.md", b"changed by hand\n")
        self.write(self.root / "kits/demo/templates/.agents/skills/stray/SKILL.md", b"no source\n")
        before = digests(self.root)
        found = forge.skill_copies(check=True, root=self.root)
        self.assertEqual(len(found), 3)
        self.assertEqual(digests(self.root), before)
        self.assertFalse(missing.exists())

    def test_a_refusal_part_way_leaves_every_destination_as_it_was(self):
        # alpha sorts before zeta and is valid; zeta's patch no longer applies. Nothing is written, alpha included.
        self.write(self.demo / "templates/.claude/skills/zeta/SKILL.md", b"# Zeta\n")
        self.write(self.demo / "skill-patches/codex/zeta/SKILL.md.json", patch_text(("text that is gone", "x")))
        self.write(self.root / "kits/demo/templates/.agents/skills/alpha/SKILL.md", b"the old copy\n")
        before = digests(self.root)
        for check in (False, True):
            with self.subTest(check=check):
                with self.assertRaises(forge.SkillCopyError) as caught:
                    forge.skill_copies(check=check, root=self.root)
                self.assertIn("kits/demo/skill-patches/codex/zeta/SKILL.md.json", str(caught.exception))
                self.assertEqual(digests(self.root), before)

    def test_codex_openai_yaml_is_hand_kept(self):
        written = forge.skill_copies(root=self.root)
        self.assertNotIn("kits/demo/templates/.codex/skills/alpha/agents/openai.yaml", written)
        self.assertEqual(forge.skill_copies(check=True, root=self.root), [])
        self.assertEqual((self.demo / "templates/.codex/skills/alpha/agents/openai.yaml").read_bytes(), OPENAI_YAML)

    def test_a_claude_file_at_the_interface_path_never_replaces_codex_s_own(self):
        # Found by the round of D01 T02 section 5: an imported Claude skill may hold agents/openai.yaml too.
        self.write(self.demo / "templates/.claude/skills/alpha/agents/openai.yaml", b"claude's file\n")
        written = forge.skill_copies(root=self.root)
        self.assertIn("kits/demo/templates/.agents/skills/alpha/agents/openai.yaml", written)
        self.assertNotIn("kits/demo/templates/.codex/skills/alpha/agents/openai.yaml", written)
        self.assertEqual((self.demo / "templates/.codex/skills/alpha/agents/openai.yaml").read_bytes(), OPENAI_YAML)
        self.assertEqual(forge.skill_copies(check=True, root=self.root), [])
        # Where Codex has no such file yet, none is made: it is written by hand or not at all.
        self.write(self.demo / "templates/.claude/skills/beta/agents/openai.yaml", b"claude's file\n")
        forge.skill_copies(root=self.root)
        self.assertFalse((self.demo / "templates/.codex/skills/beta/agents/openai.yaml").exists())
        # A patch for a copy that is never generated has nothing to apply to.
        stale = self.write(self.demo / "skill-patches/codex/alpha/agents/openai.yaml.json", patch_text(("claude", "x")))
        with self.assertRaises(forge.SkillCopyError) as caught:
            forge.skill_copies(root=self.root)
        self.assertIn(stale.relative_to(self.root).as_posix(), str(caught.exception))

    def test_a_copy_with_no_claude_source_is_reported_and_left_in_place(self):
        forge.skill_copies(root=self.root)
        strays = [
            "kits/demo/templates/.agents/skills/alpha/agents/openai.yaml",  # the exception is Codex's alone
            "kits/demo/templates/.agents/skills/retired/SKILL.md",
            "kits/demo/templates/.codex/skills/alpha/agents/other.yaml",
            "kits/demo/templates/.codex/skills/alpha/extra/agents/openai.yaml",  # not <skill>/agents/openai.yaml
            "kits/demo/templates/.codex/skills/retired/SKILL.md",
            "kits/wordpress/hosts/demo-host/templates/.codex/skills/delta/notes.md",
        ]
        for rel in strays:
            self.write(self.root / rel, b"no claude source\n")
        self.assertEqual(forge.skill_copies(check=True, root=self.root), strays)
        self.assertEqual(forge.skill_copies(root=self.root), strays)
        self.assertEqual(forge.skill_copy_report(root=self.root), {"changed": [], "stray": strays})
        for rel in strays:
            self.assertEqual((self.root / rel).read_bytes(), b"no claude source\n")

    def test_a_patch_whose_source_is_gone_is_refused(self):
        stale = self.write(self.demo / "skill-patches/agents/renamed/SKILL.md.json", patch_text(("a", "b")))
        before = digests(self.root)
        with self.assertRaises(forge.SkillCopyError) as caught:
            forge.skill_copies(root=self.root)
        self.assertIn(stale.relative_to(self.root).as_posix(), str(caught.exception))
        self.assertEqual(digests(self.root), before)

    def test_anything_under_skill_patches_that_is_not_an_agents_patch_is_refused(self):
        # rel -> what the refusal names: the folder for an unknown agent, the file for anything else.
        cases = {"skill-patches/claude/alpha/SKILL.md.json": "kits/demo/skill-patches/claude",
                 "skill-patches/gemini/alpha/SKILL.md.json": "kits/demo/skill-patches/gemini",
                 "skill-patches/notes.md": "kits/demo/skill-patches/notes.md",
                 "skill-patches/agents/alpha/SKILL.md.txt": "kits/demo/skill-patches/agents/alpha/SKILL.md.txt"}
        for rel, named in cases.items():
            with self.subTest(rel=rel):
                extra = self.write(self.demo / rel, patch_text(("`--writer claude`", "x")))
                self.addCleanup(shutil.rmtree, self.demo / "skill-patches" / rel.split("/")[1], True)
                before = digests(self.root)
                try:
                    with self.assertRaises(forge.SkillCopyError) as caught:
                        forge.skill_copies(root=self.root)
                    self.assertTrue(str(caught.exception).startswith(named + ": "), str(caught.exception))
                    self.assertEqual(digests(self.root), before)
                finally:
                    extra.unlink()
                    for folder in (self.demo / "skill-patches/claude", self.demo / "skill-patches/gemini"):
                        shutil.rmtree(folder, ignore_errors=True)

    def test_an_empty_folder_for_an_unknown_agent_is_refused(self):
        # Filed by the completion review of D01 T02 section 5: a walk over files alone accepts `skill-patches/gemini/`
        # until a patch is put in it, when the copies it was meant for have long been wrong.
        forge.skill_copies(root=self.root)
        empty = self.demo / "skill-patches/gemini"
        empty.mkdir()
        before = digests(self.root)
        for check in (False, True):
            with self.subTest(check=check):
                with self.assertRaises(forge.SkillCopyError) as caught:
                    forge.skill_copies(check=check, root=self.root)
                self.assertIn("kits/demo/skill-patches/gemini", str(caught.exception))
                self.assertEqual(digests(self.root), before)
        empty.rmdir()
        # The two agents' own folders may be empty: no patch means the copy is the source.
        (self.demo / "skill-patches/agents/empty").mkdir()
        self.assertEqual(forge.skill_copies(check=True, root=self.root), [])

    def test_a_source_that_is_not_utf8_is_refused_naming_it(self):
        bad = self.write(self.demo / "templates/.claude/skills/beta/SKILL.md", b"\xff\xfe")
        with self.assertRaises(forge.SkillCopyError) as caught:
            forge.skill_copies(root=self.root)
        self.assertIn(bad.relative_to(self.root).as_posix(), str(caught.exception))


class RepositoryCopiesTests(unittest.TestCase):
    """D01 T02 section 6: the committed Antigravity and Codex skill files are the generator's output."""

    def test_every_committed_copy_is_what_the_generator_writes(self):
        self.assertEqual(forge.skill_copy_report(check=True), {"changed": [], "stray": []})

    def test_every_kit_with_a_differing_copy_declares_it_in_a_patch(self):
        # A copy can only differ from its Claude file through a patch, so these are all the declared differences.
        patches = sorted(path.relative_to(SDK_ROOT).as_posix()
                         for path in SDK_ROOT.glob("kits/**/skill-patches/**/*.json"))
        self.assertEqual({path.split("/")[1] for path in patches}, {"lsp", "reviewer", "todo", "unattended"})
        self.assertEqual(len(patches), 21)
        for rel in patches:
            self.assertTrue(forge.load_skill_patch(SDK_ROOT / rel)["replace"], f"{rel} declares no difference")

    def test_every_agents_phase_skill_writes_the_end_markers_the_run_guard_reads(self):
        # Found by the round of D01 T02 section 6: the Antigravity and Codex copies of process-phase had lost
        # `run=<run id>` from both markers, which campaign_guard's `end` requires, so a parked or closed run
        # stayed guarded. The patches may differ in who ends the guard, never in what the markers say.
        for agent in (".claude", ".agents", ".codex"):
            with self.subTest(agent=agent):
                text = (SDK_ROOT / "kits/todo/templates" / agent / "skills/process-phase/SKILL.md").read_text(
                    encoding="utf-8")
                self.assertIn("`PARKED <UTC stamp> run=<run id> <one-line reason>`", text)
                self.assertIn("`## Closeout run=<run id>` heading", text)
                self.assertNotIn("`## Closeout` heading", text)

    def test_no_patch_swallows_a_whole_paragraph_outside_the_run_guard_block(self):
        # Same round: a 1,511 character `find` broke on any edit of its paragraph. A phrase is the unit; the one
        # block is process-plan's Run guard, a different mechanism per agent.
        for path in sorted(SDK_ROOT.glob("kits/**/skill-patches/**/*.json")):
            finds = [len(find) for find, _with in forge.load_skill_patch(path)["replace"]]
            allowed = 1 if path.parent.name == "process-plan" else 0
            self.assertLessEqual(sum(size > 400 for size in finds), allowed, path.relative_to(SDK_ROOT).as_posix())

    def test_a_copy_edited_by_hand_fails_the_check_naming_the_file(self):
        # On a scratch copy of kits/, never the checkout: one changed line in one copy of each agent.
        with tempfile.TemporaryDirectory() as tmp:
            scratch = pathlib.Path(tmp).resolve()
            shutil.copytree(SDK_ROOT / "kits", scratch / "kits",
                            ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
            self.assertEqual(forge.skill_copies(check=True, root=scratch), [])
            edited = ["kits/todo/templates/.agents/skills/add-todo/SKILL.md",
                      "kits/base/templates/.codex/skills/local-tool-safety/SKILL.md"]
            for rel in edited:
                with (scratch / rel).open("a", encoding="utf-8", newline="\n") as copy:
                    copy.write("A line added by hand.\n")
            self.assertEqual(forge.skill_copies(check=True, root=scratch), sorted(edited))
            # Editing the Claude file instead fails it too, until the generator has run.
            source = scratch / "kits/base/templates/.claude/skills/authoring-skills/SKILL.md"
            with source.open("a", encoding="utf-8", newline="\n") as claude:
                claude.write("A line added to the source.\n")
            self.assertEqual(len(forge.skill_copies(check=True, root=scratch)), 4)
            self.assertEqual(len(forge.skill_copies(root=scratch)), 4)
            self.assertEqual(forge.skill_copies(check=True, root=scratch), [])


class CommandLineTests(Fixture):
    def run_forge(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(forge, "FORGE_ROOT", self.root), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = forge.main(["skill-copies", *argv])
        return code, out.getvalue(), err.getvalue()

    def test_check_exits_1_until_the_command_has_written_the_copies(self):
        code, out, _err = self.run_forge("--check")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out), {"check": True, "changed": sorted(self.EXPECTED), "stray": []})
        self.assertFalse((self.demo / "templates/.agents").exists())
        code, out, _err = self.run_forge()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"check": False, "changed": sorted(self.EXPECTED), "stray": []})
        self.assertEqual({rel: (self.root / rel).read_bytes() for rel in self.EXPECTED}, self.EXPECTED)
        code, out, _err = self.run_forge("--check")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"check": True, "changed": [], "stray": []})

    def test_a_stray_copy_fails_the_check_and_is_named_by_a_run(self):
        self.run_forge()
        stray = "kits/demo/templates/.codex/skills/retired/SKILL.md"
        self.write(self.root / stray, b"no source\n")
        code, out, _err = self.run_forge("--check")
        self.assertEqual((code, json.loads(out)["stray"]), (1, [stray]))
        code, out, _err = self.run_forge()
        self.assertEqual((code, json.loads(out)), (0, {"check": False, "changed": [], "stray": [stray]}))

    def test_a_patch_that_no_longer_applies_ends_in_one_line_and_exit_2(self):
        self.write(self.demo / "skill-patches/agents/alpha/SKILL.md.json", patch_text(("gone", "x")))
        code, out, err = self.run_forge()
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("forge.py: error: "), err)
        self.assertEqual(len(err.splitlines()), 1)
        self.assertFalse((self.demo / "templates/.agents").exists())


class DesignCheckStepTests(unittest.TestCase):
    """D00 T03 §17: the one Opus design check of a surface section, in the canonical build skill and its prompt."""

    SKILL = SDK_ROOT / "kits/todo/templates/.claude/skills/process-todo-section/SKILL.md"
    PROMPT = SDK_ROOT / "kits/todo/templates/docs/design-check-prompt.md"

    def step(self):
        text = self.SKILL.read_text(encoding="utf-8")
        start = text.index("**One design check on a `Surface: yes` section")
        return text, start, text[start:text.index("\n", start)]

    def test_the_step_sits_after_the_rendered_check_and_before_the_commit(self):
        text, start, _ = self.step()
        self.assertLess(text.index("Reading the code is not a rendered check"), start)
        self.assertLess(start, text.index("### 7. Commit, then hand to review"))
        self.assertGreater(start, text.index("### 6. Run the Test checkpoint, for real"))

    def test_the_step_names_its_prompt_its_isolation_and_its_outcomes(self):
        _, _, step = self.step()
        for part in ("`docs/design-check-prompt.md`", "a new empty folder under the scratch folder", "`--restricted`",
                     "whoever the writer is", "`INPUTS:`", "`DESIGN:` outcome", "`DESIGN: unavailable`",
                     "it runs once", "`design` included, run as they do",
                     # D00 T03 §17 round 1: a partial inspection is no clean verdict, and copies never collide.
                     "`DESIGN: unavailable (partial: <files left out>)`", "`fidelity-<n>-<name>`",
                     "`render-<n>-<name>`",
                     # Completion review: every outcome by name, and a partial reply judged by the design files only.
                     "`DESIGN: clean`", "`DESIGN: findings`", "leaves out any `fidelity-` or `render-` file",
                     "never listed"):
            self.assertIn(part, step)

    def test_the_prompt_runs_confined_and_ends_in_one_of_three_outcomes(self):
        prompt = self.PROMPT.read_text(encoding="utf-8")
        confined = "claude -p --model claude-opus-5-5 --effort medium --restricted --strict-mcp-config --tools Read"
        # Each platform's command on its own, so losing either one fails (D00 T03 §17 round 1).
        self.assertIn(confined + " < design-check-prompt.md", prompt)
        self.assertIn("Get-Content -Raw design-check-prompt.md | " + confined + "`", prompt)
        self.assertNotIn("--allowedTools", prompt)  # it confines nothing, and it swallows a prompt that follows it
        self.assertIn("even where the render matches the design source", prompt)
        for outcome in ("`DESIGN: clean`", "`DESIGN: findings`", "`DESIGN: unavailable`", "`INPUTS:"):
            self.assertIn(outcome, prompt)


class DesignContractWordingTests(unittest.TestCase):
    """D00 T03 §1: canonical design-contract rule lookup, path trigger, static lint, and rendered check clauses."""

    PROCESS_SKILL = SDK_ROOT / "kits/todo/templates/.claude/skills/process-todo-section/SKILL.md"
    REVIEW_SKILL = SDK_ROOT / "kits/todo/templates/.claude/skills/review-todo-section/SKILL.md"
    GEMINI = SDK_ROOT / "kits/base/templates/GEMINI.md"

    def test_canonical_skills_and_gemini_require_design_contract_and_both_checks(self):
        process_text = self.PROCESS_SKILL.read_text(encoding="utf-8")
        for clause in (
            ".agents/rules/design-contract.md",
            ".claude/rules/design-contract.md",
            "--lenses round --no-surface --paths",
            "python scripts/design-lint.py",
            "real rendered check",
            "Reading the code is not a rendered check",
        ):
            self.assertIn(clause, process_text)

        review_text = self.REVIEW_SKILL.read_text(encoding="utf-8")
        for clause in (
            ".agents/rules/design-contract.md",
            ".claude/rules/design-contract.md",
            "static lint and rendered check",
            "[[schedule.conditional]]",
            "never drop `--surface` or reword a section to `Surface: no`",
        ):
            self.assertIn(clause, review_text)

        gemini_text = self.GEMINI.read_text(encoding="utf-8")
        for clause in (
            ".agents/rules/design-contract.md",
            "design contract, token source, forbidden patterns",
            "lint and rendered-check commands",
        ):
            self.assertIn(clause, gemini_text)


if __name__ == "__main__":
    unittest.main()
