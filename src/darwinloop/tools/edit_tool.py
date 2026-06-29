"""darwinloop tools/edit_tool.py — Precise file editor tool for the LLM."""

from __future__ import annotations

from pathlib import Path

EDIT_TOOL = {
    "name": "editor",
    "description": (
        "Read and edit files using precise commands. "
        "Prefer 'str_replace' over 'create' to make surgical changes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["view", "str_replace", "create"],
                "description": (
                    "'view' — show file contents with line numbers. "
                    "'str_replace' — replace an exact unique string in the file. "
                    "'create' — write an entirely new file (use sparingly)."
                ),
            },
            "path": {"type": "string", "description": "File path (relative to sandbox root)."},
            "old_str": {
                "type": "string",
                "description": "[str_replace only] The exact string to find and replace. Must be unique in the file.",
            },
            "new_str": {
                "type": "string",
                "description": "[str_replace / create] The replacement string or new file content.",
            },
            "view_range": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "[view only] Optional [start_line, end_line] to limit output.",
            },
        },
        "required": ["command", "path"],
    },
}


def editor_tool(
    command: str,
    path: str,
    old_str: str = "",
    new_str: str = "",
    view_range: list[int] | None = None,
    cwd: str | None = None,
) -> str:
    """Execute a file editing command.

    Args:
        command: One of ``"view"``, ``"str_replace"``, or ``"create"``.
        path: File path (relative to *cwd* if not absolute).
        old_str: [str_replace] String to find (must be unique in file).
        new_str: [str_replace / create] Replacement or new content.
        view_range: [view] Optional ``[start, end]`` line range.
        cwd: Working directory for resolving relative paths.

    Returns:
        Human-readable result string.
    """
    from pathlib import Path as _Path

    p = _Path(path)
    if cwd and not p.is_absolute():
        p = _Path(cwd) / p

    if command == "view":
        return _view(p, view_range)
    if command == "str_replace":
        return _str_replace(p, old_str, new_str)
    if command == "create":
        return _create(p, new_str)
    return f"Error: unknown command '{command}'. Use 'view', 'str_replace', or 'create'."


def _view(path: Path, view_range: list[int] | None) -> str:
    if not path.exists():
        return f"Error: file not found: {path}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if view_range and len(view_range) == 2:
        start = max(0, view_range[0] - 1)
        end = view_range[1]
        lines = lines[start:end]
        offset = view_range[0]
    else:
        offset = 1
    numbered = "\n".join(f"{i + offset:4d} | {line}" for i, line in enumerate(lines))
    return f"File: {path}\n\n{numbered}"


def _str_replace(path: Path, old_str: str, new_str: str) -> str:
    if not old_str:
        return "Error: 'old_str' is required for str_replace."
    if not path.exists():
        return f"Error: file not found: {path}"
    content = path.read_text(encoding="utf-8")
    count = content.count(old_str)
    if count == 0:
        return f"Error: old_str not found in {path.name}. Check for exact whitespace/indentation."
    if count > 1:
        return (
            f"Error: old_str appears {count} times — it must be unique. "
            "Include more surrounding context to make it unique."
        )
    new_content = content.replace(old_str, new_str, 1)
    path.write_text(new_content, encoding="utf-8")
    changed = new_content.count("\n") - content.count("\n")
    return f"Replaced 1 occurrence in {path.name} ({'+' if changed >= 0 else ''}{changed} lines)."


def _create(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    lines = content.count("\n") + 1
    return f"Created {path.name} ({lines} lines)."
