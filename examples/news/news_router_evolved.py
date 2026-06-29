"""
news_router.py — Self-contained headline routing logic extracted from news-agent.

This is the TARGET FILE that darwinloop will evolve.
It contains the pure logic functions from ai/headline_store.py,
stripped of DB/async calls so they can be benchmarked in a sandbox.

Known gaps darwinloop should fix:
1. Ordinals capped at 5 — "sixth", "seventh" etc. not recognised
2. _DIGIT_RE only matches [1-5] — "story 7" or "headline 9" fails
3. _FOLLOW_UP_RE misses: "summarize", "read more", "what happened with", "elaborate on"
4. is_follow_up_request too strict — misses many natural phrasings
"""

from __future__ import annotations

import re

# ── Ordinal word map ──────────────────────────────────────────────────────────

_ORDINAL_WORDS: dict[str, int] = {
    "first": 1,
    "1st": 1,
    "one": 1,
    "second": 2,
    "2nd": 2,
    "two": 2,
    "third": 3,
    "3rd": 3,
    "three": 3,
    "fourth": 4,
    "4th": 4,
    "four": 4,
    "fifth": 5,
    "5th": 5,
    "five": 5,
    "sixth": 6,
    "6th": 6,
    "six": 6,
    "seventh": 7,
    "7th": 7,
    "seven": 7,
    "eighth": 8,
    "8th": 8,
    "eight": 8,
    "ninth": 9,
    "9th": 9,
    "nine": 9,
    "tenth": 10,
    "10th": 10,
    "ten": 10,
}

# ── Regex patterns ────────────────────────────────────────────────────────────

_FOLLOW_UP_RE = re.compile(
    r"\b("
    r"go\s+deeper|more\s+on|more\s+about|tell\s+me\s+more|expand\s+on|details\s+on|"
    r"elaborate|dive\s+into|explain\s+the"
    r")\b",
    re.IGNORECASE,
)

_ORDINAL_RE = re.compile(
    r"\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th|seventh|7th|eighth|8th|ninth|9th|tenth|10th|one|two|three|four|five|six|seven|eight|nine|ten)\b",
    re.IGNORECASE,
)

_DIGIT_RE = re.compile(
    r"\b(?:headline|news|story|article|item)?\s*#?\s*([0-9])\b",
    re.IGNORECASE,
)

# ── Public API ────────────────────────────────────────────────────────────────

def parse_headline_position(text: str) -> int | None:
    """Return 1-based headline index from user text, or None.

    Examples:
        "go deeper on the second one"  → 2
        "tell me more about headline 3" → 3
        "show me story 7"              → None  (KNOWN GAP: only handles 1-5)
        "elaborate on the sixth"       → None  (KNOWN GAP: sixth not in ordinals)
    """
    lower = text.lower().strip()
    if not _FOLLOW_UP_RE.search(lower) and "headline" not in lower and "news" not in lower:
        if not _ORDINAL_RE.search(lower):
            return None

    digit = _DIGIT_RE.search(lower)
    if digit:
        return int(digit.group(1))

    for match in _ORDINAL_RE.finditer(lower):
        word = match.group(1).lower()
        if word in _ORDINAL_WORDS:
            return _ORDINAL_WORDS[word]
    return None


def is_follow_up_request(text: str) -> bool:
    """Return True if the message is a follow-up about a specific headline.

    Examples:
        "go deeper on the first one"  → True
        "summarize headline 2"        → False (KNOWN GAP: 'summarize' not in regex)
        "read more about story 3"     → False (KNOWN GAP: 'read more' not matched)
        "what happened with number 1" → False (KNOWN GAP: 'what happened with' missing)
        "show me more details"        → False (KNOWN GAP: 'show me more' not matched)
    """
    lower = text.lower()
    return bool(_FOLLOW_UP_RE.search(lower)) or (
        parse_headline_position(text) is not None
        and ("news" in lower or "headline" in lower or "story" in lower)
    )


def run(question: str) -> str:
    """Darwinloop entry point — routes question through both functions.

    Returns:
        The detected position as a string (e.g. "3"), "True" if is_follow_up_request,
        or "None" if neither applies.
    """
    pos = parse_headline_position(question)
    if pos is not None:
        return str(pos)
    if is_follow_up_request(question):
        return "True"
    return "None"


def augment_message(user_message: str, headlines: list[dict], position: int | None = None) -> str:
    """Inject exact headline context into the user message for LLM accuracy.

    Args:
        user_message: Original user message.
        headlines: List of headline dicts with 'position', 'title', 'url'.
        position: Override position (if None, auto-detected from message).

    Returns:
        Augmented message string, or original if no matching headline found.
    """
    pos = position or parse_headline_position(user_message)
    if pos is None:
        return user_message
    if not headlines:
        return user_message

    pick = next((h for h in headlines if h.get("position") == pos), None)
    if not pick and 1 <= pos <= len(headlines):
        pick = headlines[pos - 1]
    if not pick:
        return user_message

    title = pick.get("title", "")
    url = pick.get("url", "")
    return (
        f"{user_message.strip()}\n\n"
        f"[Session context: User selected headline #{pos}. "
        f"Title: {title!r}. URL: {url}. "
        f"Call go_deeper_on_headline(position={pos}) with this exact title and url.]"
    )
