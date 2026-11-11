#!/usr/bin/env python3
"""Extract Outlook message references from a TickTick task's text.

Reads the task text from a file path argument or stdin and prints JSON:

  messages   Graph message ids from OWA links, Outlook deep links and
             mail:/// URIs, with legacy URIs retained as reference data
  keys       short "Outlook key" fragments (not readable; search instead)
  subjects   values of "Subject:" lines
  senders    values of "From:" lines
  internetMessageIds  permanent ids written after "Message ID:" or
             "internetMessageId", used to confirm a search hit (Outlook
             search cannot look them up)
  addresses  every other email address mentioned, in order

OWA links carry the EWS form of the id (URL-encoded, with "+" and "/").
Microsoft Graph uses the REST form, which swaps "+" for "_" and "/" for "-".
An id stops resolving once the message moves to another folder, so callers
fall back to searching by subject, sender and date.
"""

import json
import re
import sys
from urllib.parse import unquote

OUTLOOK_URL = re.compile(r"https?://outlook\.(?:office365|office|live)\.com/[^\s)\"'<>\]]+", re.IGNORECASE)
ITEM_ID_PARAM = re.compile(r"[?&]ItemID=([^&#]+)", re.IGNORECASE)
DEEP_LINK_PATH = re.compile(r"/mail/(?:deeplink/read|[^/?#]+/id)/([^?&#/]+)", re.IGNORECASE)
MAIL_URI = re.compile(r"mail:///messages/([^?\s)\"'<>\]]+)")
OUTLOOK_KEY = re.compile(r"Outlook key\s+([A-Za-z0-9+/_=-]+?)(?=[.,;)]?(?:\s|$))", re.IGNORECASE)
HEADER = re.compile(r"^\s*(From|Subject)\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
INTERNET_MESSAGE_ID = re.compile(r"(?:Message[ -]?ID|internetMessageId)\s*:?\s*(<[^<>\s@]+@[^<>\s]+>)", re.IGNORECASE)
ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def to_graph_id(raw: str) -> str:
    """Turn a URL-encoded EWS or REST item id into the Graph REST form."""
    return unquote(raw).replace("+", "_").replace("/", "-")


def _unique(values):
    seen = set()
    out = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def extract(text: str) -> dict:
    found = []
    for match in OUTLOOK_URL.finditer(text):
        url = match.group(0)
        item = ITEM_ID_PARAM.search(url)
        path = DEEP_LINK_PATH.search(url)
        if item:
            found.append((match.start(), "owa", to_graph_id(item.group(1))))
        elif path:
            found.append((match.start(), "deeplink", to_graph_id(path.group(1))))
    for match in MAIL_URI.finditer(text):
        found.append((match.start(), "mail-uri", to_graph_id(match.group(1))))
    found.sort()
    messages = []
    seen_ids = set()
    for _, source, graph_id in found:
        if graph_id not in seen_ids:
            seen_ids.add(graph_id)
            messages.append({"source": source, "graphId": graph_id, "uri": "mail:///messages/" + graph_id})

    headers = HEADER.findall(text)
    message_ids = _unique(INTERNET_MESSAGE_ID.findall(text))
    return {
        "messages": messages,
        "keys": _unique(OUTLOOK_KEY.findall(text)),
        "subjects": _unique(value for name, value in headers if name.lower() == "subject"),
        "senders": _unique(value for name, value in headers if name.lower() == "from"),
        "internetMessageIds": message_ids,
        "addresses": _unique(ADDRESS.findall(INTERNET_MESSAGE_ID.sub(" ", text))),
    }


def main(argv) -> int:
    if len(argv) > 1:
        with open(argv[1], encoding="utf-8") as handle:
            text = handle.read()
    else:
        sys.stdin.reconfigure(encoding="utf-8")
        text = sys.stdin.read()
    json.dump(extract(text), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
