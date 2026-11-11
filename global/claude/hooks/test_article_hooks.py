"""Tests for the article hook and checker. Run on Windows and WSL: python -m unittest discover -s rules/hooks"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import article_check  # noqa: E402
import article_rules  # noqa: E402

GOOD = """# How long does a Microsoft 365 migration take?

By Jane Smith. Last reviewed 12 October 2026.

A small business migration to Microsoft 365 usually takes two to five days for 20 users. Most of that time goes on copying old mail, not on setup. We moved a 20 person firm in 2026 and the cutover itself took one evening, with users back in email the next morning.

## What slows a migration down?

Large archives slow it down. In our experience a 50 GB mailbox takes about 8 hours to copy. Microsoft documents the limits [here](https://learn.microsoft.com/exchange/mailbox-migration).
"""


def run_hook(payload):
    out = subprocess.run([sys.executable, os.path.join(HERE, "article_rules.py")], input=json.dumps(payload),
                         capture_output=True, text=True, encoding="utf-8")
    return json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"] if out.stdout.strip() else None


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class CheckerTest(unittest.TestCase):
    def status(self, text, rule, config=None):
        return next(r["status"] for r in article_check.check(text, config=config)["results"] if r["rule"] == rule)

    def test_good_article_has_no_failures(self):
        self.assertEqual(article_check.check(GOOD)["failed"], 0)

    def test_em_dash_used_as_punctuation_fails(self):
        self.assertEqual(self.status(GOOD + "\nIt works \u2014 mostly.\n", "nlp: em and en dashes"), "FAIL")
        self.assertEqual(self.status(GOOD + "\nOpen Monday \u2013 Friday.\n", "nlp: em and en dashes"), "FAIL")

    def test_ranges_quotes_and_code_keep_their_dashes(self):
        for extra in ("Prices held from 2024\u20132026, see pp. 10\u201314.",
                      'The error read "Sync failed \u2014 retry later" on every machine.',
                      "> Our backups failed \u2014 twice \u2014 last year.",
                      "<blockquote>Backups failed \u2014 twice.</blockquote>",
                      "Run `ping \u2014t` to keep pinging."):
            with self.subTest(extra=extra):
                self.assertEqual(self.status(GOOD + "\n" + extra + "\n", "nlp: em and en dashes"), "PASS")

    def test_strong_stock_phrase_fails_and_common_one_warns(self):
        self.assertEqual(self.status(GOOD + "\nLet us delve into the settings.\n", "nlp: stock AI phrasing"), "FAIL")
        text = GOOD + "\nIn conclusion, the world of email is simple.\n"
        self.assertEqual(self.status(text, "nlp: stock AI phrasing"), "PASS")
        self.assertEqual(self.status(text, "nlp: overused phrasing"), "WARN")

    def test_missing_first_hand_experience_warns(self):
        text = "# What is DMARC?\n\nDMARC tells receiving servers what to do with mail that fails SPF or DKIM checks.\n"
        self.assertEqual(self.status(text, "original: first-hand experience"), "WARN")
        self.assertEqual(article_check.check(text)["failed"], 0)

    def test_ai_disclosure_line_fails(self):
        for line in ("This article was written with the help of AI.", "Drafted using ChatGPT and edited by our team.",
                     "An AI-assisted article."):
            with self.subTest(line=line):
                self.assertEqual(self.status(GOOD + "\n" + line + "\n", "eeat: no AI disclosure line"), "FAIL")

    def test_article_about_ai_tools_is_not_a_disclosure(self):
        text = GOOD + "\nGoogle ranks helpful pages whether or not AI tools were involved. Copilot can summarise mail.\n"
        self.assertEqual(self.status(text, "eeat: no AI disclosure line"), "PASS")

    def test_own_domains_are_not_sources(self):
        text = GOOD.replace("https://learn.microsoft.com/exchange/mailbox-migration", "https://example.com/limits")
        self.assertEqual(self.status(text, "eeat: sources"), "PASS")
        self.assertEqual(self.status(text, "eeat: sources", {"own_domains": ["example.com"]}), "FAIL")

    def test_configured_author_counts(self):
        text = GOOD.replace("By Jane Smith. ", "") + "\nWritten from Jane Smith's notes.\n"
        self.assertEqual(self.status(text, "eeat: named author"), "WARN")
        self.assertEqual(self.status(text, "eeat: named author", {"authors": ["Jane Smith"]}), "PASS")

    def test_configured_currency_and_units_count_as_figures(self):
        text = "# Cost?\n\nIt costs R450 for 12 mailboxes and R900 for 30 mailboxes.\n"
        self.assertEqual(self.status(text, "original: specific facts"), "WARN")
        config = {"currencies": ["R"], "units": ["mailboxes"]}
        self.assertEqual(self.status(text, "original: specific facts", config), "PASS")

    def test_config_is_found_above_the_draft(self):
        with tempfile.TemporaryDirectory() as d:
            write(os.path.join(d, ".article-check.json"), '{"wp": "bin/wp-launch"}')
            write(os.path.join(d, "content", "x.md"), "x")
            config, root = article_check.load_config(os.path.join(d, "content", "x.md"))
        self.assertEqual((config, os.path.realpath(root)), ({"wp": "bin/wp-launch"}, os.path.realpath(d)))

    def test_utf8_draft_reads_on_any_platform(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "draft.md")
            write(path, GOOD + "\nCaf\u00e9 owners ask this \u2014 often.\n")
            out = subprocess.run([sys.executable, article_check.__file__, path], capture_output=True, text=True,
                                 encoding="utf-8")
        self.assertEqual(out.returncode, 1, out.stderr)
        self.assertIn("FAIL  nlp: em and en dashes: 1 used as punctuation", out.stdout)


class HookTest(unittest.TestCase):
    def test_article_prompt_gets_rules(self):
        context = run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "Rewrite the blog post about backups"})
        self.assertIn("section 10", context)

    def test_copy_prompt_gets_rules(self):
        self.assertIsNotNone(run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "Write new homepage copy for JMR"}))

    def test_coding_and_rules_prompts_get_nothing(self):
        for prompt in ("Write a copy of the config file", "Update the article hook rules", "Fix the login bug"):
            with self.subTest(prompt=prompt):
                self.assertIsNone(run_hook({"hook_event_name": "UserPromptSubmit", "prompt": prompt}))

    def test_wordpress_write_through_powershell_gets_rules(self):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "PowerShell",
                   "tool_input": {"command": "wp post update 16650 --post_content=@draft.html"}}
        self.assertIn("--post <id>", run_hook(payload))

    def test_other_agents_shell_tools_are_ignored(self):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "shell",
                   "tool_input": {"command": ["bash", "-lc", "bin/wp-launch post create --post_content=x"]}}
        self.assertIsNone(run_hook(payload))

    def test_saved_draft_is_checked(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "drafts", "backups.md")
            write(path, GOOD)
            context = run_hook({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": path}})
        self.assertIn("article-check: ok", context)

    def test_repository_checker_owns_its_drafts(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".git"))
            write(os.path.join(d, "scripts", "article-check.py"),
                  "import os, sys\nprint('REPO CHECK', os.path.basename(sys.argv[1]), os.path.basename(os.getcwd()))\n")
            path = os.path.join(d, "drafts", "dmarc.md")
            write(path, GOOD)
            context = run_hook({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": path}})
        self.assertIn("(repository checker)", context)
        self.assertIn("REPO CHECK dmarc.md " + os.path.basename(d), context)

    def test_other_agents_patch_tools_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            write(os.path.join(d, "posts", "m365 migration.md"), GOOD)
            patch = "*** Begin Patch\n*** Add File: posts/m365 migration.md\n+text\n*** End Patch"
            context = run_hook({"hook_event_name": "PostToolUse", "tool_name": "apply_patch", "cwd": d,
                                "tool_input": {"input": patch}})
        self.assertIsNone(context)

    def test_file_names_alone_do_not_make_a_draft(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("style-guide.md", "postgres-notes.md", os.path.join("docs", "article-standard.md")):
                with self.subTest(name=name):
                    path = os.path.join(d, name)
                    write(path, GOOD + "\nIt works \u2014 mostly.\n")
                    self.assertIsNone(run_hook({"hook_event_name": "PostToolUse", "tool_name": "Write",
                                                "tool_input": {"file_path": path}}))

    def test_draft_folders_and_configured_globs(self):
        self.assertTrue(article_rules.is_draft(r"R:\site\drafts\backup.md"))
        self.assertTrue(article_rules.is_draft("/home/u/site/blog/backup.html"))
        self.assertFalse(article_rules.is_draft(r"R:\site\drafts\README.md"))
        self.assertFalse(article_rules.is_draft(r"R:\site\drafts\backup.php"))
        with tempfile.TemporaryDirectory() as d:
            write(os.path.join(d, ".article-check.json"), '{"drafts": ["content/*.md"]}')
            self.assertTrue(article_rules.is_draft(os.path.join(d, "content", "guides", "dmarc.md")))
            self.assertFalse(article_rules.is_draft(os.path.join(d, "notes", "dmarc.md")))


if __name__ == "__main__":
    unittest.main()
