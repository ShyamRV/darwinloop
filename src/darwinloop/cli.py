"""darwinloop CLI — command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

app = typer.Typer(
    name="darwinloop",
    help="Self-improvement engine for AI agents.",
    add_completion=False,
)
_console = Console(legacy_windows=False)

load_dotenv()


@app.command()
def evolve(
    target: str = typer.Argument(..., help="Path to the agent file or directory to evolve."),
    iterations: int = typer.Option(5, "--iterations", "-i", help="Number of improvement iterations."),
    model: str = typer.Option("asi1", "--model", "-m", help="LLM model: asi1 | claude | gpt-4o"),
    tasks: Optional[str] = typer.Option(None, "--tasks", "-t", help="Path to a benchmarks.py file."),
    pack: Optional[str] = typer.Option(None, "--pack", "-p", help="Built-in pack: routing | commerce | support"),
    archive_path: str = typer.Option("darwinloop_output", "--archive", "-a", help="Output directory."),
    sandbox_timeout: int = typer.Option(30, "--timeout", help="Per-task sandbox timeout (seconds)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Use mock LLM (free, no API key needed)."),
    auto: bool = typer.Option(False, "--auto", help="Skip interactive prompts between iterations."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed LLM turn logs."),
    report: Optional[str] = typer.Option(None, "--report", "-r", help="Save markdown report to this path."),
) -> None:
    """Evolve an agent's source code using darwinloop self-improvement.

    Examples::

        darwinloop evolve agent/router.py --iterations 5 --model asi1
        darwinloop evolve agent/ --dry-run --auto
        darwinloop evolve agent/router.py --pack routing --iterations 10
        darwinloop evolve agent/router.py --tasks my_benchmarks.py --auto
    """
    from darwinloop import DarwinLoop, BenchmarkTask

    # Resolve target file
    target_path = Path(target)
    if target_path.is_dir():
        candidates = list(target_path.glob("router.py")) + list(target_path.glob("agent.py")) + list(target_path.rglob("*.py"))
        py_files = [f for f in candidates if f.is_file() and not f.name.startswith("_")]
        if not py_files:
            _console.print(f"[red]No Python files found in {target}[/]")
            raise typer.Exit(1)
        target_path = py_files[0]
        _console.print(f"[dim]Auto-detected target: {target_path}[/]")

    # Load benchmark tasks
    benchmark_tasks: list[BenchmarkTask] | None = None
    benchmark_pack = None

    if tasks:
        benchmark_tasks = _load_tasks_from_file(tasks)
        if not benchmark_tasks:
            _console.print(f"[red]No BenchmarkTask objects found in {tasks}[/]")
            raise typer.Exit(1)
        _console.print(f"[dim]Loaded {len(benchmark_tasks)} tasks from {tasks}[/]")

    elif pack:
        benchmark_pack = _load_pack(pack)
        if not benchmark_pack:
            _console.print(f"[red]Unknown pack: {pack!r}. Choose: routing, commerce, support[/]")
            raise typer.Exit(1)
        _console.print(f"[dim]Using {benchmark_pack}[/]")

    else:
        _console.print(
            "[yellow]No tasks or pack specified. Using a minimal smoke-test benchmark.[/]\n"
            "[dim]For real results, pass --tasks benchmarks.py or --pack routing[/]"
        )
        benchmark_tasks = [
            BenchmarkTask(
                id="smoke_001",
                name="basic_import",
                description="Agent file must be importable without errors",
                input="hello",
                expected="",
            )
        ]

    dl = DarwinLoop(
        target=str(target_path),
        tasks=benchmark_tasks,
        pack=benchmark_pack,
        model=model,
        iterations=iterations,
        archive_path=archive_path,
        sandbox_timeout=sandbox_timeout,
        dry_run=dry_run,
        auto=auto,
        verbose=verbose,
    )

    result = dl.run()

    if report:
        result.save_report(report)
        _console.print(f"[green]Report saved to {report}[/]")

    _console.print(f"\n[dim]Archive: {result.archive_path}[/]")
    _console.print(f"[dim]Run 'darwinloop report {archive_path}' to view a detailed report.[/]")


@app.command()
def scaffold(
    target: str = typer.Argument(..., help="Path to the agent file to analyse."),
    output: str = typer.Option("benchmarks.py", "--output", "-o", help="Output file path."),
    model: str = typer.Option("asi1", "--model", "-m", help="LLM model to use."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Mock scaffold (no API call)."),
) -> None:
    """Auto-generate benchmark tasks from an agent's source code.

    Example::

        darwinloop scaffold agent/router.py --output benchmarks.py
    """
    from darwinloop.scaffold import generate_benchmarks
    _console.print(f"[bold]Scaffolding benchmarks for[/] {target}…")
    benchmarks_code = generate_benchmarks(target, model=model, dry_run=dry_run)
    Path(output).write_text(benchmarks_code, encoding="utf-8")
    _console.print(f"[green]✓ Saved {output}[/]")
    _console.print(f"[dim]Edit {output} then run: darwinloop evolve {target} --tasks {output}[/]")


@app.command(name="report")
def show_report(
    archive: str = typer.Argument("darwinloop_output", help="Path to the archive directory."),
) -> None:
    """Show a summary report from a previous evolution run.

    Example::

        darwinloop report darwinloop_output/
    """
    archive_json = Path(archive) / "archive.json"
    if not archive_json.exists():
        _console.print(f"[red]Archive not found: {archive_json}[/]")
        raise typer.Exit(1)

    from darwinloop.core.archive import AgentArchive
    arc = AgentArchive.load(str(archive_json))
    arc.print_tree()
    arc.print_table()
    s = arc.stats()
    _console.print(
        f"\n  Best score: [bold cyan]{s['best_score']:.2f}[/] | "
        f"Best agent: [bold]{s['best_agent_id']}[/] | "
        f"Max generation: {s['max_generation']}"
    )


@app.command(name="diff")
def show_diff(
    archive: str = typer.Argument("darwinloop_output", help="Path to the archive directory."),
    from_agent: str = typer.Option("agent_0000", "--from", help="Source agent ID."),
    to_agent: Optional[str] = typer.Option(None, "--to", help="Target agent ID (default: best)."),
) -> None:
    """Show the unified diff between two agent generations.

    Example::

        darwinloop diff darwinloop_output/ --from agent_0000 --to agent_0003
    """
    import difflib

    archive_json = Path(archive) / "archive.json"
    if not archive_json.exists():
        _console.print(f"[red]Archive not found: {archive_json}[/]")
        raise typer.Exit(1)

    from darwinloop.core.archive import AgentArchive
    arc = AgentArchive.load(str(archive_json))

    try:
        src = arc.get(from_agent)
    except KeyError:
        _console.print(f"[red]Agent {from_agent!r} not found in archive.[/]")
        raise typer.Exit(1)

    if to_agent:
        try:
            dst = arc.get(to_agent)
        except KeyError:
            _console.print(f"[red]Agent {to_agent!r} not found in archive.[/]")
            raise typer.Exit(1)
    else:
        dst = arc.best()
        if dst is None:
            _console.print("[red]No valid agents in archive.[/]")
            raise typer.Exit(1)

    diff = "".join(difflib.unified_diff(
        src.code_snapshot.splitlines(keepends=True),
        dst.code_snapshot.splitlines(keepends=True),
        fromfile=from_agent,
        tofile=dst.agent_id,
    ))
    if diff:
        _console.print(diff)
    else:
        _console.print("[dim]No differences between the two agents.[/]")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_tasks_from_file(path: str) -> list:
    """Import a Python file and collect all BenchmarkTask instances."""
    import importlib.util
    from darwinloop._models import BenchmarkTask

    spec = importlib.util.spec_from_file_location("_user_tasks", path)
    if spec is None or spec.loader is None:
        return []
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    tasks = []
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, BenchmarkTask):
            tasks.append(obj)
        elif isinstance(obj, list) and all(isinstance(t, BenchmarkTask) for t in obj):
            tasks.extend(obj)
    return tasks


def _load_pack(name: str):
    name = name.lower()
    if name == "routing":
        from darwinloop.packs.routing import RoutingPack
        return RoutingPack()
    if name == "commerce":
        from darwinloop.packs.commerce import CommercePack
        return CommercePack()
    if name == "support":
        from darwinloop.packs.support import SupportPack
        return SupportPack()
    return None


if __name__ == "__main__":
    app()
