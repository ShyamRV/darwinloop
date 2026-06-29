"""Tests for the darwinloop CLI."""

from pathlib import Path
from typer.testing import CliRunner

from darwinloop.cli import app

runner = CliRunner()


def test_evolve_dry_run(tmp_path: Path) -> None:
    """darwinloop evolve --dry-run should complete without error."""
    agent_file = tmp_path / "router.py"
    agent_file.write_text(
        "def route_question(q):\n    return type('R', (), {'intent': 'competition'})()\n"
    )
    result = runner.invoke(app, [
        "evolve", str(agent_file),
        "--dry-run", "--auto", "--iterations", "1",
        "--archive", str(tmp_path / "archive"),
    ])
    assert result.exit_code == 0, result.output
    assert "Evolution complete" in result.output


def test_evolve_missing_target() -> None:
    result = runner.invoke(app, ["evolve", "nonexistent/path.py", "--dry-run"])
    assert result.exit_code != 0


def test_report_command(tmp_path: Path) -> None:
    """darwinloop report should print archive summary."""
    from darwinloop.core.archive import AgentArchive, AgentEntry
    archive = AgentArchive()
    archive.add_agent(AgentEntry("a0", None, "pass", benchmark_score=0.7))
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    archive.save(str(archive_dir / "archive.json"))

    result = runner.invoke(app, ["report", str(archive_dir)])
    assert result.exit_code == 0


def test_scaffold_dry_run(tmp_path: Path) -> None:
    agent_file = tmp_path / "agent.py"
    agent_file.write_text("def run(q): return q\n")
    out = tmp_path / "benchmarks.py"
    result = runner.invoke(app, ["scaffold", str(agent_file), "--output", str(out), "--dry-run"])
    assert result.exit_code == 0
    assert out.exists()
    assert "BenchmarkTask" in out.read_text()
