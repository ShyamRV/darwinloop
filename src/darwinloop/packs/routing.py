"""darwinloop packs/routing.py — Benchmark pack for intent routing / classification agents."""

from __future__ import annotations

from darwinloop._models import BenchmarkTask
from darwinloop.packs.base import BenchmarkPack


class RoutingPack(BenchmarkPack):
    """Benchmark pack for agents that classify/route user queries by intent.

    Tests basic routing, follow-up context (pronoun resolution), ambiguous
    phrasing, negation, and multi-turn conversations.

    Args:
        intents: List of intent names the agent should recognise
            (e.g. ``["live", "team", "competition", "fixtures"]``).
        test_cases: Optional override for the default test cases. Each dict
            must have ``"input"``, ``"expected"``, and optionally
            ``"must_not_contain"`` and ``"input_sequence"``.
    """

    def __init__(
        self,
        intents: list[str] | None = None,
        test_cases: list[dict] | None = None,
    ) -> None:
        self._intents = intents or []
        self._custom = test_cases

    @property
    def tasks(self) -> list[BenchmarkTask]:
        if self._custom:
            return [
                BenchmarkTask(
                    id=f"routing_{i:03d}",
                    name=tc.get("name", f"case_{i}"),
                    description=tc.get("description", ""),
                    input=tc.get("input", ""),
                    input_sequence=tc.get("input_sequence", []),
                    expected=tc.get("expected", ""),
                    must_not_contain=tc.get("must_not_contain", ""),
                )
                for i, tc in enumerate(self._custom)
            ]

        tasks: list[BenchmarkTask] = []

        # Basic single-turn routing for each declared intent
        _INTENT_PROBES: dict[str, str] = {
            "live": "What are the live scores right now?",
            "team": "Tell me about Arsenal FC",
            "competition": "Who won the Champions League final?",
            "fixtures": "Show me Liverpool's upcoming fixtures",
            "player": "What are Haaland's stats this season?",
            "league": "Show Premier League fixtures this week",
            "day": "What matches are on today?",
            "greeting": "Hello there",
        }

        for intent in self._intents:
            probe = _INTENT_PROBES.get(intent, f"query about {intent}")
            tasks.append(BenchmarkTask(
                id=f"routing_basic_{intent}",
                name=f"routes_{intent}",
                description=f"Query clearly about '{intent}' should route to '{intent}'",
                input=probe,
                expected=intent,
            ))

        # Universal follow-up / pronoun test (if "team" or "fixtures" in intents)
        if any(i in self._intents for i in ("team", "fixtures")):
            tasks.append(BenchmarkTask(
                id="routing_pronoun_followup",
                name="pronoun_followup",
                description="'When do they play next?' after team question should resolve to that team",
                input_sequence=["Tell me about Liverpool FC", "When do they play next?"],
                expected="fixture",
            ))

        # Ambiguous phrasing — "vs" should trigger competition not team
        tasks.append(BenchmarkTask(
            id="routing_vs_competition",
            name="vs_triggers_competition",
            description="'TeamA vs TeamB result' should route to competition, not team",
            input="Barcelona vs Real Madrid result",
            expected="competition",
            must_not_contain="team",
        ))

        return tasks
