"""darwinloop core/benchmark.py — Benchmark suite for evaluating agent code."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field

from darwinloop._models import BenchmarkTask
from darwinloop.sandbox.executor import SandboxExecutor
from darwinloop.sandbox.validator import validate_code


@dataclass
class TaskResult:
    """Result for a single benchmark task.

    Attributes:
        task_id: The task's ``id`` field.
        task_name: The task's ``name`` field.
        score: Score in [0.0, 1.0] for this task.
        passed: Whether the task fully passed (score == 1.0).
        stdout: Captured stdout from the sandbox run.
        stderr: Captured stderr from the sandbox run.
        error: Human-readable error message (empty if passed).
    """

    task_id: str
    task_name: str
    score: float
    passed: bool
    stdout: str = ""
    stderr: str = ""
    error: str = ""


@dataclass
class BenchmarkResult:
    """Aggregate result from running all benchmark tasks.

    Attributes:
        score: Weighted mean score across all tasks (0.0–1.0).
        task_results: Per-task results.
        eval_logs: Combined log lines for the LLM's diagnostic prompt.
    """

    score: float
    task_results: list[TaskResult] = field(default_factory=list)
    eval_logs: list[str] = field(default_factory=list)

    @property
    def passed(self) -> list[TaskResult]:
        """Tasks with score == 1.0."""
        return [r for r in self.task_results if r.passed]

    @property
    def failed(self) -> list[TaskResult]:
        """Tasks with score < 1.0."""
        return [r for r in self.task_results if not r.passed]

    def failed_as_dicts(self) -> list[dict]:
        """Return failed tasks as JSON-serialisable dicts for LLM prompts."""
        return [
            {
                "task_id": r.task_id,
                "task_name": r.task_name,
                "score": r.score,
                "error": r.error,
                "stdout": r.stdout[:500],
                "stderr": r.stderr[:500],
            }
            for r in self.failed
        ]


class BenchmarkSuite:
    """Evaluate a code snapshot against a list of :class:`BenchmarkTask` objects.

    Each task is run in an isolated sandbox subprocess. Scoring is proportional:
    each task contributes its ``weight``-adjusted score to the final mean.

    Args:
        tasks: List of benchmark tasks to run.
        target_filename: Filename to use for the agent code inside the sandbox
            (default ``"agent.py"``).
        sandbox_timeout: Per-task timeout in seconds (default 30).
    """

    def __init__(
        self,
        tasks: list[BenchmarkTask],
        target_filename: str = "agent.py",
        sandbox_timeout: int = 30,
    ) -> None:
        self.tasks = tasks
        self.target_filename = target_filename
        self._executor = SandboxExecutor(timeout=sandbox_timeout)

    def evaluate(self, code: str) -> BenchmarkResult:
        """Run all tasks against *code* and return the aggregate result.

        Args:
            code: Python source code of the agent to evaluate.

        Returns:
            :class:`BenchmarkResult` with per-task scores and eval logs.
        """
        # Safety gate — never run code that fails validation
        validation = validate_code(code)
        if not validation.is_safe:
            logs = [f"BLOCKED: {v}" for v in validation.violations]
            return BenchmarkResult(score=0.0, eval_logs=logs)

        task_results: list[TaskResult] = []
        logs: list[str] = []

        for task in self.tasks:
            result = self._run_task(code, task)
            task_results.append(result)
            status = "PASS" if result.passed else "FAIL"
            logs.append(f"[{status}] {task.name} (score={result.score:.2f}): {result.error or 'ok'}")

        # Weighted mean score
        total_weight = sum(t.weight for t in self.tasks)
        if total_weight == 0:
            score = 0.0
        else:
            weighted_sum = sum(
                r.score * t.weight for r, t in zip(task_results, self.tasks)
            )
            score = weighted_sum / total_weight

        return BenchmarkResult(score=score, task_results=task_results, eval_logs=logs)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run_task(self, code: str, task: BenchmarkTask) -> TaskResult:
        """Run one task in the sandbox and return its result."""
        test_script = self._build_test_script(task)
        exec_result = self._executor.run_module_with_test(
            module_code=code,
            module_filename=self.target_filename,
            test_code=test_script,
        )

        if exec_result.timed_out:
            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                score=0.0,
                passed=False,
                stderr=exec_result.stderr,
                error="Sandbox timeout",
            )

        if exec_result.exit_code != 0:
            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                score=0.0,
                passed=False,
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
                error=exec_result.stderr[:200] or "Non-zero exit code",
            )

        # Parse score from stdout: expect "SCORE:0.75" or "PASS" / "FAIL"
        stdout = exec_result.stdout.strip()
        score = _parse_score(stdout)
        passed = score >= 1.0

        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            score=score,
            passed=passed,
            stdout=stdout,
            stderr=exec_result.stderr,
            error="" if passed else f"Got: {stdout[:120]}",
        )

    def _build_test_script(self, task: BenchmarkTask) -> str:
        """Generate a self-contained test runner script for *task*."""
        target_module = self.target_filename.replace(".py", "")
        inputs = task.input_sequence if task.input_sequence else [task.input]

        checks = []
        for i, inp in enumerate(inputs):
            checks.append(f"    result_{i} = str(run({inp!r}))")

        final_result = f"result_{len(inputs) - 1}"
        expected_check = ""
        if task.expected:
            expected_check = f"""
if {task.expected!r}.lower() not in {final_result}.lower():
    print(f"FAIL: expected {task.expected!r} in output, got: {{{final_result}[:120]}}")
    sys.exit(0)
"""
        must_not_check = ""
        if task.must_not_contain:
            must_not_check = f"""
if {task.must_not_contain!r}.lower() in {final_result}.lower():
    print(f"FAIL: output must not contain {task.must_not_contain!r}, got: {{{final_result}[:120]}}")
    sys.exit(0)
"""

        script = textwrap.dedent(f"""
import sys
import importlib.util
import os

# Load the agent module
spec = importlib.util.spec_from_file_location("{target_module}", "{target_module}.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["{target_module}"] = mod
spec.loader.exec_module(mod)

def run(question):
    # Try common entry points
    for fn_name in ("route_question", "run", "process", "handle", "predict", "classify"):
        fn = getattr(mod, fn_name, None)
        if fn:
            try:
                result = fn(question)
                if hasattr(result, "intent"):
                    return result.intent
                return str(result)
            except Exception as e:
                return f"ERROR: {{e}}"
    return "ERROR: no entry point found (tried route_question, run, process, handle, predict, classify)"

try:
{chr(10).join(checks)}
except Exception as e:
    print(f"FAIL: exception during run: {{e}}")
    sys.exit(0)

{expected_check}
{must_not_check}
print("SCORE:1.0")
""")
        return script


def _parse_score(stdout: str) -> float:
    """Parse the score emitted by the test runner.

    Accepts ``SCORE:0.75`` format, or ``PASS``/``FAIL``.
    """
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("SCORE:"):
            try:
                return float(line.split(":", 1)[1])
            except ValueError:
                pass
        if line == "PASS":
            return 1.0
        if line == "FAIL":
            return 0.0
    # If process exited 0 but no explicit score, assume pass
    return 1.0 if stdout and "FAIL" not in stdout and "ERROR" not in stdout else 0.0
