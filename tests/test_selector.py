"""Tests for darwinloop core selector."""

import pytest

from darwinloop.core.archive import AgentArchive, AgentEntry
from darwinloop.core.selector import ParentSelector


def _archive(*scores) -> AgentArchive:
    archive = AgentArchive()
    for i, score in enumerate(scores):
        archive.add_agent(AgentEntry(
            agent_id=f"a{i}", parent_id=None,
            code_snapshot="pass", benchmark_score=score,
        ))
    return archive


def test_select_returns_k_parents() -> None:
    archive = _archive(0.5, 0.7, 0.3)
    sel = ParentSelector()
    parents = sel.select(archive, k=3)
    assert len(parents) == 3


def test_all_agents_have_nonzero_probability() -> None:
    archive = _archive(0.1, 0.9)
    sel = ParentSelector()
    probs = sel.probabilities(archive)
    assert all(p > 0 for _, p in probs)


def test_probabilities_sum_to_one() -> None:
    archive = _archive(0.2, 0.5, 0.8)
    sel = ParentSelector()
    probs = sel.probabilities(archive)
    total = sum(p for _, p in probs)
    assert total == pytest.approx(1.0)


def test_higher_score_preferred() -> None:
    archive = _archive(0.1, 0.9)
    sel = ParentSelector()
    probs = {a.agent_id: p for a, p in sel.probabilities(archive)}
    assert probs["a1"] > probs["a0"]


def test_raises_on_empty_archive() -> None:
    archive = AgentArchive()
    sel = ParentSelector()
    with pytest.raises(ValueError):
        sel.select(archive, k=1)


def test_novelty_bonus_reduces_used_parent_probability() -> None:
    """Parent with many children should have lower probability than a fresh peer."""
    archive = AgentArchive()
    parent = AgentEntry("p0", None, "pass", benchmark_score=0.8)
    archive.add_agent(parent)
    for i in range(5):
        child = AgentEntry(f"c{i}", parent_id="p0", code_snapshot="pass", benchmark_score=0.8)
        archive.add_agent(child)

    fresh = AgentEntry("p1", None, "pass", benchmark_score=0.8)
    archive.add_agent(fresh)

    sel = ParentSelector()
    probs = {a.agent_id: p for a, p in sel.probabilities(archive)}
    # p1 has no children so its novelty bonus is higher
    assert probs["p1"] > probs["p0"]
