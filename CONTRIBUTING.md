# Contributing to darwinloop

Thank you for your interest in contributing! darwinloop is an Apache 2.0 open source
project and welcomes contributions from the community.

---

## Quick Start

```bash
git clone https://github.com/fetchai/darwinloop
cd darwinloop
pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest tests/ -v
```

Run the linter and type checker:

```bash
ruff check src/ tests/
mypy src/
```

---

## Project Structure

```
src/darwinloop/
├── _api.py          # DarwinLoop class (main entry point)
├── _models.py       # BenchmarkTask, EvolutionResult, GenerationInfo
├── core/            # Archive, Selector, Improver, BenchmarkSuite
├── sandbox/         # Executor + AST Validator
├── llm/             # LLMClient (ASI:One / Anthropic / OpenAI) + Mock
├── tools/           # bash_tool, editor_tool
├── packs/           # RoutingPack, CommercePack, SupportPack
├── report.py        # Markdown report generator
├── scaffold.py      # Auto-generate benchmarks from agent code
└── cli.py           # Typer CLI
```

---

## How to Contribute

### Adding a new BenchmarkPack

1. Create `src/darwinloop/packs/<domain>.py`
2. Subclass `BenchmarkPack` and implement the `tasks` property
3. Export it from `src/darwinloop/packs/__init__.py`
4. Add a `--pack <domain>` case to `cli.py`

### Improving the LLM client

The LLM client is in `src/darwinloop/llm/client.py`. To add a new provider:

1. Add a new branch in `LLMClient.__init__` and `_call`
2. Update `get_llm_client` auto-detection logic
3. Add a test in `tests/` (mock the API call)

### Adding safety checks

The AST validator is in `src/darwinloop/sandbox/validator.py`. Add new
`visit_*` methods to `_SafetyVisitor` to block additional dangerous patterns.
Always add a test for the new check.

---

## Code Standards

- **Type hints**: All public APIs must have full type hints (mypy strict passes).
- **Docstrings**: All public classes and methods use Google-style docstrings.
- **No hardcoded paths or secrets**: Use constructor parameters or env vars.
- **Rich output**: Use `rich.console.Console` for all user-facing output.
- **Tests**: Every new public function/class should have at least one test.

---

## Pull Request Process

1. Fork the repo and create a branch from `main`.
2. Make your changes.
3. Run `pytest`, `ruff check`, and `mypy` — all must pass.
4. Open a pull request with a clear description of what changed and why.

---

## License

By contributing, you agree that your contribution will be licensed under the
Apache 2.0 License.
