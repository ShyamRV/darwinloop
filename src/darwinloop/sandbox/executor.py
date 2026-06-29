"""darwinloop sandbox/executor.py — Isolated subprocess-based code execution."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    """Result of running code in the sandbox.

    Attributes:
        stdout: Captured standard output (capped at 50 000 chars).
        stderr: Captured standard error (capped at 50 000 chars).
        exit_code: Process exit code (0 = success).
        timed_out: ``True`` if the process exceeded the timeout.
    """

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False

    @property
    def success(self) -> bool:
        """``True`` iff exit code is 0 and the process did not time out."""
        return self.exit_code == 0 and not self.timed_out


class SandboxExecutor:
    """Execute Python code in an isolated temporary directory.

    Every execution:

    * Gets a fresh UUID-named temp directory.
    * Runs as a child process (never in the darwinloop process).
    * Is killed after *timeout* seconds.
    * Has its output capped at 50 000 characters.
    * Has its temp directory deleted on completion.

    Args:
        timeout: Maximum execution time in seconds (default 30).
    """

    MAX_OUTPUT = 50_000

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def run_code(
        self,
        code: str,
        filename: str = "agent.py",
        extra_files: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Write *code* to a fresh sandbox and execute it.

        Args:
            code: Python source code to execute.
            filename: Name for the main file inside the sandbox.
            extra_files: Optional ``{filename: content}`` helper files.

        Returns:
            :class:`ExecutionResult` with stdout, stderr, exit_code, timed_out.
        """
        sandbox = Path(tempfile.gettempdir()) / f"darwinloop_{uuid.uuid4().hex[:8]}"
        sandbox.mkdir(parents=True, exist_ok=True)
        try:
            (sandbox / filename).write_text(code, encoding="utf-8")
            if extra_files:
                for fname, content in extra_files.items():
                    (sandbox / fname).write_text(content, encoding="utf-8")
            return self._run(sandbox / filename, sandbox)
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

    def run_module_with_test(
        self,
        module_code: str,
        module_filename: str,
        test_code: str,
    ) -> ExecutionResult:
        """Write a module + a test runner to sandbox, then run the test.

        Used by :class:`~darwinloop.core.benchmark.BenchmarkSuite` to evaluate
        each agent snapshot in isolation.

        Args:
            module_code: The agent code being evaluated.
            module_filename: Filename for the module (e.g. ``"router.py"``).
            test_code: The test runner script to execute.

        Returns:
            :class:`ExecutionResult`.
        """
        sandbox = Path(tempfile.gettempdir()) / f"darwinloop_{uuid.uuid4().hex[:8]}"
        sandbox.mkdir(parents=True, exist_ok=True)
        try:
            (sandbox / module_filename).write_text(module_code, encoding="utf-8")
            runner = sandbox / "_runner.py"
            runner.write_text(test_code, encoding="utf-8")
            return self._run(runner, sandbox)
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self, script: Path, cwd: Path) -> ExecutionResult:
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(cwd),
            )
            return ExecutionResult(
                stdout=proc.stdout[: self.MAX_OUTPUT],
                stderr=proc.stderr[: self.MAX_OUTPUT],
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                stdout="",
                stderr=f"TimeoutError: exceeded {self.timeout}s",
                exit_code=1,
                timed_out=True,
            )
        except Exception as exc:
            return ExecutionResult(stdout="", stderr=f"ExecutionError: {exc}", exit_code=1)
