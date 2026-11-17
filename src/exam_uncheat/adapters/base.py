"""Adapter (driver) interface.

An adapter turns *any* receive-only RF hardware into a stream of
``exam-uncheat.event/v1`` dicts. Adapters MUST NOT transmit: no active scans,
no probe/scan requests, no connections, no injection, no jamming.

Minimal adapter::

    class MyDetector(Adapter):
        name = "my-detector"
        def run(self):
            while not self.stopped:
                reading = read_my_device()
                self.emit({"schema": "exam-uncheat.event/v1",
                           "sensor": {"id": "det-1", "driver": self.name},
                           "kind": "detector.alert",
                           "attrs": {"level": reading.level, "vendor": "ACME"}})
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Callable, Protocol


class EventSink(Protocol):
    def __call__(self, obj: dict) -> None: ...


class Adapter(ABC):
    name: str = "adapter"
    #: Must be False for every adapter shipped in this repository.
    tx_capable: bool = False

    def __init__(self, sink: Callable[[dict], None]):
        self._sink = sink
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def emit(self, obj: dict) -> None:
        self._sink(obj)

    @abstractmethod
    def run(self) -> None:
        """Blocking receive loop; return when ``self.stopped`` becomes True."""

    def start(self) -> "Adapter":
        self._thread = threading.Thread(target=self.run, name=f"adapter-{self.name}", daemon=True)
        self._thread.start()
        return self

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
