from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass(slots=True)
class TimerStats:
    count: int = 0
    total_ms: float = 0.0
    min_ms: float | None = None
    max_ms: float | None = None

    def observe(self, duration_ms: float) -> None:
        self.count += 1
        self.total_ms += duration_ms
        self.min_ms = duration_ms if self.min_ms is None else min(self.min_ms, duration_ms)
        self.max_ms = duration_ms if self.max_ms is None else max(self.max_ms, duration_ms)

    def as_dict(self) -> dict[str, float | int | None]:
        average_ms = self.total_ms / self.count if self.count else 0.0
        return {
            "count": self.count,
            "total_ms": round(self.total_ms, 3),
            "avg_ms": round(average_ms, 3),
            "min_ms": None if self.min_ms is None else round(self.min_ms, 3),
            "max_ms": None if self.max_ms is None else round(self.max_ms, 3),
        }


@dataclass
class MetricsRegistry:
    counters: dict[str, int] = field(default_factory=dict)
    timers: dict[str, TimerStats] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def increment(
        self,
        name: str,
        labels: dict[str, Any] | None = None,
        amount: int = 1,
    ) -> None:
        key = self._key(name, labels)
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + amount

    def observe(
        self,
        name: str,
        duration_ms: float,
        labels: dict[str, Any] | None = None,
    ) -> None:
        key = self._key(name, labels)
        with self._lock:
            self.timers.setdefault(key, TimerStats()).observe(duration_ms)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(sorted(self.counters.items())),
                "timers": {
                    key: value.as_dict()
                    for key, value in sorted(self.timers.items())
                },
            }

    def _key(self, name: str, labels: dict[str, Any] | None) -> str:
        if not labels:
            return name
        serialized = ",".join(
            f"{key}={labels[key]}"
            for key in sorted(labels)
        )
        return f"{name}{{{serialized}}}"


metrics_registry = MetricsRegistry()
