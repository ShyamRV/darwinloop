"""darwinloop sandbox/validator.py — AST-based safety validation."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

_BLOCKED_CALLS = {"exec", "eval", "compile", "__import__"}
_BLOCKED_SHELL = {"os.system", "subprocess.call", "subprocess.run"}


@dataclass
class ValidationResult:
    """Result of static code analysis.

    Attributes:
        is_safe: ``True`` if no blocking issues found. Warnings alone do not
            set this to ``False``.
        violations: List of blocking issue descriptions.
        warnings: List of non-blocking advisory messages.
    """

    is_safe: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def all_messages(self) -> list[str]:
        """All violations + warnings combined."""
        return self.violations + self.warnings


class _SafetyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[str] = []
        self.warnings: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Only block bare name calls (e.g. eval(), exec(), compile()).
        # Attribute calls like re.compile() or obj.eval() are intentional
        # uses of library methods and must NOT be blocked.
        if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_CALLS:
            self.violations.append(
                f"Line {node.lineno}: blocked call '{node.func.id}()' — "
                "use darwinloop sandbox instead"
            )

        # subprocess with shell=True
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("call", "run", "Popen"):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value:
                    self.violations.append(
                        f"Line {node.lineno}: subprocess with shell=True is blocked"
                    )

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        _WARN_IMPORTS = {"socket", "requests", "httpx", "urllib", "ftplib", "smtplib", "paramiko"}
        for alias in node.names:
            base = alias.name.split(".")[0]
            if base in _WARN_IMPORTS:
                self.warnings.append(
                    f"Line {node.lineno}: network import '{alias.name}' — "
                    "sandbox blocks network; this will fail at runtime"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        _WARN_IMPORTS = {"socket", "requests", "httpx", "urllib", "ftplib", "smtplib", "paramiko"}
        module = node.module or ""
        base = module.split(".")[0]
        if base in _WARN_IMPORTS:
            self.warnings.append(
                f"Line {node.lineno}: network import from '{module}' — "
                "sandbox blocks network; this will fail at runtime"
            )
        self.generic_visit(node)


def validate_code(code: str) -> ValidationResult:
    """Validate Python source code for safety issues.

    This is the first gate in the darwinloop safety pipeline. Code that
    fails here is **never executed**.

    Args:
        code: Python source code string.

    Returns:
        :class:`ValidationResult` with ``is_safe``, ``violations``, and
        ``warnings``.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ValidationResult(is_safe=False, violations=[f"SyntaxError: {e}"])

    visitor = _SafetyVisitor()
    visitor.visit(tree)
    return ValidationResult(
        is_safe=len(visitor.violations) == 0,
        violations=visitor.violations,
        warnings=visitor.warnings,
    )


def validate_file(path: str) -> ValidationResult:
    """Convenience wrapper: read *path* then call :func:`validate_code`.

    Args:
        path: Path to a Python source file.

    Returns:
        :class:`ValidationResult`.
    """
    try:
        from pathlib import Path
        return validate_code(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ValidationResult(is_safe=False, violations=[f"File not found: {path}"])
    except Exception as e:
        return ValidationResult(is_safe=False, violations=[f"Could not read file: {e}"])
