"""
Benchmark tasks for the news-agent headline routing logic.

Tests parse_headline_position() and is_follow_up_request() across:
- Happy paths (ordinals, digits, follow-up phrases)
- Extended ordinals (sixth, seventh — known gaps)
- Extended digit range (1-9 — known gap, only 1-5 supported)
- Natural follow-up phrases (summarize, read more — known gaps)
- Edge cases and negatives

Usage:
    darwinloop evolve examples/news/news_router.py \\
        --tasks examples/news/benchmarks.py \\
        --iterations 5 --model asi1 --auto
"""

from darwinloop import BenchmarkTask

TASKS = [
    # ── Ordinal words (should already work) ──────────────────────────────────
    BenchmarkTask(
        id="n01_ordinal_second",
        name="ordinal_second",
        description="'go deeper on the second' should return position 2",
        input="go deeper on the second one",
        expected="2",
    ),
    BenchmarkTask(
        id="n02_ordinal_third",
        name="ordinal_third",
        description="'tell me more about the third' should return position 3",
        input="tell me more about the third headline",
        expected="3",
    ),
    BenchmarkTask(
        id="n03_digit_headline",
        name="digit_headline_3",
        description="'headline 3' should return position 3",
        input="headline 3",
        expected="3",
    ),
    # ── Extended ordinals (KNOWN GAP: sixth/seventh not in _ORDINAL_WORDS) ───
    BenchmarkTask(
        id="n04_sixth",
        name="ordinal_sixth",
        description="'go deeper on the sixth' should return 6 — currently a gap",
        input="go deeper on the sixth article",
        expected="6",
    ),
    BenchmarkTask(
        id="n05_seventh",
        name="ordinal_seventh",
        description="'more on the seventh' should return 7",
        input="more on the seventh story",
        expected="7",
    ),
    # ── Extended digit range (KNOWN GAP: _DIGIT_RE caps at [1-5]) ────────────
    BenchmarkTask(
        id="n06_story_7",
        name="story_digit_7",
        description="'show me story 7' should return 7 — currently fails (capped at 5)",
        input="show me story 7",
        expected="7",
    ),
    BenchmarkTask(
        id="n07_headline_9",
        name="headline_digit_9",
        description="'headline 9' should return 9",
        input="headline 9",
        expected="9",
    ),
    # ── Natural follow-up phrases (KNOWN GAPS) ────────────────────────────────
    BenchmarkTask(
        id="n08_summarize",
        name="followup_summarize",
        description="'summarize headline 2' should be detected as a follow-up request",
        input="summarize headline 2",
        expected="True",
    ),
    BenchmarkTask(
        id="n09_read_more",
        name="followup_read_more",
        description="'read more about story 3' should be detected as a follow-up request",
        input="read more about story 3",
        expected="True",
    ),
    BenchmarkTask(
        id="n10_show_more_details",
        name="followup_show_more_details",
        description="'show me more details on the first news' should be a follow-up",
        input="show me more details on the first news",
        expected="True",
    ),
]
