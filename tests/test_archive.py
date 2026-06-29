"""Tests for darwinloop.core.archive."""

from pathlib import Path

import pytest

from darwinloop.core.archive import AgentArchive, AgentEntry


def make_entry(agent_id: str, parent_id=None, score=0.5, gen=0) -> AgentEntry:
    return AgentEntry(
        agent_id=agent_id,
        parent_id=parent_id,
        code_snapshot=f"# agent {agent_id}\nprint('hello')",
        benchmark_score=score,
        generation=gen,
    )


def test_add_and_get() -> None:
    archive = AgentArchive()
    e = make_entry("agent_0000")
    archive.add_agent(e)
    assert archive.get("agent_0000") is e
    assert len(archive) == 1


def test_duplicate_ignored() -> None:
    archive = AgentArchive()
    e = make_entry("agent_0000", score=0.5)
    archive.add_agent(e)
    archive.add_agent(e)  # duplicate — ignored
    assert len(archive) == 1


def test_parent_children_updated() -> None:
    archive = AgentArchive()
    parent = make_entry("agent_0000")
    child = make_entry("agent_0001", parent_id="agent_0000", score=0.7, gen=1)
    archive.add_agent(parent)
    archive.add_agent(child)
    assert "agent_0001" in archive.get("agent_0000").children_ids


def test_best_returns_highest_score() -> None:
    archive = AgentArchive()
    archive.add_agent(make_entry("a0", score=0.5))
    archive.add_agent(make_entry("a1", score=0.8))
    archive.add_agent(make_entry("a2", score=0.6))
    assert archive.best().agent_id == "a1"  # type: ignore[union-attr]


def test_invalid_agent_excluded_from_best() -> None:
    archive = AgentArchive()
    archive.add_agent(make_entry("a0", score=0.5))
    bad = make_entry("a1", score=0.9)
    bad.is_valid = False
    archive.add_agent(bad)
    assert archive.best().agent_id == "a0"  # type: ignore[union-attr]


def test_lineage() -> None:
    archive = AgentArchive()
    a0 = make_entry("a0", gen=0)
    a1 = make_entry("a1", parent_id="a0", gen=1)
    a2 = make_entry("a2", parent_id="a1", gen=2)
    for e in (a0, a1, a2):
        archive.add_agent(e)
    lineage = archive.lineage("a2")
    assert [e.agent_id for e in lineage] == ["a0", "a1", "a2"]


def test_save_and_load(tmp_path: Path) -> None:
    archive = AgentArchive()
    for i in range(3):
        archive.add_agent(make_entry(f"a{i}", score=i * 0.3, gen=i))
    save_path = str(tmp_path / "archive.json")
    archive.save(save_path)

    loaded = AgentArchive.load(save_path)
    assert len(loaded) == 3
    assert loaded.best().agent_id == "a2"  # type: ignore[union-attr]


def test_stats() -> None:
    archive = AgentArchive()
    archive.add_agent(make_entry("a0", score=0.4))
    archive.add_agent(make_entry("a1", score=0.8))
    s = archive.stats()
    assert s["total_agents"] == 2
    assert s["best_score"] == pytest.approx(0.8)
    assert s["best_agent_id"] == "a1"
