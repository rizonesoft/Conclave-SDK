#!/usr/bin/env python3
"""Print an Outlook connector message as headers and plain text.

Save oversized connector output as JSON outside Git and pass the file
(or pipe UTF-8 JSON on stdin):

  python mail_text.py <saved-result.txt> [--max-chars N]

Prints the headers that matter for triage and filing, then the body as
text: tags removed, hidden preheaders, styles and scripts dropped, blank
runs collapsed. The body is cut at --max-chars (default 20000) with a note.
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser

BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "hr", "blockquote", "pre"}
SKIP_TAGS = {"style", "script", "head", "title"}
HIDDEN_STYLE = re.compile(r"display\s*:\s*none", re.IGNORECASE)
VOID_TAGS = {"br", "hr", "img", "meta", "link", "input", "col", "area", "base", "wbr", "source"}


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []  # (tag, hides) for open elements

    def _hidden(self):
        return any(hides for _, hides in self.stack)

    def handle_starttag(self, tag, attrs):
        if tag in {"td", "th"}:
            self.parts.append(" ")
        if tag in BLOCK_TAGS:
            self.parts.append("\n")
        if tag in VOID_TAGS:
            return
        style = dict(attrs).get("style") or ""
        self.stack.append((tag, tag in SKIP_TAGS or bool(HIDDEN_STYLE.search(style))))

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._hidden():
            self.parts.append(data)


INVISIBLE = re.compile("[­͏​-‏⁠﻿]")


def html_to_text(markup: str) -> str:
    parser = _TextParser()
    parser.feed(markup)
    parser.close()
    return tidy("".join(parser.parts))


def tidy(text: str) -> str:
    text = INVISIBLE.sub("", text.replace("\r\n", "\n").replace("\xa0", " "))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    out = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def _address(entry) -> str:
    box = (entry or {}).get("emailAddress", entry) or {}
    name, address = box.get("name") or "", box.get("address") or ""
    return f"{name} <{address}>" if name and name != address else address


def unwrap(message):
    """Accept one message, never silently select among multiple messages."""
    for _ in range(8):
        if not isinstance(message, dict) or message.get('isError') or message.get('error'):
            raise ValueError('Expected a successful single-message connector result')
        if any(key in message for key in ('body', 'subject', 'sender')):
            return message
        if 'structuredContent' in message:
            message = message['structuredContent']
        elif 'value' in message:
            value = message['value']
            values = list(value.values()) if isinstance(value, dict) else value
            if not isinstance(values, list) or len(values) != 1:
                raise ValueError('Select exactly one message before rendering')
            message = values[0]
        elif isinstance(message.get('content'), list):
            texts = [part['text'] for part in message['content'] if part.get('type') == 'text']
            if len(texts) != 1:
                raise ValueError('Expected exactly one JSON text result')
            message = json.loads(texts[0])
        else:
            raise ValueError('No message found in connector result')
    raise ValueError('Connector result nesting is too deep')


def render(message: dict, max_chars: int) -> str:
    if max_chars < 0:
        raise ValueError('max_chars must be non-negative')
    message = unwrap(message)
    body = message.get("body") or {}
    content = body.get("content") or ""
    text = html_to_text(content) if (body.get("contentType") or "").lower() == "html" else tidy(content)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + f"\n[body cut at {max_chars} of {len(text)} characters]"
    attachments = [a.get("name") or "?" for a in message.get("attachments") or []]
    headers = [
        ("Subject", message.get("subject")),
        ("From", _address(message.get("sender"))),
        ("To", ", ".join(_address(r) for r in message.get("toRecipients") or [])),
        ("Cc", ", ".join(_address(r) for r in message.get("ccRecipients") or [])),
        ("Received", message.get("receivedDateTime")),
        ("Read", message.get("isRead")),
        ("Categories", ", ".join(message.get("categories") or [])),
        ("Attachments", ", ".join(attachments)),
        ("Graph id", message.get("id")),
        ("Conversation id", message.get("conversationId") or message.get("conversation_id") or "null"),
        ("Internet message id", message.get("internetMessageId") or message.get("internet_message_id") or "null"),
        ("Folder id", message.get("parentFolderId") or message.get("parent_folder_id") or "null"),
        ("Link", message.get("webLink") or message.get("web_link") or "null"),
    ]
    head = "\n".join(f"{name}: {value}" for name, value in headers if value not in (None, ""))
    return head + "\n\n" + text + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="?", help="saved connector JSON; UTF-8 stdin when omitted")
    parser.add_argument("--max-chars", type=int, default=20000)
    args = parser.parse_args(argv)
    if args.path:
        with open(args.path, encoding="utf-8") as handle:
            raw = handle.read()
    else:
        sys.stdin.reconfigure(encoding="utf-8")
        raw = sys.stdin.read()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(render(json.loads(raw), args.max_chars))
    return 0


if __name__ == "__main__":
    sys.exit(main())
