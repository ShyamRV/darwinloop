"""
darwinloop — Self-improvement engine for AI agents.

Based on the Darwin Gödel Machine (DGM) paper, Zhang et al., ICLR 2026.

Quickstart::

    from darwinloop import DarwinLoop, BenchmarkTask

    dl = DarwinLoop(target="my_agent/router.py", model="asi1")
    result = dl.run(iterations=5)
    print(f"Score: {result.base_score:.2f} → {result.best_score:.2f} (+{result.score_delta:.2f})")
    result.apply()
"""

from __future__ import annotations

from darwinloop._api import DarwinLoop
from darwinloop._models import BenchmarkTask, EvolutionResult, GenerationInfo

__all__ = [
    "DarwinLoop",
    "BenchmarkTask",
    "EvolutionResult",
    "GenerationInfo",
]

__version__ = "0.1.0"
__author__ = "Fetch.ai Innovation Lab"
__license__ = "Apache-2.0"
