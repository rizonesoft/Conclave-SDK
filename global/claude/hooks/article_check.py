#!/usr/bin/env python3
"""Check an article against the owner's writing rules before it is written back or published.

    python article_check.py draft.md            # a Markdown, HTML or plain-text draft
    python article_check.py --post 16650        # a WordPress post, through the repository's WP-CLI command
    python article_check.py --json draft.html   # machine-readable report
    cat draft.md | python article_check.py -    # standard input

Owner rules (section 10 of the global rules in R:\\Claude\\rules), for every article written or rewritten:
1. Natural language (NLP): written the way people speak and search: short, clear sentences in the
   active voice, the answer first, question-shaped headings, and no stock AI phrasing.
2. Original value: unique insight, first-hand experience and accurate, specific facts that generic
   AI text misses.
3. E-E-A-T: the article shows Experience, Expertise, Authoritativeness and Trustworthiness: a named
   author, first-hand detail, sources for claims, and a review date.
4. No line saying AI assisted with or wrote the article.

A script cannot judge truth or insight, so the checks are floors, not a verdict: FAIL means a rule is
visibly broken; WARN means a human should look. Exit 1 on any FAIL. Runs unchanged on Windows and WSL;
drafts are read as UTF-8 whatever the platform's default encoding is.

Site-specific settings live in the repository, in `.article-check.json` at or above the draft (all keys optional):

    {
      "own_domains": ["example.com"],     links to these do not count as external sources
      "authors": ["Jane Smith"],          names that count as a named author
      "currencies": ["R"],                currency prefixes counted as specific figures, besides $, EUR and GBP signs
      "units": ["mailboxes"],             extra units counted as specific figures
      "wp": "bin/wp-launch",              WP-CLI command for --post (default: wp)
      "drafts": ["content/*.md"]          files the hook treats as drafts, besides drafts/, articles/, posts/, blog/
    }
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONFIG_NAME = '.article-check.json'

# Phrases that almost only machine text uses: FAIL.
STOCK_STRONG = [
    "in today's digital landscape", "in today's fast-paced", "in the ever-evolving", "ever-changing landscape",
    "delve", "delves", "delving", "tapestry", "unlock the power", "harness the power", "navigate the complexities",
    "a testament to", "in this article, we will", "without further ado", "treasure trove", "plethora", "myriad of",
    "embark on", "look no further", "supercharge", "unleash", "revolutionize", "revolutionise",
]
# Ordinary English that machine text overuses: WARN, so a writer can keep one that earns its place.
STOCK_COMMON = [
    "it's important to note", "it is important to note", "it's worth noting", "it is worth noting", "in conclusion",
    "game-changer", "game changer", "seamlessly", "cutting-edge", "elevate your", "whether you're a",
    "in this blog post", "at the end of the day", "the world of", "realm of", "dive into", "let's dive",
    "robust solution", "leverage the",
]
# Signals of first-hand experience (Experience in E-E-A-T, and original value).
FIRST_HAND = re.compile(
    r"\b(I|I've|I'm|I'd|we|we've|we're|our|my|me)\b[^.?!]{0,80}\b(tested|found|saw|see|set up|configured|migrated|"
    r"built|fixed|ran|run|recommend|measured|learned|learnt|use|used|install|installed|moved|checked|advise|work|worked|handle|handled)\b"
    r"|\b(in (my|our) experience|a client|one client|clients (often|usually|ask)|on a recent|last (month|year|week)|"
    r"we tested|I tested|in practice|a mistake (I|we) see|the mistake (I|we) see)\b", re.I)
UNITS = ['%', 'percent', 'KB', 'MB', 'GB', 'TB', 'ms', 'seconds?', 'minutes?', 'hours?', 'days?', 'weeks?', 'months?',
         'years?', 'users?', 'people', 'customers?', 'employees?', 'pages?', 'visitors?']
CURRENCIES = ['$', '\u20ac', '\u00a3']
PASSIVE = re.compile(r"\b(is|are|was|were|be|been|being)\s+(\w+ly\s+)?\w+(ed|en)\b", re.I)
BYLINE = re.compile(r"\b[Bb]y [A-Z][a-z]+ [A-Z][a-z]+\b|^author:\s*\S", re.M)
REVIEWED = re.compile(r"\b(last (reviewed|updated|checked)|reviewed on|updated on)\b", re.I)
# A line telling readers AI helped write the article. Matched only in disclosure shapes, so an article about AI
# tools can still name them.
_AI = r"(AI|artificial intelligence|ChatGPT|Claude|Gemini|Copilot|(a |an )?(large )?language model)"
DISCLOSURE = re.compile(
    r"\b(this|the) (article|post|guide|piece|content|text|page)\b[^.?!]{0,60}\b(written|drafted|created|generated|produced|"
    r"assisted|edited)\b[^.?!]{0,30}\b" + _AI + r"\b"
    r"|\b(written|drafted|created|generated|produced|edited)\s+(with|by|using)\s+(the\s+(help|assistance)\s+of\s+)?"
    r"(an?\s+)?" + _AI + r"\b"
    r"|\b" + _AI + r"[- ]assisted (article|post|guide|writing|draft)\b", re.I)


def load_config(start):
    """The nearest .article-check.json at or above `start`, and the directory it was found in."""
    path = Path(start).resolve()
    for folder in [path, *path.parents] if path.is_dir() else [*path.parents]:
        candidate = folder / CONFIG_NAME
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding='utf-8')), folder
    return {}, None


def fetch_post(post_id, wp):
    out = subprocess.run([wp, 'post', 'get', str(post_id), '--format=json', '--fields=post_title,post_content,post_author'],
                         capture_output=True, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL, check=True).stdout
    data = json.JSONDecoder().raw_decode(out[out.index('{'):])[0]
    # Read the name as JSON too: WP-CLI can print a plugin's PHP notices after the answer, so the last line of plain
    # output is not the name.
    who = subprocess.run([wp, 'user', 'get', str(data['post_author']), '--fields=display_name', '--format=json'],
                         capture_output=True, text=True, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL).stdout
    author = json.JSONDecoder().raw_decode(who[who.index('{'):])[0].get('display_name', '') if '{' in who else ''
    # The post body carries no byline or date; the theme prints the author box and the modified date.
    return f"# {data['post_title']}\n\nBy {author}\n\n{data['post_content']}", True


def parse(raw):
    """Split a draft into headings, paragraphs, links and plain body text."""
    text = re.sub(r'```.*?```', ' ', raw, flags=re.S)                      # fenced code
    text = re.sub(r'<(script|style|pre|code)\b.*?</\1>', ' ', text, flags=re.S | re.I)
    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.S)                   # block comments
    links = re.findall(r'href="(https?://[^"]+)"', text) + re.findall(r'\]\((https?://[^)\s]+)\)', text)
    headings = [html.unescape(re.sub(r'<[^>]+>', '', h)).strip() for h in re.findall(r'<h[2-4][^>]*>(.*?)</h[2-4]>', text, re.S | re.I)]
    headings += [h.strip() for h in re.findall(r'^#{2,4}\s+(.+)$', text, re.M)]
    text = re.sub(r'<(p|li|h[1-6]|tr|div|br)\b[^>]*>', '\n\n', text, flags=re.I)
    text = html.unescape(re.sub(r'<[^>]+>', ' ', text))
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)                  # Markdown links keep their words
    text = re.sub(r'^\s*(#{1,6}|[-*+]|\d+\.)\s+', '', text, flags=re.M)
    text = re.sub(r'[*_`>|]', ' ', text)
    paragraphs = [re.sub(r'\s+', ' ', p).strip() for p in re.split(r'\n\s*\n', text)]
    return [p for p in paragraphs if p], headings, links


def prose_dashes(raw):
    """Em and en dashes the writer used as punctuation. Quotes keep their dashes and numeric ranges take an en dash."""
    text = re.sub(r'<blockquote\b.*?</blockquote>', ' ', raw, flags=re.S | re.I)
    text = re.sub(r'<q\b.*?</q>', ' ', text, flags=re.S | re.I)
    text = re.sub(r'^\s*>.*$', ' ', text, flags=re.M)                     # Markdown blockquotes
    text = re.sub(r'`[^`\n]*`', ' ', text)                                # inline code
    body = ' '.join(parse(text)[0])
    body = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', ' ', body)           # quoted words
    body = re.sub(r'(?<=\d)\s?\u2013\s?(?=\d)', '', body)                 # 2026-2027 written with an en dash
    return len(re.findall('[\u2013\u2014]', body))


def sentences(paragraphs):
    out = []
    for p in paragraphs:
        out += [s.strip() for s in re.split(r'(?<=[.?!])\s+(?=[A-Z0-9"\u201c(])', p) if len(s.split()) >= 3]
    return out


def found(phrases, lower):
    return sorted({p for p in phrases if re.search(r'(?<![a-z])' + re.escape(p) + r'(?![a-z])', lower)})


def check(raw, from_post=False, config=None):
    config = config or {}
    paragraphs, headings, links = parse(raw)
    body = ' '.join(paragraphs)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019.-]*", body)
    sents = sentences(paragraphs)
    lengths = [len(s.split()) for s in sents] or [0]
    avg = sum(lengths) / len(lengths)
    long_share = sum(n > 30 for n in lengths) / len(lengths)
    passive_share = sum(bool(PASSIVE.search(s)) for s in sents) / max(len(sents), 1)
    lower = body.lower()
    strong, common = found(STOCK_STRONG, lower), found(STOCK_COMMON, lower)
    first_hand = FIRST_HAND.findall(body)
    currencies = '|'.join(re.escape(c) for c in CURRENCIES + config.get('currencies', []))
    units = '|'.join(UNITS + [re.escape(u) for u in config.get('units', [])])
    specific = re.compile(r'(?<!\w)(' + currencies + r')\s?\d[\d ,.]*|\b\d+(?:[.,]\d+)?\s?(' + units + r')(?!\w)|\b(19|20)\d{2}\b', re.I)
    specifics = specific.findall(body)
    own = [d.lower() for d in config.get('own_domains', [])]
    external = [u for u in links if not any(d in u.lower() for d in own)]
    questions = [h for h in headings if h.rstrip().endswith('?')]
    names = [re.escape(n) for n in config.get('authors', [])]
    author = BYLINE.search(raw) or (names and re.search(r'\b(' + '|'.join(names) + r')\b', raw))
    # The answer-first paragraph: the first real paragraph after the title and any byline. The title is skipped by its
    # text, since a long title has 15 words or more too.
    title = re.search(r'^#\s+(.+)$', raw, re.M) or re.search(r'<h1\b[^>]*>(.*?)</h1>', raw, re.S | re.I)
    title = parse(title.group(1))[0] if title else []
    opening = next((p for p in paragraphs if len(p.split()) >= 15 and p not in title), '')
    results = []

    def add(rule, status, detail):
        results.append({'rule': rule, 'status': status, 'detail': detail})

    # Natural language.
    add('nlp: sentence length', 'FAIL' if avg > 24 else 'WARN' if avg > 20 else 'PASS', f'average {avg:.1f} words per sentence (aim for 20 or fewer)')
    add('nlp: long sentences', 'WARN' if long_share > 0.1 else 'PASS', f'{long_share:.0%} of sentences over 30 words (aim for 10% or fewer)')
    add('nlp: active voice', 'WARN' if passive_share > 0.15 else 'PASS', f'{passive_share:.0%} of sentences look passive (aim for 15% or fewer)')
    add('nlp: stock AI phrasing', 'FAIL' if strong else 'PASS', ', '.join(strong) if strong else 'none found')
    add('nlp: overused phrasing', 'WARN' if common else 'PASS', ', '.join(common) if common else 'none found')
    dashes = prose_dashes(raw)
    add('nlp: em and en dashes', 'FAIL' if dashes else 'PASS', f'{dashes} used as punctuation' if dashes else 'none')
    open_n = len(opening.split())
    add('nlp: answer first', 'PASS' if 40 <= open_n <= 60 else 'WARN', f'opening paragraph is {open_n} words (aim for a 40 to 60 word direct answer)')
    add('nlp: question headings', 'PASS' if questions else 'WARN', f'{len(questions)} of {len(headings)} headings are questions readers ask')
    # Original value.
    add('original: first-hand experience', 'PASS' if first_hand else 'WARN',
        f'{len(first_hand)} first-hand passages' if first_hand else 'no first-hand experience found (what did you see, test, fix or measure?)')
    add('original: specific facts', 'PASS' if len(specifics) >= 3 else 'WARN', f'{len(specifics)} specific figures, prices, dates or quantities (aim for 3 or more)')
    # E-E-A-T.
    add('eeat: named author', 'PASS' if author else 'WARN', 'author named' if author else 'no named author in the draft (confirm the site prints one)')
    needs_sources = bool(re.search(r'\d+(?:[.,]\d+)?\s?(%|percent)', body)) or len(specifics) >= 3
    add('eeat: sources', 'PASS' if external else 'FAIL' if needs_sources else 'WARN',
        f'{len(external)} external source links' if external else 'no external source links for the facts and figures')
    disclosure = DISCLOSURE.search(body)
    add('eeat: no AI disclosure line', 'FAIL' if disclosure else 'PASS', f'"{disclosure.group(0)}"' if disclosure else 'none')
    reviewed = REVIEWED.search(raw)
    add('eeat: review date', 'PASS' if reviewed or from_post else 'WARN',
        'review date present' if reviewed else 'the theme prints the modified date' if from_post else 'no "last reviewed" date')
    return {'words': len(words), 'results': results, 'failed': sum(r['status'] == 'FAIL' for r in results),
            'warned': sum(r['status'] == 'WARN' for r in results)}


def main(argv=None):
    # Windows consoles default to a legacy code page; a quoted disclosure line or stock phrase must still print.
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('source', nargs='?', help='draft file (.md, .html, .txt) or - for standard input')
    parser.add_argument('--post', help='WordPress post id')
    parser.add_argument('--wp', help=f'WP-CLI command for --post (default: "wp" in {CONFIG_NAME}, else wp)')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    from_file = args.source and args.source != '-'
    config, _ = load_config(args.source if from_file else os.getcwd())
    if args.post:
        raw, from_post = fetch_post(args.post, args.wp or config.get('wp', 'wp'))
    elif args.source == '-':
        raw, from_post = sys.stdin.read(), False
    elif args.source:
        raw, from_post = Path(args.source).read_text(encoding='utf-8'), False
    else:
        parser.error('give a draft file, - or --post ID')
    report = check(raw, from_post, config)
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        for r in report['results']:
            print(f"{r['status']:4}  {r['rule']}: {r['detail']}")
        print(f"article-check: {'FAIL' if report['failed'] else 'ok'} ({report['failed']} failed, {report['warned']} to review)")
    return 1 if report['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
