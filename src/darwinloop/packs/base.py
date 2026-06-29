"""darwinloop packs/base.py — Base class for benchmark packs."""

from __future__ import annotations

from abc import ABC, abstractmethod

from darwinloop._models import BenchmarkTask


class BenchmarkPack(ABC):
    """Base class for pre-built domain benchmark packs.

    Subclasses define a :attr:`tasks` property returning a list of
    :class:`~darwinloop._models.BenchmarkTask` objects covering their domain.

    Example::

        from darwinloop.packs import RoutingPack
        from darwinloop import DarwinLoop

        dl = DarwinLoop(
            target="agent/router.py",
            pack=RoutingPack(intents=["live", "team", "competition"]),
        )
    """

    @property
    @abstractmethod
    def tasks(self) -> list[BenchmarkTask]:
        """Return the list of benchmark tasks in this pack."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({len(self.tasks)} tasks)"
