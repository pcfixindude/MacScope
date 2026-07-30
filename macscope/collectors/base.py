from __future__ import annotations

from abc import ABC, abstractmethod

from inventory import Item


class Collector(ABC):
    name: str

    @abstractmethod
    def collect(self) -> list[Item]:
        ...
