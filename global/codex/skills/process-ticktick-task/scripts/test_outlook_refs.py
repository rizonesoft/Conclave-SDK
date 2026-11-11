"""Tests for outlook_refs.py. Run: python -m unittest discover -s <skill>/scripts"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from outlook_refs import extract, to_graph_id

SCRIPT = Path(__file__).resolve().parent / "outlook_refs.py"

# A real task link and the id Graph returned for the same message (12 Oct 2026).
OWA_URL = (
    "https://outlook.office365.com/owa/?ItemID=AAMkADZhNzRmZWYxLTFiZWUtNGVhZS05YjUyLTNlNDI0ODc4ZDk1MgBGAAAAAABQmcncensqQIIY2Ov9gk90BwDg5T4IWR3uTaqX7BAF0M%2BEAAAAAAEMAADg5T4IWR3uTaqX7BAF0M%2BEAAm%2BawsoAAA%3D&exvsurl=1&viewmodel=ReadMessageItem"
)
GRAPH_ID = "AAMkADZhNzRmZWYxLTFiZWUtNGVhZS05YjUyLTNlNDI0ODc4ZDk1MgBGAAAAAABQmcncensqQIIY2Ov9gk90BwDg5T4IWR3uTaqX7BAF0M_EAAAAAAEMAADg5T4IWR3uTaqX7BAF0M_EAAm_awsoAAA="


class ToGraphIdTest(unittest.TestCase):
    def test_owa_encoded_id_becomes_graph_rest_id(self):
        raw = OWA_URL.split("ItemID=")[1].split("&")[0]
        self.assertEqual(to_graph_id(raw), GRAPH_ID)

    def test_slash_becomes_dash(self):
        self.assertEqual(to_graph_id("AB%2FCD%2BEF%3D"), "AB-CD_EF=")

    def test_graph_id_is_unchanged(self):
        self.assertEqual(to_graph_id(GRAPH_ID), GRAPH_ID)


class ExtractTest(unittest.TestCase):
    def test_owa_link_in_source_line(self):
        result = extract("Review the notice.\n\nSource: " + OWA_URL)
        self.assertEqual(result["messages"], [{"source": "owa", "graphId": GRAPH_ID, "uri": "mail:///messages/" + GRAPH_ID}])

    def test_several_links_keep_order_and_drop_duplicates(self):
        second = OWA_URL.replace("AAm%2BawsoAAA", "AAm8TNSqAAA")
        result = extract("Source:\n" + OWA_URL + "\n" + second + "\n" + OWA_URL)
        self.assertEqual([m["graphId"] for m in result["messages"]], [GRAPH_ID, GRAPH_ID.replace("AAm_awsoAAA", "AAm8TNSqAAA")])

    def test_deep_link_and_mail_uri(self):
        text = (
            "See https://outlook.office.com/mail/deeplink/read/AAMkAD%2Fxyz%3D?ItemID=AAMkAD%2Fxyz%3D&exvsurl=1 and "
            "https://outlook.office.com/mail/inbox/id/AAQkAbc%2B1 and mail:///messages/AAMkQQ%3D"
        )
        result = extract(text)
        self.assertEqual([(m["source"], m["graphId"]) for m in result["messages"]], [("owa", "AAMkAD-xyz="), ("deeplink", "AAQkAbc_1"), ("mail-uri", "AAMkQQ=")])

    def test_one_link_gives_one_message(self):
        url = "https://outlook.office.com/mail/deeplink/read/AAMkAD%2Fxyz%3D?ItemID=AAMkAD%2Fother%3D"
        self.assertEqual([m["graphId"] for m in extract(url)["messages"]], ["AAMkAD-other="])

    def test_outlook_key_and_headers(self):
        text = (
            "From: ssnyman@george.gov.za · 2025-02-06\n"
            "Subject: Re: Sean laptop pick up and check\n"
            "He asks about Brave. Outlook key AAkz3IjEAAA=. Kept in Inbox."
        )
        result = extract(text)
        self.assertEqual(result["keys"], ["AAkz3IjEAAA="])
        self.assertEqual(result["subjects"], ["Re: Sean laptop pick up and check"])
        self.assertEqual(result["senders"], ["ssnyman@george.gov.za · 2025-02-06"])
        self.assertEqual(result["addresses"], ["ssnyman@george.gov.za"])
        self.assertEqual(result["messages"], [])

    def test_addresses_are_unique_and_ordered(self):
        result = extract("alettae@jmrgroup.co.za, leratom@jmrgroup.co.za and alettae@jmrgroup.co.za")
        self.assertEqual(result["addresses"], ["alettae@jmrgroup.co.za", "leratom@jmrgroup.co.za"])

    def test_text_without_references(self):
        self.assertEqual(extract("Call the client."), {"messages": [], "keys": [], "subjects": [], "senders": [], "internetMessageIds": [], "addresses": []})

    def test_angle_bracket_address_is_not_a_message_id(self):
        text = "From: Carol-Ann <carolann@suregeorge.co.za>" + chr(10) + "Filed: internetMessageId <JN1PP@JN1PP.PROD.OUTLOOK.COM>, link"
        result = extract(text)
        self.assertEqual(result["internetMessageIds"], ["<JN1PP@JN1PP.PROD.OUTLOOK.COM>"])
        self.assertEqual(result["addresses"], ["carolann@suregeorge.co.za"])

    def test_internet_message_id_is_not_an_address(self):
        text = "Message ID: <E1xEGVg-B9zBpi9TsfV-HUUA@message-id.smtpcorp.com>" + chr(10) + "From: ticket@smtp2go.com"
        result = extract(text)
        self.assertEqual(result["internetMessageIds"], ["<E1xEGVg-B9zBpi9TsfV-HUUA@message-id.smtpcorp.com>"])
        self.assertEqual(result["addresses"], ["ticket@smtp2go.com"])


class CliTest(unittest.TestCase):
    def test_utf8_stdin_preserves_headers(self):
        text = 'Subject: R\u00e9sum\u00e9 \u0418\u0432\u0430\u043d\nFrom: Andr\u00e9 <andre@example.com>'
        run = subprocess.run([sys.executable, '-I', str(SCRIPT)], input=text, capture_output=True, text=True, check=True, encoding='utf-8')
        self.assertEqual(json.loads(run.stdout)['subjects'], ['R\u00e9sum\u00e9 \u0418\u0432\u0430\u043d'])

    def test_reads_stdin_and_prints_json(self):
        run = subprocess.run([sys.executable, "-I", str(SCRIPT)], input="Source: " + OWA_URL, capture_output=True, text=True, check=True, encoding="utf-8")
        self.assertEqual(json.loads(run.stdout)["messages"][0]["graphId"], GRAPH_ID)

    def test_reads_file_argument(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "task.txt"
            path.write_text("Outlook key AAkz3IjEAAA=.", encoding="utf-8")
            run = subprocess.run([sys.executable, "-I", str(SCRIPT), str(path)], capture_output=True, text=True, check=True, encoding="utf-8")
            self.assertEqual(json.loads(run.stdout)["keys"], ["AAkz3IjEAAA="])


if __name__ == "__main__":
    unittest.main()
