# Football Example

This example uses the real football-score-agent router as the target, with 10 benchmark tasks covering the main failure modes darwinloop discovered and fixed.

## Results

| Iteration | Score | Improvement |
|-----------|-------|-------------|
| 0 (base) | 0.51 | — |
| 1 | 0.60 | Pronoun (they/their/them) follow-up using `ctx.last_team` |
| 2 | 0.68 | +16 clubs (Juventus, Atletico Madrid, Napoli, BVB…) |
| 3 | 0.75 | Competition-signal priority (`vs`, `result`, `score`) |
| 4 | 0.80 | Fixture regex expansion (`next game`, `upcoming game`) |

## Run

```bash
# From the darwinloop/ root:
darwinloop evolve examples/football/football_router.py \
    --tasks examples/football/benchmarks.py \
    --iterations 5 --model asi1 --auto

# Dry run (no API key, free):
darwinloop evolve examples/football/football_router.py \
    --tasks examples/football/benchmarks.py \
    --dry-run --auto --iterations 3
```
