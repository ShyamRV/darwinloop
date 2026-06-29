"""
Example: Evolve a simple intent router using darwinloop.

Run:
    pip install darwinloop
    python examples/quickstart/run.py --dry-run   # free, no API key
    python examples/quickstart/run.py             # real run (needs ASI1_API_KEY)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from darwinloop import BenchmarkTask, DarwinLoop


def main(dry_run: bool = False) -> None:
    tasks = [
        BenchmarkTask(
            id="task_001",
            name="routes_live",
            description="'live scores' should return intent=live",
            input="What are the live scores right now?",
            expected="live",
        ),
        BenchmarkTask(
            id="task_002",
            name="routes_fixtures",
            description="'next game' should return intent=team_fixtures",
            input="Arsenal next game",
            expected="fixture",
        ),
        BenchmarkTask(
            id="task_003",
            name="routes_competition",
            description="'vs result' should trigger competition, not team",
            input="Barcelona vs Real Madrid result",
            expected="competition",
            must_not_contain="team",
        ),
        BenchmarkTask(
            id="task_004",
            name="pronoun_followup",
            description="Pronoun 'they' should resolve to last mentioned team",
            input_sequence=["Tell me about Liverpool", "When do they play next?"],
            expected="fixture",
        ),
        BenchmarkTask(
            id="task_005",
            name="greeting",
            description="'Hello' should return greeting intent",
            input="Hello!",
            expected="greeting",
        ),
    ]

    dl = DarwinLoop(
        target=str(Path(__file__).parent / "my_router.py"),
        tasks=tasks,
        model="asi1",
        iterations=3,
        archive_path="darwinloop_quickstart_output",
        dry_run=dry_run,
        auto=True,
    )

    result = dl.run()

    print(f"\nBase score : {result.base_score:.2f}")
    print(f"Best score : {result.best_score:.2f}")
    print(f"Delta      : +{result.score_delta:.2f}")
    print(f"Best agent : {result.best_agent_id} (gen {result.best_generation})")

    if result.score_delta > 0:
        result.apply()
        result.save_report("quickstart_report.md")
        print("\nEvolved code written back to my_router.py")
        print("Report saved to quickstart_report.md")
    else:
        print("\nNo improvement found — original code is already optimal.")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
