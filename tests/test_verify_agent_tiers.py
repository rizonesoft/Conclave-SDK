"""Tests for the base kit's scripts/verify-agent-tiers.mjs: the Claude subagent tier rule, including the narrow Haiku allowance."""
import pathlib
import subprocess
import tempfile
import unittest

FORGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFIER = FORGE_ROOT / "kits/base/templates/scripts/verify-agent-tiers.mjs"

HAIKU_OK = {
    "name": "dependency-mapper",
    "description": "List each package's declared dependencies from the manifests and report them as a table.",
    "model": "claude-haiku-5-5",
    "tools": "Read, Glob, Grep",
    "mechanical_share": "95",
    "haiku_replay": "docs/agents/dependency-mapper-replay.md",
}


# Copied byte for byte from R:\GitHub\Isotone\.claude\agents\isotone-reviewer.md, the shape Claude Code's per-agent hooks take.
ISOTONE_HOOKS = r'''hooks:
  PreToolUse:
    - matcher: "Bash|PowerShell"
      hooks:
        - type: command
          command: "python -c \"import os, runpy, sys; sys.argv = ['panel_slots.py', 'delegate-shell-gate']; runpy.run_path(os.path.join(os.environ['CLAUDE_PROJECT_DIR'], 'scripts', 'panel_slots.py'), run_name='__main__')\""
          timeout: 30'''

REVIEWER = {
    "name": "isotone-reviewer",
    "description": "Routine pre-panel review delegate on Sonnet at high effort.",
    "model": "sonnet",
    "tools": "Read, Grep, Glob, Bash",
    "disallowedTools": "Edit, Write, NotebookEdit, Agent",
}


def agent(**fields):
    lines = ["---", *(f"{key}: {value}" for key, value in fields.items()), "---", "", "Body."]
    return "\n".join(lines) + "\n"


def frontmatter(*blocks):
    """An agent file whose frontmatter is the given raw blocks, for shapes `agent()` cannot express."""
    return "\n".join(["---", *blocks, "---", "", "Body."]) + "\n"


def flat(fields):
    return "\n".join(f"{key}: {value}" for key, value in fields.items())


class AgentTierCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        (self.root / ".claude/agents").mkdir(parents=True)
        replay = self.root / "docs/agents/dependency-mapper-replay.md"
        replay.parent.mkdir(parents=True)
        replay.write_text("Known-answer replay on 12 manifests: 12/12 identical to the Sonnet run.\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_verifier(self, **fields):
        return self.run_raw(agent(**fields))

    def run_raw(self, text):
        (self.root / ".claude/agents/subject.md").write_text(text, encoding="utf-8")
        return subprocess.run(["node", str(VERIFIER)], cwd=self.root, capture_output=True, text=True, timeout=60)

    def assert_refused(self, fragment, **fields):
        self.assert_raw_refused(fragment, agent(**fields))

    def assert_raw_refused(self, fragment, text):
        result = self.run_raw(text)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(fragment, result.stderr)

    def assert_raw_passes(self, text):
        result = self.run_raw(text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class VerifyAgentTiers(AgentTierCase):
    def test_sonnet_passes(self):
        result = self.run_verifier(name="git-runner", description="git status", model="sonnet", tools="Bash, Read")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_opus_needs_a_rationale(self):
        self.assert_refused("model_rationale", name="reviewer", description="review", model="opus", tools="Read")

    def test_no_agent_on_any_tier_edits(self):
        tiers = {
            "sonnet": {"name": "implementer", "description": "build it", "model": "sonnet"},
            "opus": {"name": "implementer", "description": "build it", "model": "opus", "model_rationale": "hard code"},
            "haiku": HAIKU_OK,
        }
        for tier, fields in tiers.items():
            for tools in ("Read, Edit", "Write", "Read, MultiEdit", "NotebookEdit, Read", "Read, Edit(src/**)", '"*"'):
                with self.subTest(tier=tier, tools=tools):
                    self.assert_refused("edit tools", **{**fields, "tools": tools})

    def test_every_agent_declares_its_tools(self):
        self.assert_refused('explicit "tools:"', name="git-runner", description="git status", model="sonnet")
        self.assert_refused('explicit "tools:"', name="git-runner", description="git status", model="sonnet", tools='""')

    def test_a_qualifying_haiku_agent_passes(self):
        result = self.run_verifier(**HAIKU_OK)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 on Haiku", result.stdout)

    def test_haiku_must_be_a_pinned_version_of_5_5_or_later(self):
        for model in ("haiku", "claude-haiku-4-5", "claude-haiku-5-4", "claude-haiku-latest"):
            with self.subTest(model=model):
                self.assert_refused("claude-haiku-5-5 or later", **{**HAIKU_OK, "model": model})
        for model in ("claude-haiku-5-5", "claude-haiku-5-10", "claude-haiku-6-0", "claude-haiku-5-5-20261001"):
            with self.subTest(model=model):
                self.assertEqual(self.run_verifier(**{**HAIKU_OK, "model": model}).returncode, 0)

    def test_haiku_work_must_be_at_least_90_percent_mechanical(self):
        for share in ("89", "50", "ninety", "", "100.5"):
            with self.subTest(share=share):
                fields = {**HAIKU_OK, "mechanical_share": share} if share else {k: v for k, v in HAIKU_OK.items() if k != "mechanical_share"}
                self.assert_refused("mechanical_share", **fields)

    def test_haiku_needs_a_replay_record_on_disk(self):
        self.assert_refused("haiku_replay", **{k: v for k, v in HAIKU_OK.items() if k != "haiku_replay"})
        self.assert_refused("haiku_replay", **{**HAIKU_OK, "haiku_replay": "docs/agents/missing.md"})
        self.assert_refused("haiku_replay", **{**HAIKU_OK, "haiku_replay": "../outside.md"})

    def test_haiku_never_does_judgment_work(self):
        for word in ("Review", "audit", "security", "research", "design", "debug", "diagnose", "architecture", "plan", "verdict"):
            with self.subTest(word=word):
                self.assert_refused("judgment", **{**HAIKU_OK, "description": f"Mostly lookups, then {word} the result."})
        self.assert_refused("judgment", **{**HAIKU_OK, "name": "security-scanner"})


class HooksBlock(AgentTierCase):
    """Claude Code's per-agent `hooks:` is the one nested block the strict reader skips, and it still cannot set a key."""

    def test_isotone_hooks_shape_passes(self):
        self.assert_raw_passes(frontmatter(flat(REVIEWER), ISOTONE_HOOKS))
        # The block ends at the next column-0 line, which is read as a top-level key again.
        self.assert_raw_passes(frontmatter(flat({k: v for k, v in REVIEWER.items() if k != "model"}), ISOTONE_HOOKS, "model: sonnet"))
        self.assert_raw_passes(frontmatter(flat(REVIEWER), "hooks:  # shell gate", ISOTONE_HOOKS.split("\n", 1)[1]))
        # A blank line and an indented comment inside the block are still the block.
        self.assert_raw_passes(frontmatter(flat(REVIEWER), ISOTONE_HOOKS.replace("  PreToolUse:", "\n  # gate\n  PreToolUse:")))
        # A quote inside a plain scalar is content, and a block scalar's lines are text.
        self.assert_raw_passes(frontmatter(flat(REVIEWER), ISOTONE_HOOKS, "    note: it's a gate # don't"))
        self.assert_raw_passes(frontmatter(flat(REVIEWER), ISOTONE_HOOKS, "    script: |-\n      echo \"it's\n      [ -f x ]"))

    def test_the_tool_rule_is_unchanged_with_hooks(self):
        self.assert_raw_refused("edit tools", frontmatter(flat({**REVIEWER, "tools": "Read, Edit"}), ISOTONE_HOOKS))

    def test_a_key_inside_the_block_is_not_a_top_level_key(self):
        nested_model = ISOTONE_HOOKS + "\n    model: claude-haiku-4-5"
        nested_tools = ISOTONE_HOOKS.replace("        - type: command", "        - type: command\n          tools: Edit")
        self.assert_raw_passes(frontmatter(flat(REVIEWER), nested_model))
        self.assert_raw_passes(frontmatter(flat(REVIEWER), nested_tools))
        # With no top-level pin, a nested `model:` does not stand in for one.
        self.assert_raw_refused('explicit "model:"', frontmatter(flat({k: v for k, v in REVIEWER.items() if k != "model"}), nested_model))
        # A column-0 key after the block is top level, so a second `model:` there is the duplicate it looks like.
        self.assert_raw_refused('"model:" more than once', frontmatter(flat(REVIEWER), ISOTONE_HOOKS, "model: claude-haiku-4-5"))

    def test_a_tab_in_the_block_indentation_is_refused(self):
        self.assert_raw_refused("tab", frontmatter(flat(REVIEWER), ISOTONE_HOOKS.replace("\n    - matcher", "\n\t- matcher")))
        self.assert_raw_refused("tab", frontmatter(flat(REVIEWER), ISOTONE_HOOKS.replace("\n    - matcher", "\n  \t- matcher")))

    def test_a_quote_left_open_in_the_block_is_refused(self):
        # YAML reads the column-0 line as the rest of the quoted command; a line reader would read a Haiku pin.
        open_quote = ISOTONE_HOOKS.replace('timeout: 30', 'timeout: "30\nmodel: claude-haiku-4-5"')
        self.assert_raw_refused("does not close on the same line", frontmatter(flat(REVIEWER), open_quote))
        open_single = ISOTONE_HOOKS.replace("matcher: \"Bash|PowerShell\"", "matcher: 'Bash|PowerShell")
        self.assert_raw_refused("does not close on the same line", frontmatter(flat(REVIEWER), open_single))
        # A plain key may hold spaces and quotes; the value after its colon is still checked.
        for line in ('    note it: "open', "    - a'b: 'open", '    note: "ends in an escaped line break\\'):
            with self.subTest(line=line):
                self.assert_raw_refused("does not close on the same line", frontmatter(flat(REVIEWER), ISOTONE_HOOKS, line))
        # The same risk through a flow collection that spans lines.
        open_flow = ISOTONE_HOOKS.replace('matcher: "Bash|PowerShell"', "matcher: [Bash,\nmodel: claude-haiku-4-5]")
        self.assert_raw_refused("flow collection", frontmatter(flat(REVIEWER), open_flow))

    def test_hooks_with_an_inline_value_is_refused(self):
        for inline in ("{}", "[]", "{PreToolUse: []}", "&gate", "*gate", "!!map", "|", ">-", "none"):
            with self.subTest(inline=inline):
                self.assert_raw_refused("indented block", frontmatter(flat(REVIEWER), f"hooks: {inline}"))
        self.assert_raw_refused("indented block", frontmatter(flat(REVIEWER), "hooks:"))
        self.assert_raw_refused("indented block", frontmatter(flat(REVIEWER), "hooks:", "- matcher: Bash"))

    def test_a_duplicate_hooks_block_is_refused(self):
        self.assert_raw_refused('"hooks:" more than once', frontmatter(flat(REVIEWER), ISOTONE_HOOKS, ISOTONE_HOOKS))

    def test_an_indented_block_under_any_other_key_is_refused(self):
        for key in ("mcpServers", "Hooks", "permissions", "model"):
            with self.subTest(key=key):
                block = f"{key}:\n  github:\n    command: npx"
                self.assert_raw_refused("is not a plain", frontmatter(flat({k: v for k, v in REVIEWER.items() if k != key}), block))


if __name__ == "__main__":
    unittest.main()
