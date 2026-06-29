"""
Example agent router — the TARGET file darwinloop will evolve.

This is a simplified version of the football-score-agent's router.py
for the quickstart demo. It has intentional gaps that darwinloop will fix:
- Missing team recognition for many clubs
- No pronoun (they/them) follow-up handling
- Competition vs team routing can be ambiguous
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RouterContext:
    last_team: Optional[str] = None
    last_intent: Optional[str] = None


@dataclass
class RouteResult:
    intent: str
    team: Optional[str] = None
    context_updated: bool = False


_KNOWN_TEAMS = [
    "arsenal", "chelsea", "liverpool", "manchester city", "manchester united",
    "tottenham", "barcelona", "real madrid", "bayern munich",
]

_GREETING_WORDS = ["hello", "hi", "hey", "good morning", "good evening"]


def route_question(question: str, ctx: RouterContext | None = None) -> RouteResult:
    """Route a user question to the appropriate intent."""
    ctx = ctx or RouterContext()
    q = question.lower().strip()

    # Greeting
    if any(g in q for g in _GREETING_WORDS):
        return RouteResult(intent="greeting")

    # Live scores
    if "live" in q or "right now" in q or "current score" in q:
        return RouteResult(intent="live")

    # Competition (vs match result)
    if " vs " in q or "result" in q:
        return RouteResult(intent="competition")

    # Fixtures / upcoming games
    if re.search(r"next match|next game|fixture|schedule|upcoming", q):
        return RouteResult(intent="team_fixtures")

    # Team info
    for team in _KNOWN_TEAMS:
        if team in q:
            ctx.last_team = team
            return RouteResult(intent="team", team=team)

    # Default
    return RouteResult(intent="competition")
