"""
darwinloop core/archive.py — Agent archive (family tree of all generations).

Every agent ever generated is stored here — including failures. This open-ended
archive is the KEY difference between DGM and naive hill-climbing: we never
discard agents, enabling exploration of multiple evolutionary branches.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

_console = Console(legacy_windows=False)


class AgentEntry:
    """One node in the darwinloop family tree.

    Args:
        agent_id: Unique identifier (e.g. ``"agent_0003"``).
        parent_id: Parent agent ID, or ``None`` for the base agent.
        code_snapshot: Full source code of this agent version.
        benchmark_score: Score in [0.0, 1.0] on the benchmark suite.
        children_ids: IDs of child agents spawned from this one.
        is_valid: Whether this agent passed safety + syntax validation.
        generation: Generation number (0 = base).
        improvement_summary: Short description of what changed vs parent.
        eval_logs: Captured stdout/stderr from benchmark runs.
        created_at: UTC timestamp of creation.
    """

    def __init__(
        self,
        agent_id: str,
        parent_id: str | None,
        code_snapshot: str,
        benchmark_score: float = 0.0,
        children_ids: list[str] | None = None,
        is_valid: bool = True,
        generation: int = 0,
        improvement_summary: str = "",
        eval_logs: list[str] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.parent_id = parent_id
        self.code_snapshot = code_snapshot
        self.benchmark_score = benchmark_score
        self.children_ids: list[str] = children_ids or []
        self.is_valid = is_valid
        self.generation = generation
        self.improvement_summary = improvement_summary
        self.eval_logs: list[str] = eval_logs or []
        self.created_at = created_at or datetime.now(UTC)

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dictionary."""
        return {
            "agent_id": self.agent_id,
            "parent_id": self.parent_id,
            "code_snapshot": self.code_snapshot,
            "benchmark_score": self.benchmark_score,
            "children_ids": self.children_ids,
            "is_valid": self.is_valid,
            "generation": self.generation,
            "improvement_summary": self.improvement_summary,
            "eval_logs": self.eval_logs,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgentEntry:
        """Deserialise from a JSON dictionary."""
        entry = cls(
            agent_id=d["agent_id"],
            parent_id=d.get("parent_id"),
            code_snapshot=d["code_snapshot"],
            benchmark_score=d.get("benchmark_score", 0.0),
            children_ids=d.get("children_ids", []),
            is_valid=d.get("is_valid", True),
            generation=d.get("generation", 0),
            improvement_summary=d.get("improvement_summary", d.get("self_improve_proposal", "")),
            eval_logs=d.get("eval_logs", []),
        )
        if "created_at" in d:
            try:
                entry.created_at = datetime.fromisoformat(d["created_at"])
            except Exception:
                entry.created_at = datetime.now(UTC)
        return entry

    def __repr__(self) -> str:
        return (
            f"AgentEntry(id={self.agent_id!r}, score={self.benchmark_score:.2f}, "
            f"gen={self.generation}, valid={self.is_valid})"
        )


class AgentArchive:
    """Thread-safe, persistent registry of all agents produced by darwinloop.

    The archive is append-only: once an ``AgentEntry`` is written, it is never
    modified (the ``improvement_summary`` and ``eval_logs`` are set at creation).

    Args:
        save_path: Path to the JSON file used for persistence (optional).
    """

    def __init__(self, save_path: str | None = None) -> None:
        self._agents: dict[str, AgentEntry] = {}
        self._lock = threading.Lock()
        self.save_path = save_path

    # ── Mutation ──────────────────────────────────────────────────────────────

    def add_agent(self, agent: AgentEntry) -> None:
        """Add a new agent and update its parent's children list.

        Thread-safe. Silently ignores duplicates (same agent_id).
        """
        with self._lock:
            if agent.agent_id in self._agents:
                return
            self._agents[agent.agent_id] = agent
            if agent.parent_id and agent.parent_id in self._agents:
                parent = self._agents[agent.parent_id]
                if agent.agent_id not in parent.children_ids:
                    parent.children_ids.append(agent.agent_id)
            if self.save_path:
                self._save_locked(self.save_path)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get(self, agent_id: str) -> AgentEntry:
        """Return the agent with *agent_id*.

        Raises:
            KeyError: If *agent_id* is not in the archive.
        """
        try:
            return self._agents[agent_id]
        except KeyError:
            raise KeyError(f"Agent '{agent_id}' not found in archive.") from None

    def all(self) -> list[AgentEntry]:
        """Return all agents, sorted by creation time."""
        return sorted(self._agents.values(), key=lambda a: a.created_at)

    def valid(self) -> list[AgentEntry]:
        """Return only valid agents, sorted by creation time."""
        return [a for a in self.all() if a.is_valid]

    def best(self) -> AgentEntry | None:
        """Return the valid agent with the highest benchmark score."""
        v = self.valid()
        return max(v, key=lambda a: a.benchmark_score) if v else None

    def lineage(self, agent_id: str) -> list[AgentEntry]:
        """Return the ancestor chain from root down to *agent_id*.

        Args:
            agent_id: The target agent whose lineage to trace.

        Returns:
            List of agents from root (index 0) to *agent_id* (last index).
        """
        chain: list[AgentEntry] = []
        current_id: str | None = agent_id
        visited: set[str] = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            agent = self._agents.get(current_id)
            if agent is None:
                break
            chain.append(agent)
            current_id = agent.parent_id
        chain.reverse()
        return chain

    def stats(self) -> dict:
        """Return summary statistics about the archive."""
        all_agents = self.all()
        valid_agents = self.valid()
        scores = [a.benchmark_score for a in valid_agents]
        b = self.best()
        return {
            "total_agents": len(all_agents),
            "valid_agents": len(valid_agents),
            "avg_score": sum(scores) / len(scores) if scores else 0.0,
            "best_score": max(scores) if scores else 0.0,
            "best_agent_id": b.agent_id if b else None,
            "max_generation": max((a.generation for a in all_agents), default=0),
        }

    def __len__(self) -> int:
        return len(self._agents)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Save the archive to a JSON file at *path*.

        Args:
            path: File path (parent directories are created automatically).
        """
        with self._lock:
            self._save_locked(path)

    def _save_locked(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {aid: entry.to_dict() for aid, entry in self._agents.items()}
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> AgentArchive:
        """Load an archive from a JSON file.

        Args:
            path: Path to the archive JSON file.

        Returns:
            Populated :class:`AgentArchive`.
        """
        archive = cls(save_path=path)
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for entry_dict in data.values():
            # Bypass add_agent to avoid triggering auto-save on load
            agent = AgentEntry.from_dict(entry_dict)
            archive._agents[agent.agent_id] = agent
        return archive

    # ── Visualisation ─────────────────────────────────────────────────────────

    def to_networkx(self) -> nx.DiGraph:
        """Build a directed NetworkX graph (parent → child edges)."""
        G: nx.DiGraph = nx.DiGraph()
        for agent in self._agents.values():
            G.add_node(
                agent.agent_id,
                score=agent.benchmark_score,
                generation=agent.generation,
                is_valid=agent.is_valid,
            )
        for agent in self._agents.values():
            if agent.parent_id:
                G.add_edge(agent.parent_id, agent.agent_id)
        return G

    def print_tree(self, console: Console | None = None) -> None:
        """Render the family tree using Rich."""
        con = console or _console
        b = self.best()
        roots = [a for a in self._agents.values() if a.parent_id is None]

        def _bar(score: float) -> str:
            filled = int(score * 6)
            return "█" * filled + "░" * (6 - filled)

        def _add_children(tree_node: Tree, agent: AgentEntry) -> None:
            for child_id in agent.children_ids:
                child = self._agents.get(child_id)
                if child is None:
                    continue
                is_best = b and child.agent_id == b.agent_id
                status = "⭐ BEST" if is_best else ("✓" if child.is_valid else "✗ INVALID")
                colour = "green" if child.is_valid else "red"
                label = (
                    f"[{colour}]{child.agent_id}[/] "
                    f"[dim]{_bar(child.benchmark_score)}[/] "
                    f"[bold cyan]{child.benchmark_score:.2f}[/] "
                    f"[dim]GEN {child.generation}[/] "
                    f"[yellow]{status}[/]"
                )
                branch = tree_node.add(label)
                _add_children(branch, child)

        s = self.stats()
        con.print()
        con.rule("[bold cyan]darwinloop — Agent Family Tree[/]")
        for root in roots:
            root_label = (
                f"[bold green]🌱 {root.agent_id}[/] "
                f"[dim]{_bar(root.benchmark_score)}[/] "
                f"[bold cyan]{root.benchmark_score:.2f}[/] "
                f"[dim]GEN 0 (BASE)[/]"
            )
            tree = Tree(root_label)
            _add_children(tree, root)
            con.print(tree)

        con.print()
        con.print(
            f"  Total: [bold]{s['total_agents']}[/] | "
            f"Valid: [green]{s['valid_agents']}[/] | "
            f"Best: [cyan]{s['best_agent_id']}[/] "
            f"(score=[bold]{s['best_score']:.2f}[/])"
        )

    def print_table(self, console: Console | None = None) -> None:
        """Render a Rich table summary of all agents."""
        con = console or _console
        b = self.best()
        table = Table(title="darwinloop — Agent Archive", show_lines=True)
        table.add_column("Agent ID", style="cyan")
        table.add_column("Parent", style="dim")
        table.add_column("Score", justify="right")
        table.add_column("Bar")
        table.add_column("Gen", justify="center")
        table.add_column("Status")
        table.add_column("Improvement")

        for agent in self.all():
            is_best = b and agent.agent_id == b.agent_id
            bar = "█" * int(agent.benchmark_score * 6) + "░" * (6 - int(agent.benchmark_score * 6))
            status = (
                "[bold yellow]⭐ BEST[/]" if is_best
                else ("[green]✓ valid[/]" if agent.is_valid else "[red]✗ invalid[/]")
            )
            summary = agent.improvement_summary
            if len(summary) > 50:
                summary = summary[:47] + "…"
            table.add_row(
                agent.agent_id,
                agent.parent_id or "—",
                f"{agent.benchmark_score:.2f}",
                f"[cyan]{bar}[/]",
                str(agent.generation),
                status,
                summary or "—",
            )
        con.print(table)
