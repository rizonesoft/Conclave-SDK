"""Tests for the correct-layer hook. Run on Windows and WSL: python -m unittest discover -s rules/hooks"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layer_rules  # noqa: E402


def run_hook(payload):
    out = subprocess.run([sys.executable, os.path.join(HERE, "layer_rules.py")], input=json.dumps(payload),
                         capture_output=True, text=True, encoding="utf-8")
    return json.loads(out.stdout) if out.stdout.strip() else None


def context(result):
    return result["hookSpecificOutput"]["additionalContext"] if result else None


class LayerHookTest(unittest.TestCase):
    def setUp(self):
        self.session = "test-" + uuid.uuid4().hex
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(layer_rules.clear_state, self.session)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def edit(self, name, old, new, lands=True):
        """An Edit as Claude runs it: PreToolUse, then PostToolUse once the edit lands. Returns the Pre result."""
        payload = {"session_id": self.session, "tool_name": "Edit",
                   "tool_input": {"file_path": self.path(name), "old_string": old, "new_string": new}}
        result = run_hook({"hook_event_name": "PreToolUse", **payload})
        if lands:
            self.assertIsNone(run_hook({"hook_event_name": "PostToolUse", **payload}))
        return result

    def stop(self, message, active=False):
        return run_hook({"hook_event_name": "Stop", "session_id": self.session, "stop_hook_active": active,
                         "last_assistant_message": message})

    # Masking patterns.
    def test_added_output_buffer_is_flagged(self):
        result = context(self.edit("theme.php", "function boot() {\n}", "function boot() {\n    ob_start('fix_markup');\n}"))
        self.assertIn("theme.php:2: output buffer rewriting the page", result)

    def test_workaround_comment_answers_the_flag(self):
        new = "// WORKAROUND: Elementor 3.2 has no control for this; remove when it does.\nadd_filter('the_content', 'fix');"
        self.assertIsNone(self.edit("theme.php", "", new))

    def test_pattern_already_in_the_file_is_not_flagged(self):
        old = "ob_start();\n$a = 1;"
        self.assertIsNone(self.edit("theme.php", old, "ob_start();\n$a = 2;"))

    def test_business_logic_filter_is_not_flagged(self):
        self.assertIsNone(self.edit("query.php", "", "add_filter('pre_get_posts', 'exclude_cancelled_orders');"))

    def test_each_masking_pattern_is_recognised(self):
        cases = {
            "app.ts": "// @ts-ignore\nconst x = broken();",
            "style.css": ".notice { display: none !important; }",
            "test_x.py": "@pytest.mark.skip(reason='flaky')\ndef test_a(): pass",
            "sync.py": "try:\n    sync()\nexcept Exception:\n    pass",
            "deploy.sh": "npm test || true",
            "fix.js": "el.innerHTML = el.innerHTML.replace(/foo/g, 'bar');",
            "import.php": "$wpdb->update('wp_posts', $data, $where);",
            "load.php": "$data = @file_get_contents($url);",
            "commit.sh": "git commit --no-verify -m wip",
        }
        for name, code in cases.items():
            with self.subTest(name=name):
                self.assertIsNotNone(self.edit(name, "", code))

    def test_php_error_operator_is_php_only(self):
        self.assertIsNone(self.edit("app.py", "", "@app.route('/')\ndef home(): return 'ok'"))

    def test_write_compares_with_the_file_on_disk(self):
        with open(self.path("old.ts"), "w", encoding="utf-8") as f:
            f.write("// @ts-ignore\nlet a = 1;\n")
        payload = {"hook_event_name": "PreToolUse", "session_id": self.session, "tool_name": "Write",
                   "tool_input": {"file_path": self.path("old.ts"), "content": "// @ts-ignore\nlet a = 2;\n"}}
        self.assertIsNone(run_hook(payload))
        payload["tool_input"]["content"] += "// @ts-nocheck\n"
        self.assertIn("old.ts:3", context(run_hook(payload)))

    def test_other_agents_patch_tools_are_ignored(self):
        patch = ("*** Begin Patch\n*** Update File: src/sync.py\n@@\n-    except Exception:\n-        pass\n"
                 "+    except Exception:\n+        pass\n*** End Patch")
        self.assertIsNone(run_hook({"hook_event_name": "PostToolUse", "session_id": self.session, "tool_name": "apply_patch",
                                    "cwd": self.dir.name, "tool_input": {"input": patch}}))
        self.assertIsNone(self.stop("Done."))

    def test_prose_files_are_ignored(self):
        self.assertIsNone(self.edit("notes.md", "", "Never use `@ts-ignore` or `ob_start()`."))
        self.assertIsNone(self.stop("Done."))

    # Layer statement.
    def test_stop_without_code_changes_passes(self):
        self.assertIsNone(self.stop("Answered the question."))

    def test_stop_after_code_change_needs_a_layer_line(self):
        self.edit("app.js", "a = 1", "a = 2")
        result = self.stop("Changed the value.")
        self.assertEqual(result["decision"], "block")
        self.assertIn("Layer:", result["reason"])

    def test_layer_line_satisfies_and_clears(self):
        self.edit("app.js", "a = 1", "a = 2")
        self.assertIsNone(self.stop("Fixed it.\n\n**Layer:** the importer owns this; changed the importer; no workaround."))
        self.assertIsNone(self.stop("Next turn, nothing changed."))

    def test_flagged_lines_are_named_in_the_send_back(self):
        self.edit("theme.php", "", "ob_start('fix');")
        self.assertIn("theme.php:1 output buffer rewriting the page", self.stop("Done.")["reason"])

    def test_second_stop_always_succeeds(self):
        self.edit("app.js", "a = 1", "a = 2")
        self.assertIsNotNone(self.stop("Done."))
        self.assertIsNone(self.stop("Still no line.", active=True))
        self.assertIsNone(self.stop("Later turn."))

    def test_another_stop_hook_does_not_switch_it_off(self):
        # A repository's campaign controller keeps stop_hook_active true for a whole unattended run.
        self.edit("app.js", "a = 1", "a = 2")
        self.assertEqual(self.stop("Section done.", active=True)["decision"], "block")
        self.assertIsNone(self.stop("Still no line.", active=True))
        self.edit("app.js", "a = 2", "a = 3")
        self.assertEqual(self.stop("Next section done.", active=True)["decision"], "block")

    def test_denied_edit_is_not_changed_code(self):
        # A repository's own PreToolUse gate can deny the edit; then nothing changed and no Layer line is owed.
        self.assertIsNotNone(self.edit("theme.php", "", "ob_start('fix');", lands=False))
        self.assertIsNone(self.stop("The gate refused the edit."))
        self.edit("theme.php", "", "ob_start('fix');")
        self.assertIn("theme.php:1 output buffer", self.stop("Done.")["reason"])

    def test_new_prompt_clears_leftover_state(self):
        self.edit("app.js", "a = 1", "a = 2")
        run_hook({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "prompt": "next"})
        self.assertIsNone(self.stop("Done."))

    def test_layer_line_read_from_claude_transcripts_only(self):
        claude = [{"type": "user", "message": {"role": "user", "content": "fix it"}},
                  {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Layer: the template."}]}}]
        other = [{"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "fix it"}]}},
                 {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Layer: the template."}]}}]
        stale = [{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Layer: old turn."}]}},
                 {"type": "user", "message": {"role": "user", "content": "now fix this"}},
                 {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]}}]
        for name, entries, expected in (("claude", claude, True), ("other agent", other, False), ("stale", stale, False)):
            with self.subTest(name=name):
                path = self.path(name + ".jsonl")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(json.dumps(e) for e in entries))
                self.assertEqual(bool(layer_rules.LAYER_LINE.search(layer_rules.final_report(path))), expected)


if __name__ == "__main__":
    unittest.main()
