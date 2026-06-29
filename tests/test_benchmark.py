"""Tests for darwinloop core benchmark suite."""

import pytest

from darwinloop._models import BenchmarkTask
from darwinloop.core.benchmark import BenchmarkSuite, _parse_score

# ── Score parser ──────────────────────────────────────────────────────────────

def test_parse_score_explicit() -> None:
    assert _parse_score("SCORE:0.75") == pytest.approx(0.75)


def test_parse_score_pass() -> None:
    assert _parse_score("PASS") == pytest.approx(1.0)


def test_parse_score_fail() -> None:
    assert _parse_score("FAIL: wrong output") == pytest.approx(0.0)


def test_parse_score_empty_output() -> None:
    # Empty stdout is treated conservatively as 0.0 (no explicit SCORE/PASS seen)
    assert _parse_score("") == pytest.approx(0.0)


# ── BenchmarkSuite ────────────────────────────────────────────────────────────

_ROUTER_CODE = '''\
def route_question(question):
    q = question.lower()
    if "live" in q:
        return type("R", (), {"intent": "live"})()
    if "fixture" in q or "next game" in q:
        return type("R", (), {"intent": "team_fixtures"})()
    return type("R", (), {"intent": "competition"})()
'''


def test_suite_passing_task() -> None:
    tasks = [
        BenchmarkTask(id="t1", name="live", input="live scores now", expected="live"),
    ]
    suite = BenchmarkSuite(tasks, target_filename="router.py", sandbox_timeout=15)
    result = suite.evaluate(_ROUTER_CODE)
    assert result.score == pytest.approx(1.0)
    assert len(result.passed) == 1
    assert len(result.failed) == 0


def test_suite_failing_task() -> None:
    tasks = [
        BenchmarkTask(id="t1", name="player", input="Haaland stats", expected="player"),
    ]
    suite = BenchmarkSuite(tasks, target_filename="router.py", sandbox_timeout=15)
    result = suite.evaluate(_ROUTER_CODE)
    assert result.score < 1.0
    assert len(result.failed) == 1


def test_suite_must_not_contain() -> None:
    tasks = [
        BenchmarkTask(
            id="t1", name="vs_not_team",
            input="Barcelona vs Madrid result",
            expected="competition",
            must_not_contain="team",
        ),
    ]
    suite = BenchmarkSuite(tasks, target_filename="router.py", sandbox_timeout=15)
    result = suite.evaluate(_ROUTER_CODE)
    assert result.score == pytest.approx(1.0)


def test_suite_unsafe_code_blocked() -> None:
    tasks = [BenchmarkTask(id="t1", name="smoke", input="test", expected="")]
    suite = BenchmarkSuite(tasks, sandbox_timeout=15)
    result = suite.evaluate("x = eval('1+1')\n")
    assert result.score == pytest.approx(0.0)
    assert any("BLOCKED" in log for log in result.eval_logs)


def test_suite_weighted_scoring() -> None:
    tasks = [
        BenchmarkTask(id="t1", name="pass", input="live scores", expected="live", weight=2.0),
        BenchmarkTask(id="t2", name="fail", input="player stats", expected="player", weight=1.0),
    ]
    suite = BenchmarkSuite(tasks, target_filename="router.py", sandbox_timeout=15)
    result = suite.evaluate(_ROUTER_CODE)
    # t1 passes (weight 2) + t2 fails (weight 1) → 2/3 ≈ 0.667
    assert result.score == pytest.approx(2 / 3, abs=0.05)
