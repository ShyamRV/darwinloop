"""darwinloop._api — Main DarwinLoop class (public entry point)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from darwinloop._models import BenchmarkTask, EvolutionResult, GenerationInfo
from darwinloop.core.archive import AgentArchive, AgentEntry
from darwinloop.core.benchmark import BenchmarkSuite
from darwinloop.core.improver import SelfImprover
from darwinloop.core.selector import ParentSelector

if TYPE_CHECKING:
    from darwinloop.packs.base import BenchmarkPack

_console = Console(legacy_windows=False)

_BANNER = """\
  [bold cyan]darwinloop[/]  [dim]— self-improvement engine for AI agents[/]
  [dim]Based on the Darwin Gödel Machine (Zhang et al., ICLR 2026)[/]
"""


class DarwinLoop:
    """Self-improvement engine for AI agents.

    Evolves an agent's source code through iterative benchmark-driven
    improvement using a large language model.

    Example::

        from darwinloop import DarwinLoop, BenchmarkTask

        tasks = [
            BenchmarkTask(id="t1", name="live_scores",
                          input="live scores now", expected="live"),
        ]
        dl = DarwinLoop(target="my_agent/router.py", tasks=tasks, model="asi1")
        result = dl.run(iterations=5)
        print(f"{result.base_score:.2f} → {result.best_score:.2f}")
        result.apply()

    Args:
        target: Path to the Python file to evolve (e.g. ``"agent/router.py"``).
        tasks: List of :class:`~darwinloop._models.BenchmarkTask` objects. If not
            provided, *pack* must be given.
        pack: A :class:`~darwinloop.packs.base.BenchmarkPack` instance. Mutually
            exclusive with *tasks*.
        model: LLM model shorthand: ``"asi1"`` (default), ``"claude"``, ``"gpt-4o"``.
        api_key: API key (auto-detected from env if omitted).
        provider: Explicit LLM provider: ``"asi1"``, ``"anthropic"``, ``"openai"``.
        base_url: Custom LLM base URL (for self-hosted endpoints).
        iterations: Maximum number of improvement iterations (default 5).
        parallel_children: Children to generate per iteration (default 1).
        archive_path: Directory to save the archive JSON (default ``"darwinloop_output"``).
        sandbox_timeout: Per-task sandbox timeout in seconds (default 30).
        dry_run: Use the :class:`~darwinloop.llm.client.MockLLMClient` (free, no API key).
        auto: Skip interactive prompts between iterations.
        verbose: Show detailed LLM turn logs.
    """

    def __init__(
        self,
        target: str,
        tasks: list[BenchmarkTask] | None = None,
        pack: BenchmarkPack | None = None,
        model: str = "asi1",
        api_key: str = "",
        provider: str = "",
        base_url: str = "",
        iterations: int = 5,
        parallel_children: int = 1,
        archive_path: str = "darwinloop_output",
        sandbox_timeout: int = 30,
        dry_run: bool = False,
        auto: bool = False,
        verbose: bool = False,
    ) -> None:
        if not tasks and not pack:
            raise ValueError("Provide 'tasks' or 'pack' to define benchmarks.")
        if tasks and pack:
            raise ValueError("Provide 'tasks' OR 'pack', not both.")

        self.target = Path(target)
        self.tasks: list[BenchmarkTask] = tasks or pack.tasks  # type: ignore[union-attr]
        self.model = model
        self.api_key = api_key
        self.provider = provider or _provider_from_model(model)
        self.base_url = base_url
        self.iterations = iterations
        self.parallel_children = parallel_children
        self.archive_dir = Path(archive_path)
        self.sandbox_timeout = sandbox_timeout
        self.dry_run = dry_run
        self.auto = auto
        self.verbose = verbose

    def run(self, iterations: int | None = None) -> EvolutionResult:
        """Run the evolution loop and return the best evolved agent.

        Args:
            iterations: Override the number of iterations set in the constructor.

        Returns:
            :class:`~darwinloop._models.EvolutionResult` with scores, diff, and
            methods to apply the change and save a report.
        """
        max_iter = iterations or self.iterations
        _console.print(Panel(_BANNER, border_style="cyan"))

        # ── Setup ──────────────────────────────────────────────────────────────
        if not self.target.exists():
            raise FileNotFoundError(f"Target file not found: {self.target}")

        original_code = self.target.read_text(encoding="utf-8")
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        archive_json = str(self.archive_dir / "archive.json")

        from darwinloop.llm.client import get_llm_client
        llm = get_llm_client(
            dry_run=self.dry_run,
            provider=self.provider,
            api_key=self.api_key,
            model=self.model,
            base_url=self.base_url,
        )

        archive = AgentArchive(save_path=archive_json)
        selector = ParentSelector()
        suite = BenchmarkSuite(
            tasks=self.tasks,
            target_filename=self.target.name,
            sandbox_timeout=self.sandbox_timeout,
        )
        improver = SelfImprover(llm_client=llm, target_filename=self.target.name)
        generation_infos: list[GenerationInfo] = []

        # ── Gen 0 — evaluate base agent ────────────────────────────────────────
        _console.print(f"\n[bold]Evaluating base agent[/] ({self.target.name})…")
        base_result = suite.evaluate(original_code)
        base_entry = AgentEntry(
            agent_id="agent_0000",
            parent_id=None,
            code_snapshot=original_code,
            benchmark_score=base_result.score,
            is_valid=True,
            generation=0,
            eval_logs=base_result.eval_logs,
        )
        archive.add_agent(base_entry)
        generation_infos.append(GenerationInfo(
            agent_id="agent_0000", parent_id=None, generation=0,
            score=base_result.score, proposal="(base agent)",
        ))

        _console.print(
            f"  [green]✓[/] agent_0000: score=[bold]{base_result.score:.2f}[/] "
            f"({len(base_result.passed)}/{len(self.tasks)} tasks passed)"
        )

        agent_counter = 1

        # ── Evolution loop ─────────────────────────────────────────────────────
        for iteration in range(1, max_iter + 1):
            _console.rule(f"[bold]ITERATION {iteration}/{max_iter}[/]")

            parents = selector.select(archive, k=self.parallel_children)
            parent_ids = [p.agent_id for p in parents]
            _console.print(f"  Selected parents: {parent_ids}")

            for parent in parents:
                child_id = f"agent_{agent_counter:04d}"
                agent_counter += 1
                _console.print(f"\n  [dim]→ Generating {child_id} from {parent.agent_id}…[/]")

                try:
                    proposal = improver.propose(
                        agent_code=parent.code_snapshot,
                        eval_logs=parent.eval_logs,
                        failed_tasks=base_result.failed_as_dicts() if iteration == 1 else [],
                    )
                    _console.print(f"    Proposal: [italic]{proposal.chosen_improvement[:80]}[/]")
                except Exception as exc:
                    _console.print(f"    [red]Proposal failed:[/] {exc}")
                    archive.add_agent(AgentEntry(
                        agent_id=child_id, parent_id=parent.agent_id,
                        code_snapshot=parent.code_snapshot, benchmark_score=0.0,
                        is_valid=False, generation=parent.generation + 1,
                        improvement_summary=f"Proposal failed: {exc}",
                    ))
                    generation_infos.append(GenerationInfo(
                        agent_id=child_id, parent_id=parent.agent_id,
                        generation=parent.generation + 1, score=0.0,
                        proposal=f"Proposal failed: {exc}", is_valid=False,
                    ))
                    continue

                try:
                    new_code = improver.implement(parent.code_snapshot, proposal)
                except Exception as exc:
                    _console.print(f"    [red]Implementation failed:[/] {exc}")
                    new_code = parent.code_snapshot

                _console.print("    Evaluating…", end=" ")
                eval_result = suite.evaluate(new_code)
                _console.print(f"score=[bold]{eval_result.score:.2f}[/]")

                # Score regression protection — only keep strictly better code
                improved = eval_result.score > parent.benchmark_score
                child = AgentEntry(
                    agent_id=child_id,
                    parent_id=parent.agent_id,
                    code_snapshot=new_code if improved else parent.code_snapshot,
                    benchmark_score=eval_result.score if improved else parent.benchmark_score,
                    is_valid=True,
                    generation=parent.generation + 1,
                    improvement_summary=proposal.chosen_improvement,
                    eval_logs=eval_result.eval_logs,
                )
                archive.add_agent(child)
                generation_infos.append(GenerationInfo(
                    agent_id=child_id, parent_id=parent.agent_id,
                    generation=parent.generation + 1,
                    score=child.benchmark_score,
                    proposal=proposal.chosen_improvement,
                ))

                delta = child.benchmark_score - parent.benchmark_score
                sign = "+" if delta >= 0 else ""
                colour = "green" if delta > 0 else ("yellow" if delta == 0 else "red")
                _console.print(
                    f"  [dim]{parent.agent_id}[/] → [bold]{child_id}[/]  "
                    f"Score: {parent.benchmark_score:.2f} → {child.benchmark_score:.2f} "
                    f"([{colour}]{sign}{delta:.2f}[/])"
                )

            # Show archive summary
            s = archive.stats()
            _console.print(
                f"\n  Archive: {s['total_agents']} agents | "
                f"Valid: {s['valid_agents']} | "
                f"Best: [bold cyan]{s['best_score']:.2f}[/] ({s['best_agent_id']})"
            )

            # Show selection probabilities
            probs = selector.probabilities(archive)
            _console.print("\n  Parent selection probabilities:")
            for agent, prob in probs[:5]:
                bar = "█" * int(prob * 16) + "░" * (16 - int(prob * 16))
                _console.print(
                    f"  {agent.agent_id:12s}  [cyan]{bar}[/]  {prob*100:5.1f}%  "
                    f"(score={agent.benchmark_score:.2f})"
                )

            # Human checkpoint (non-auto mode)
            if not self.auto and iteration < max_iter:
                try:
                    cont = input("\nContinue? [y/n]: ").strip().lower()
                    if cont not in ("y", "yes", ""):
                        _console.print("[yellow]Run paused by user.[/]")
                        break
                except (EOFError, KeyboardInterrupt):
                    break

        # ── Finalise ───────────────────────────────────────────────────────────
        archive.print_tree()
        archive.print_table()

        best = archive.best() or base_entry
        result = EvolutionResult(
            base_score=base_entry.benchmark_score,
            best_score=best.benchmark_score,
            score_delta=best.benchmark_score - base_entry.benchmark_score,
            best_agent_id=best.agent_id,
            best_generation=best.generation,
            best_code=best.code_snapshot,
            original_code=original_code,
            total_agents=len(archive),
            valid_agents=len(archive.valid()),
            iterations_run=max_iter,
            archive_path=archive_json,
            generations=generation_infos,
        )
        # Store target path for result.apply()
        object.__setattr__(result, "_target_path", str(self.target))  # type: ignore[call-overload]

        _console.print(
            f"\n[bold green]Evolution complete![/]  "
            f"Score: [bold]{result.base_score:.2f}[/] → [bold cyan]{result.best_score:.2f}[/]  "
            f"([green]+{result.score_delta:.2f}[/]  "
            f"best: {result.best_agent_id}  gen {result.best_generation})"
        )

        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _provider_from_model(model: str) -> str:
    """Infer provider from model shorthand."""
    m = model.lower()
    if m in ("asi1", "asi:one"):
        return "asi1"
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gpt") or m.startswith("o1") or m.startswith("o3"):
        return "openai"
    # Fall back to env-based auto-detection
    return ""
