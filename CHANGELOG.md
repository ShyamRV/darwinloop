# darwinloop — Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-06-29

### Added
- `DarwinLoop` — main evolution loop (benchmark → diagnose → improve → re-benchmark → keep if better)
- `BenchmarkTask` — task definition with single-turn, multi-turn, and negative assertion support
- `EvolutionResult` — rich result object with `.apply()`, `.save_report()`, `.diff`, `.to_dict()`
- `AgentArchive` — thread-safe, immutable JSON archive of all generated agents
- `ParentSelector` — sigmoid-weighted novelty-boosted parent sampling (DGM paper Algorithm 1)
- `SelfImprover` — two-step LLM pipeline: diagnose failures → implement fix using editor tools
- `BenchmarkSuite` — sandboxed, proportional-scoring benchmark runner
- `SandboxExecutor` — isolated subprocess execution with hard timeouts
- AST validator — blocks `eval`, `exec`, `shell=True` before any code runs
- `LLMClient` — unified client for ASI:One (default), Anthropic Claude, OpenAI GPT
- `MockLLMClient` — deterministic dry-run mode (no API key, zero cost)
- `RoutingPack`, `CommercePack`, `SupportPack` — pre-built domain benchmark packs
- `darwinloop scaffold` — auto-generate benchmark tasks from agent source code
- `darwinloop report` — view archive summary from a previous run
- `darwinloop diff` — compare any two generations
- 38-test suite covering archive, selector, benchmark, sandbox, and CLI
- Examples: quickstart router + real football-agent router (0.51 → 0.80 in 5 iterations)
- `SECURITY.md` — full documentation of all 10 safety guarantees

[0.1.0]: https://github.com/fetchai/darwinloop/releases/tag/v0.1.0
