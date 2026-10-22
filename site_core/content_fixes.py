"""Spelling and wording corrections applied to all imported text. Edit content_fixes.json, then re-run the import."""
import json
import re
from functools import lru_cache
from pathlib import Path

FIXES_FILE = Path(__file__).with_name("content_fixes.json")


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


def apply_fixes(text):
    """Apply corrections to text or HTML. Rules never match inside tags or URLs (they skip text inside <...>)."""
    if not text:
        return text
    rules = _rules()
    if not rules:
        return text
    parts = re.split(r"(<[^>]+>)", text)
    for i, part in enumerate(parts):
        if part.startswith("<"):
            continue
        for pattern, right in rules:
            part = pattern.sub(right, part)
        parts[i] = part
    return "".join(parts)
