# darwinloop × news-agent

This example shows darwinloop autonomously improving the news-agent's
`headline_store.py` headline routing logic in **5 iterations**.

## What darwinloop evolved

| Metric | Before | After |
|---|---|---|
| Benchmark score | 0.30 | **0.60** |
| Tasks passing | 3/10 | 6/10 |
| Improvement | — | **+0.30** |

### Change 1 — Extended digit range (iteration 1)

**Before** — only matched headlines 1 through 5:
```python
_DIGIT_RE = re.compile(r"\b(?:headline|news|story|article|item)?\s*#?\s*([1-5])\b", ...)
```

**After** — matches any single digit 1–9:
```python
_DIGIT_RE = re.compile(r"\b(?:headline|news|story|article|item)?\s*#?\s*([1-9])\b", ...)
```

Now `"show me story 7"` and `"headline 9"` work correctly.

### Change 2 — Extended ordinal vocabulary (iteration 3)

**Before** — ordinals only up to "fifth":
```python
_ORDINAL_WORDS = { "first": 1, ..., "fifth": 5 }
_ORDINAL_RE = re.compile(r"\b(first|...|fifth|5th|...)\b", ...)
```

**After** — ordinals through "tenth":
```python
_ORDINAL_WORDS = { "first": 1, ..., "fifth": 5, "sixth": 6, "seventh": 7,
                   "eighth": 8, "ninth": 9, "tenth": 10, ... }
_ORDINAL_RE = re.compile(r"\b(first|...|tenth|10th|...)\b", ...)
```

Now `"go deeper on the sixth"` and `"more on the ninth story"` work.

## Files

- `news_router.py` — Original extracted routing logic (the target file)
- `news_router_evolved.py` — Best evolved version (agent_0003, score=0.60)
- `benchmarks.py` — 10 benchmark tasks used for evaluation

## Run it yourself

```bash
cd darwinloop

# Dry run (no LLM, see base score)
darwinloop evolve examples/news/news_router.py \
  --tasks examples/news/benchmarks.py \
  --dry-run --auto

# Real run with ASI:One
export ASI1_API_KEY=your_key_here
darwinloop evolve examples/news/news_router.py \
  --tasks examples/news/benchmarks.py \
  --iterations 5 --model asi1 --auto
```

## Evolution family tree

```
🌱 agent_0000  0.30  GEN 0  (BASE)
├── agent_0001  0.40  GEN 1  Expanded _DIGIT_RE [1-5] → [1-9]
│   └── agent_0003  0.60  GEN 2  ⭐ BEST  Added ordinals sixth–tenth
│       └── agent_0004  0.60  GEN 3  (no further gain)
└── agent_0002  0.40  GEN 1  Expanded _DIGIT_RE (parallel branch)
    └── agent_0005  0.60  GEN 2  Extended ordinals
```

The improvements were applied back to
`agents/news-agent/ai/headline_store.py` automatically.
