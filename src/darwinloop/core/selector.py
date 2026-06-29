"""darwinloop core/selector.py — Sigmoid-weighted, novelty-boosted parent selection."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from darwinloop.core.archive import AgentArchive, AgentEntry


class ParentSelector:
    """Sample parents for the next generation using DGM's open-ended selection.

    Combines benchmark performance (via sigmoid) with a novelty bonus that
    rewards under-explored agents, preventing collapse to a single lineage.

    Formula (DGM paper Appendix C.2)::

        sigmoid_score  = 1 / (1 + exp(-λ · (score - α₀)))
        novelty_bonus  = 1 / (1 + |valid_children|)
        weight         = sigmoid_score × novelty_bonus
        P(agent)       = weight / Σ weights

    Args:
        sigmoid_lambda: Sharpness of the sigmoid (default 10.0).
        sigmoid_alpha0: Centre of the sigmoid — agents near this score get
            probability ≈ 0.5 (default 0.5).
    """

    def __init__(
        self,
        sigmoid_lambda: float = 10.0,
        sigmoid_alpha0: float = 0.5,
    ) -> None:
        self.lam = sigmoid_lambda
        self.alpha0 = sigmoid_alpha0

    def select(self, archive: "AgentArchive", k: int) -> list["AgentEntry"]:
        """Sample *k* parents (with replacement) from *archive*.

        All valid agents have non-zero probability — this is the open-ended
        exploration guarantee from the DGM paper.

        Args:
            archive: The populated agent archive.
            k: Number of parents to sample.

        Returns:
            List of *k* :class:`AgentEntry` objects.

        Raises:
            ValueError: If the archive has no valid agents.
        """
        weighted = self._weights(archive)
        if not weighted:
            raise ValueError("Archive has no valid agents to select from.")

        agents, weights = zip(*weighted)
        total = sum(weights)
        probs = [w / total for w in weights]

        selected: list[AgentEntry] = []
        for _ in range(k):
            r = random.random()
            cumulative = 0.0
            for agent, p in zip(agents, probs):
                cumulative += p
                if r <= cumulative:
                    selected.append(agent)
                    break
            else:
                selected.append(agents[-1])
        return selected

    def probabilities(self, archive: "AgentArchive") -> list[tuple["AgentEntry", float]]:
        """Return ``(agent, probability)`` pairs sorted by descending probability.

        Args:
            archive: The populated agent archive.

        Returns:
            Sorted list of ``(AgentEntry, probability)`` tuples.
        """
        weighted = self._weights(archive)
        if not weighted:
            return []
        agents, weights = zip(*weighted)
        total = sum(weights)
        probs = [w / total for w in weights]
        return sorted(zip(agents, probs), key=lambda t: -t[1])

    # ── Internal ──────────────────────────────────────────────────────────────

    def _sigmoid(self, score: float) -> float:
        return 1.0 / (1.0 + math.exp(-self.lam * (score - self.alpha0)))

    def _weights(
        self, archive: "AgentArchive"
    ) -> list[tuple["AgentEntry", float]]:
        eligible = [a for a in archive.valid() if a.benchmark_score < 1.0]
        if not eligible:
            eligible = archive.valid()

        results: list[tuple[AgentEntry, float]] = []
        for agent in eligible:
            sig = self._sigmoid(agent.benchmark_score)
            valid_children = sum(
                1
                for cid in agent.children_ids
                if archive._agents.get(cid) and archive._agents[cid].is_valid
            )
            novelty = 1.0 / (1.0 + valid_children)
            results.append((agent, sig * novelty))
        return results
