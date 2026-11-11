"""Tests for mail_text.py. Run: python -m unittest discover -s <skill>/scripts"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mail_text import html_to_text, render

SCRIPT = Path(__file__).resolve().parent / "mail_text.py"

MESSAGE = {
    "id": "AAMkQQ=",
    "subject": "RE: Queue Error",
    "body": {
        "contentType": "html",
        "content": (
            "<html><head><style>p{color:red}</style></head><body>"
            "<div style=\"display:none\">Preheader text ͏ ­</div>"
            "<p>Hi Courtney,</p><p>This error was&nbsp;unrelated.<br>Regards</p>"
            "<table><tr><td>Order</td><td>27367</td></tr></table>"
            "<script>alert(1)</script></body></html>"
        ),
    },
    "sender": {"name": "Stock2Shop Support", "address": "support@stock2shop.com"},
    "toRecipients": [{"name": "Derick Payne", "address": "derick@rizonetech.com"}],
    "ccRecipients": [],
    "receivedDateTime": "2026-10-12T14:12:44Z",
    "isRead": True,
    "categories": [],
    "attachments": [{"name": "log.txt"}],
    "conversationId": "AAQkConv=",
    "internetMessageId": "<abc@example.com>",
    "parentFolderId": "inbox-id",
    "webLink": "https://outlook.office365.com/owa/?ItemID=AAMkQQ%3D",
}


class HtmlToTextTest(unittest.TestCase):
    def test_table_cells_remain_separate(self):
        self.assertEqual(html_to_text('<table><tr><td>Order</td><td>27367</td></tr></table>'), 'Order 27367')

    def test_drops_hidden_style_and_script(self):
        text = html_to_text(MESSAGE["body"]["content"])
        self.assertNotIn("Preheader", text)
        self.assertNotIn("color:red", text)
        self.assertNotIn("alert", text)

    def test_keeps_paragraphs_and_breaks(self):
        text = html_to_text(MESSAGE["body"]["content"])
        self.assertEqual(text.split("\n")[:4], ["Hi Courtney,", "", "This error was unrelated.", "Regards"])

    def test_void_tags_do_not_hide_following_text(self):
        self.assertEqual(html_to_text('<div><img src="x"><span>Shown</span></div>'), "Shown")

    def test_unclosed_hidden_element_ends_with_its_parent(self):
        self.assertEqual(html_to_text('<div><div style="display:none">Hidden</div></div><p>Shown</p>'), "Shown")


class RenderTest(unittest.TestCase):
    def test_connector_snake_case_and_wrapper(self):
        message = dict(MESSAGE)
        for old, new in [('internetMessageId', 'internet_message_id'), ('conversationId', 'conversation_id'), ('parentFolderId', 'parent_folder_id'), ('webLink', 'web_link')]:
            message[new] = message.pop(old)
        out = render({'structuredContent': {'value': {message['id']: message}}}, 20000)
        self.assertIn('Internet message id: <abc@example.com>', out)
        self.assertIn('Folder id: inbox-id', out)
        self.assertIn('Link: https://outlook.', out)

    def test_single_message_list_and_mcp_text(self):
        wrapped = {'content': [{'type': 'text', 'text': json.dumps({'value': [MESSAGE]})}]}
        self.assertIn('Subject: RE: Queue Error', render(wrapped, 20000))

    def test_missing_identity_is_explicit(self):
        out = render({'subject': 'Test', 'body': {'contentType': 'text', 'content': 'Hello'}}, 100)
        self.assertIn('Internet message id: null', out)
        self.assertIn('Conversation id: null', out)
        self.assertIn('Folder id: null', out)

    def test_rejects_multiple_messages_and_error(self):
        for value in ({'value': [MESSAGE, MESSAGE]}, {'error': 'unavailable'}, {'value': []}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                render(value, 100)

    def test_negative_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            render(MESSAGE, -1)

    def test_headers_for_triage(self):
        out = render(MESSAGE, 20000)
        self.assertIn("Subject: RE: Queue Error", out)
        self.assertIn("From: Stock2Shop Support <support@stock2shop.com>", out)
        self.assertIn("To: Derick Payne <derick@rizonetech.com>", out)
        self.assertIn("Internet message id: <abc@example.com>", out)
        self.assertIn("Attachments: log.txt", out)
        self.assertNotIn("Cc:", out)
        self.assertNotIn("Categories:", out)

    def test_plain_text_body(self):
        message = dict(MESSAGE, body={"contentType": "text", "content": "Line one\r\n\r\n\r\nLine two"})
        self.assertTrue(render(message, 20000).endswith("Line one\n\nLine two\n"))

    def test_cuts_long_body(self):
        message = dict(MESSAGE, body={"contentType": "text", "content": "x" * 50})
        self.assertIn("x" * 10 + "\n[body cut at 10 of 50 characters]", render(message, 10))


class CliTest(unittest.TestCase):
    def test_utf8_stdin(self):
        message = dict(MESSAGE, subject='R\u00e9sum\u00e9 \u0418\u0432\u0430\u043d')
        run = subprocess.run([sys.executable, '-I', str(SCRIPT)], input=json.dumps(message, ensure_ascii=False), capture_output=True, text=True, check=True, encoding='utf-8')
        self.assertIn(message['subject'], run.stdout)

    def test_reads_saved_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.txt"
            path.write_text(json.dumps(MESSAGE), encoding="utf-8")
            run = subprocess.run([sys.executable, "-I", str(SCRIPT), str(path)], capture_output=True, text=True, check=True, encoding="utf-8")
        self.assertIn("Subject: RE: Queue Error", run.stdout)
        self.assertIn("This error was unrelated.", run.stdout)

    def test_reads_stdin(self):
        run = subprocess.run([sys.executable, "-I", str(SCRIPT), "--max-chars", "5"], input=json.dumps(MESSAGE), capture_output=True, text=True, check=True, encoding="utf-8")
        self.assertIn("[body cut at 5 of", run.stdout)


if __name__ == "__main__":
    unittest.main()
