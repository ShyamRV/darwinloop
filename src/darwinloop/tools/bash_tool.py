"""darwinloop tools/bash_tool.py — Bash execution tool for the LLM."""

from __future__ import annotations

import subprocess
import sys

BASH_TOOL = {
    "name": "bash",
    "description": (
        "Run a bash/shell command in the sandbox directory. "
        "Use for reading files, listing directories, and running quick checks. "
        "Do NOT use for network requests or destructive operations."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."},
        },
        "required": ["command"],
    },
}


def bash_tool(command: str, cwd: str | None = None, timeout: int = 15) -> str:
    """Execute *command* and return combined stdout + stderr.

    Args:
        command: Shell command string.
        cwd: Working directory (defaults to current directory).
        timeout: Maximum execution time in seconds.

    Returns:
        Combined stdout/stderr output, capped at 4000 characters.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:4000] if len(output) > 4000 else output
    except subprocess.TimeoutExpired:
        return f"TimeoutError: command exceeded {timeout}s"
    except Exception as exc:
        return f"Error: {exc}"
