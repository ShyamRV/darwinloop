"""Tests for darwinloop sandbox (executor + validator)."""


from darwinloop.sandbox.executor import SandboxExecutor
from darwinloop.sandbox.validator import validate_code

# ── Executor tests ────────────────────────────────────────────────────────────

def test_run_simple_code() -> None:
    ex = SandboxExecutor(timeout=10)
    result = ex.run_code("print('hello darwinloop')")
    assert result.success
    assert "hello darwinloop" in result.stdout


def test_run_code_failure() -> None:
    ex = SandboxExecutor(timeout=10)
    result = ex.run_code("raise ValueError('intentional error')")
    assert not result.success
    assert result.exit_code != 0


def test_run_code_timeout() -> None:
    ex = SandboxExecutor(timeout=1)
    result = ex.run_code("import time; time.sleep(10)")
    assert not result.success
    assert result.timed_out


def test_run_module_with_test() -> None:
    module = "def greet(name):\n    return f'Hello, {name}!'\n"
    test = (
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('m', 'mod.py')\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "sys.modules['m'] = mod\n"
        "spec.loader.exec_module(mod)\n"
        "assert mod.greet('world') == 'Hello, world!'\n"
        "print('SCORE:1.0')\n"
    )
    ex = SandboxExecutor(timeout=10)
    result = ex.run_module_with_test(module, "mod.py", test)
    assert result.success
    assert "SCORE:1.0" in result.stdout


def test_extra_files() -> None:
    helper = "VALUE = 42\n"
    main = "import helper; print(helper.VALUE)\n"
    ex = SandboxExecutor(timeout=10)
    result = ex.run_code(main, filename="main.py", extra_files={"helper.py": helper})
    assert result.success
    assert "42" in result.stdout


# ── Validator tests ───────────────────────────────────────────────────────────

def test_safe_code_passes() -> None:
    code = "def add(a, b):\n    return a + b\n"
    result = validate_code(code)
    assert result.is_safe
    assert not result.violations


def test_eval_blocked() -> None:
    code = "x = eval('1+1')\n"
    result = validate_code(code)
    assert not result.is_safe
    assert any("eval" in v for v in result.violations)


def test_exec_blocked() -> None:
    code = "exec('import os')\n"
    result = validate_code(code)
    assert not result.is_safe


def test_syntax_error_blocked() -> None:
    code = "def broken(\n"
    result = validate_code(code)
    assert not result.is_safe
    assert any("SyntaxError" in v for v in result.violations)


def test_network_import_warning() -> None:
    code = "import requests\n"
    result = validate_code(code)
    # requests import is a warning, not a blocking violation
    assert result.is_safe
    assert any("requests" in w for w in result.warnings)


def test_subprocess_shell_true_blocked() -> None:
    code = "import subprocess\nsubprocess.run('ls', shell=True)\n"
    result = validate_code(code)
    assert not result.is_safe


def test_re_compile_allowed() -> None:
    """re.compile() must NOT be blocked — it's a library call, not the built-in compile()."""
    code = "import re\npattern = re.compile(r'\\w+')\n"
    result = validate_code(code)
    assert result.is_safe, f"re.compile() was wrongly blocked: {result.violations}"


def test_builtin_compile_blocked() -> None:
    """The bare compile() built-in IS blocked as it compiles arbitrary code."""
    code = "compile('x=1', '<string>', 'exec')\n"
    result = validate_code(code)
    assert not result.is_safe
    assert any("compile" in v for v in result.violations)
