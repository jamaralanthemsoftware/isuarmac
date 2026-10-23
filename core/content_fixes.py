"""Spelling and wording corrections applied to all imported text. Edit content_fixes.json, then re-run the import."""
import json
import re
from functools import lru_cache
from pathlib import Path

FIXES_FILE = Path(__file__).with_name("content_fixes.json")
SPACE_BEFORE_PUNCT = re.compile(r"(?<=[\w’”)%]) +(?=[,.;:!?](?:\s|$))")
LEADING_SPACE_PUNCT = re.compile(r"^ +(?=[,.;:!?](?:\s|$))")


@lru_cache(maxsize=1)
def _rules():
    if not FIXES_FILE.exists():
        return []
    data = json.loads(FIXES_FILE.read_text())
    rules = []
    for wrong, right in data.get("words", {}).items():
        rules.append((re.compile(rf"(?<![\w/.-]){re.escape(wrong)}(?![\w/-])"), right))
    for wrong, right in data.get("phrases", {}).items():
        rules.append((re.compile(re.escape(wrong)), right))
    return rules


@lru_cache(maxsize=1)
def _brand_rules():
    if not FIXES_FILE.exists():
        return []
    data = json.loads(FIXES_FILE.read_text())
    # Not inside email addresses or URLs (preceded/followed by @ . / -).
    return [(re.compile(rf"(?<![\w@./-]){re.escape(w)}(?![\w@/-])"), r) for w, r in data.get("brand", {}).items()]


@lru_cache(maxsize=1)
def _page_fixes():
    if not FIXES_FILE.exists():
        return {}
    by_url = {}
    for item in json.loads(FIXES_FILE.read_text()).get("page_fixes", []):
        by_url.setdefault(item["url"], []).append((item["find"], item["replace"]))
    return by_url


APPLIED = set()  # (url, find) pairs that matched during this run; used to report misses


def apply_page_fixes(text, url):
    """Exact find/replace corrections from the proofreading review, scoped to one page."""
    if not text or not url:
        return text
    for find, replace in _page_fixes().get(url, []):
        if find in text:
            text = text.replace(find, replace)
            APPLIED.add((url, find))
            continue
        # The reviewer saw plain text; in HTML the same words may be split by inline tags or extra spaces.
        gap = r"(?:\s|&nbsp;|<[^>]+>)*"
        pattern = gap.join(re.escape(tok) for tok in re.findall(r"\w+|[^\w\s]", find))
        new, n = re.subn(pattern, lambda m: replace, text)
        if n:
            text = new
            APPLIED.add((url, find))
    return text


def unapplied_page_fixes():
    return [(u, f) for u, fixes in _page_fixes().items() for f, _ in fixes if (u, f) not in APPLIED]


def apply_fixes(text, url=None, brand=True):
    """Apply corrections to text or HTML. Rules never match inside tags or URLs (they skip text inside <...>)."""
    if not text:
        return text
    text = apply_page_fixes(text, url)
    rules = _rules() + (_brand_rules() if brand else [])
    if not rules:
        return text
    parts = re.split(r"(<[^>]+>)", text)
    # stray space before punctuation ("word , next" / "</a> .")
    for i, part in enumerate(parts):
        if part.startswith("<"):
            continue
        for pattern, right in rules:
            part = pattern.sub(right, part)
        part = SPACE_BEFORE_PUNCT.sub("", part)
        if i > 0 and parts[i - 1].startswith("</"):
            part = LEADING_SPACE_PUNCT.sub("", part)
        parts[i] = part
    return "".join(parts)
