"""Public data models for darwinloop."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkTask:
    """A single evaluation task for the agent under evolution.

    Args:
        id: Unique identifier for this task (e.g. ``"task_001"``).
        name: Short human-readable name.
        description: What behaviour this task validates.
        input: Single-turn input string to the agent.
        input_sequence: Multi-turn conversation (list of strings). Use instead of ``input``.
        expected: Expected output substring or exact match.
        must_not_contain: String that must NOT appear in the output.
        weight: Relative weight in the final score (default 1.0).
    """

    id: str
    name: str
    description: str = ""
    input: str = ""
    input_sequence: list[str] = field(default_factory=list)
    expected: str = ""
    must_not_contain: str = ""
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.input and not self.input_sequence:
            raise ValueError(f"BenchmarkTask '{self.id}': provide 'input' or 'input_sequence'")
        if self.input and self.input_sequence:
            raise ValueError(f"BenchmarkTask '{self.id}': provide 'input' OR 'input_sequence', not both")


@dataclass
class GenerationInfo:
    """Score and metadata for one agent generation.

    Attributes:
        agent_id: Unique agent identifier (e.g. ``"agent_0003"``).
        parent_id: Parent agent identifier, or ``None`` for generation 0.
        generation: Generation number (0 = base agent).
        score: Benchmark score in [0.0, 1.0].
        proposal: Short description of what was changed.
        is_valid: Whether the code passed safety validation.
    """

    agent_id: str
    parent_id: str | None
    generation: int
    score: float
    proposal: str = ""
    is_valid: bool = True


@dataclass
class EvolutionResult:
    """Result returned by :meth:`DarwinLoop.run`.

    Attributes:
        base_score: Score of the original (Generation 0) agent.
        best_score: Highest score achieved across all generations.
        score_delta: ``best_score - base_score``.
        best_agent_id: Identifier of the best-scoring agent.
        best_generation: Generation number of the best agent.
        best_code: Source code of the best agent.
        original_code: Source code of the original agent.
        total_agents: Total number of agents evaluated.
        valid_agents: Agents that passed safety and syntax validation.
        iterations_run: Number of iterations completed.
        archive_path: Path where the archive JSON was saved.
        generations: Per-generation score and proposal details.
    """

    base_score: float
    best_score: float
    score_delta: float
    best_agent_id: str
    best_generation: int
    best_code: str
    original_code: str
    total_agents: int
    valid_agents: int
    iterations_run: int
    archive_path: str
    generations: list[GenerationInfo] = field(default_factory=list)

    # ── Derived helpers ───────────────────────────────────────────────────────

    @property
    def diff(self) -> str:
        """Unified diff between the original code and the best evolved code."""
        return "".join(
            difflib.unified_diff(
                self.original_code.splitlines(keepends=True),
                self.best_code.splitlines(keepends=True),
                fromfile="original",
                tofile=f"evolved ({self.best_agent_id})",
            )
        )

    def apply(self, path: str | None = None) -> None:
        """Write the best evolved code back to the target file.

        Args:
            path: Override the target file path. If ``None``, uses the path
                  recorded in the archive.
        """
        target = path or self.archive_path.replace("archive.json", "").rstrip("/\\")
        # archive_path is the directory; resolve the actual target from _target_path
        if hasattr(self, "_target_path") and self._target_path:
            target = self._target_path  # type: ignore[attr-defined]
        if not target or not Path(target).suffix:
            raise ValueError("Cannot determine target file path. Pass 'path' explicitly.")
        Path(target).write_text(self.best_code, encoding="utf-8")

    def save_report(self, path: str = "darwinloop_report.md") -> None:
        """Save a markdown evolution report to *path*.

        Args:
            path: Output file path (default ``darwinloop_report.md``).
        """
        from darwinloop.report import build_markdown_report
        report = build_markdown_report(self)
        Path(path).write_text(report, encoding="utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "base_score": self.base_score,
            "best_score": self.best_score,
            "score_delta": self.score_delta,
            "best_agent_id": self.best_agent_id,
            "best_generation": self.best_generation,
            "total_agents": self.total_agents,
            "valid_agents": self.valid_agents,
            "iterations_run": self.iterations_run,
            "archive_path": self.archive_path,
            "generations": [
                {
                    "agent_id": g.agent_id,
                    "parent_id": g.parent_id,
                    "generation": g.generation,
                    "score": g.score,
                    "proposal": g.proposal,
                    "is_valid": g.is_valid,
                }
                for g in self.generations
            ],
            "diff": self.diff,
        }
