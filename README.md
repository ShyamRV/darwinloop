# darwinloop

[![PyPI version](https://img.shields.io/pypi/v/darwinloop.svg)](https://pypi.org/project/darwinloop/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](#)

**darwinloop — self-improvement engine for AI agents**

Point darwinloop at any Python agent, define what "good" looks like with benchmark tasks, and darwinloop will autonomously improve the code — iteration by iteration — using an LLM, without you writing a single patch.

Based on the [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954) (Zhang et al., ICLR 2026).

---

## Why darwinloop?

- **Measurable gains.** The football-score-agent router went from **51% → 80%** accuracy in 5 iterations — 16 more teams recognised, pronoun follow-ups fixed, competition-vs-team routing corrected. Zero manual patches.
- **Fully auditable.** Every change is recorded as a unified diff. Every generation is preserved in an immutable JSON archive. Roll back anytime.
- **Works on any Python agent.** uAgents, LangChain, LangGraph, raw Python — if it's a `.py` file, darwinloop can evolve it.

---

## Quickstart

```bash
pip install darwinloop
```

```python
from darwinloop import DarwinLoop, BenchmarkTask

tasks = [
    BenchmarkTask(id="t1", name="live_scores",
                  input="live scores now", expected="live"),
    BenchmarkTask(id="t2", name="vs_competition",
                  input="Arsenal vs Chelsea result", expected="competition"),
]

dl = DarwinLoop(target="my_agent/router.py", tasks=tasks, model="asi1")
result = dl.run(iterations=5)

print(f"Score: {result.base_score:.2f} → {result.best_score:.2f} (+{result.score_delta:.2f})")
result.apply()            # write best version back to router.py
result.save_report()      # save darwinloop_report.md
```

**Expected output:**

```
darwinloop  — self-improvement engine for AI agents

Evaluating base agent (router.py)…
  ✓ agent_0000: score=0.51 (5/10 tasks passed)

── ITERATION 1/5 ──────────────────────────────────────────
  Selected parents: ['agent_0000']
  Proposal: Add pronoun (they/them/their) follow-up handling using ctx.last_team
    Evaluating… score=0.60
  agent_0000 → agent_0001  Score: 0.51 → 0.60 (+0.09)

[… 4 more iterations …]

Evolution complete!  Score: 0.51 → 0.80  (+0.29  best: agent_0004  gen 4)
```

---

## How it works

```
Your agent code
      │
      ▼
┌─────────────┐
│  Benchmark  │  Run tasks in isolated sandbox → score (0.0–1.0)
└──────┬──────┘
       │ failures
       ▼
┌─────────────┐
│  Diagnose   │  LLM analyses code + failures → improvement proposal
└──────┬──────┘
       │ proposal
       ▼
┌─────────────┐
│   Improve   │  LLM uses editor tools (str_replace) to apply change
└──────┬──────┘
       │ new code
       ▼
┌─────────────┐
│  Re-score   │  Run benchmarks again on new code
└──────┬──────┘
       │ score > old?
      YES → keep it (add to archive)
       NO → discard it (archive still records it for open-ended exploration)
       │
       └── repeat N iterations
```

---

## LLM Support

| Provider | Model | Set env var |
|----------|-------|-------------|
| ASI:One (default) | `asi1` | `ASI1_API_KEY` |
| Anthropic | `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Mock (free) | — | `--dry-run` |

Get an ASI:One API key at [asi1.ai](https://asi1.ai) — it's the Fetch.ai ecosystem LLM.

---

## Benchmark Packs

Pre-built domain packs so you don't need to write tasks from scratch:

```python
from darwinloop import DarwinLoop
from darwinloop.packs import RoutingPack, CommercePack, SupportPack

# Routing agent (intent classification)
dl = DarwinLoop(target="agent/router.py",
                pack=RoutingPack(intents=["live", "team", "competition", "fixtures"]))

# Commerce agent (product search, cart, checkout)
dl = DarwinLoop(target="agent/shop.py", pack=CommercePack())

# Customer support agent
dl = DarwinLoop(target="agent/support.py", pack=SupportPack())
```

---

## CLI Reference

```bash
# Evolve a specific file
darwinloop evolve agent/router.py --iterations 5 --model asi1

# Dry run (free, no API key needed)
darwinloop evolve agent/ --dry-run --auto

# Use a built-in benchmark pack
darwinloop evolve agent/router.py --pack routing --iterations 5

# Load benchmarks from a file
darwinloop evolve agent/router.py --tasks benchmarks.py --iterations 10

# Auto-generate benchmarks from agent code
darwinloop scaffold agent/router.py --output benchmarks.py

# View a previous run report
darwinloop report darwinloop_output/

# Diff two generations
darwinloop diff darwinloop_output/ --from agent_0000 --to agent_0004
```

---

## Real Example: Football Agent

The `examples/football/` directory contains the real football-score-agent router and its benchmark tasks.

```bash
darwinloop evolve examples/football/football_router.py \
    --tasks examples/football/benchmarks.py \
    --iterations 5 --model asi1
```

DGM-discovered improvements in 5 iterations:

| # | Improvement | Score impact |
|---|-------------|-------------|
| 1 | Pronoun follow-up (they/their/them → last team) | +0.09 |
| 2 | +16 clubs (Juventus, Atletico, Napoli, Dortmund…) | +0.08 |
| 3 | Competition-signal priority (`vs`, `result`, `score`) | +0.07 |
| 4 | Fixture regex expansion (`next game`, `upcoming game`) | +0.05 |

**Total: 0.51 → 0.80 (+0.29)**

---

## Safety

darwinloop is designed to be the most trustworthy self-improvement library available.

| Guarantee | Implementation |
|-----------|---------------|
| AST validation before execution | `sandbox/validator.py` blocks `eval`, `exec`, `shell=True` |
| Subprocess isolation | All agent code runs in a child process, never in the darwinloop process |
| Hard timeouts | Sandbox default 30s, configurable via `sandbox_timeout` |
| No network in sandbox | Network imports trigger warnings; calls fail at runtime |
| Immutable archive | `AgentEntry` records are never modified after creation |
| Diff transparency | Every change recorded as unified diff |
| Revert anytime | All generations preserved; load archive and roll back |
| Dry run mode | `MockLLMClient` tests full pipeline at zero cost |
| Score regression protection | New code kept **only** if score strictly improves |
| Human checkpoints | In non-`--auto` mode, prompts before each iteration |

See [SECURITY.md](SECURITY.md) for full details.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
