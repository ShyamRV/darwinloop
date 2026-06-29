"""
Football agent router benchmark tasks.

These are the real benchmarks used to evolve the football-score-agent's router.py
using darwinloop. The base agent scored ~0.51; after 5 iterations it reached ~0.80.

Usage:
    darwinloop evolve examples/football/football_router.py \\
        --tasks examples/football/benchmarks.py \\
        --iterations 5 --model asi1
"""

from darwinloop import BenchmarkTask

TASKS = [
    # ── Basic intent routing ──────────────────────────────────────────────────
    BenchmarkTask(
        id="f01_live_scores",
        name="routes_live_scores",
        description="Query about live scores should route to 'live' intent",
        input="What are the live scores right now?",
        expected="live",
    ),
    BenchmarkTask(
        id="f02_known_team",
        name="routes_known_team",
        description="Query about Arsenal should route to 'team' intent",
        input="Tell me about Arsenal",
        expected="team",
    ),
    BenchmarkTask(
        id="f03_competition_vs",
        name="vs_triggers_competition",
        description="'vs' keyword should route to competition, not team",
        input="Napoli vs Inter result",
        expected="competition",
        must_not_contain="team",
    ),
    BenchmarkTask(
        id="f04_fixtures",
        name="routes_fixtures",
        description="'next game' query should route to team_fixtures",
        input="Arsenal next game",
        expected="fixture",
    ),
    # ── Team name coverage ────────────────────────────────────────────────────
    BenchmarkTask(
        id="f05_italian_team",
        name="recognises_italian_team",
        description="Napoli is an Italian club and should be recognised as a team",
        input="Tell me about Napoli",
        expected="team",
    ),
    BenchmarkTask(
        id="f06_german_team",
        name="recognises_german_team",
        description="Borussia Dortmund should be recognised as a team",
        input="Borussia Dortmund form this season",
        expected="team",
    ),
    BenchmarkTask(
        id="f07_spanish_team",
        name="recognises_atletico",
        description="Atletico Madrid should be recognised as a team",
        input="Atletico Madrid vs Barcelona last night",
        expected="competition",
    ),
    # ── Context / follow-up ───────────────────────────────────────────────────
    BenchmarkTask(
        id="f08_pronoun_they",
        name="pronoun_they_resolves",
        description="'When do they play next?' after team query should resolve via context",
        input_sequence=[
            "Tell me about Liverpool",
            "When do they play next?",
        ],
        expected="fixture",
    ),
    BenchmarkTask(
        id="f09_pronoun_their",
        name="pronoun_their_resolves",
        description="'their next match' after team query should use last team",
        input_sequence=[
            "Chelsea stats this season",
            "What about their next match?",
        ],
        expected="fixture",
    ),
    # ── Edge cases ────────────────────────────────────────────────────────────
    BenchmarkTask(
        id="f10_date_routing",
        name="today_matches",
        description="'matches today' should route to competition or fixtures",
        input="What matches are on today?",
        expected="competition",
    ),
]
