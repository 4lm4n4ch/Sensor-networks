"""Core discrete-event simulation primitives.

This module provides a minimal deterministic scheduler built on ``heapq``,
along with a floating-point simulation clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from itertools import count
from typing import Any, Callable

import numpy as np

from wsnsim.utils.logger import TraceLogger


@dataclass(order=True)
class ScheduledEvent:
    """A scheduled callback in simulation time.

    Ordering fields ensure deterministic popping from the heap in this order:
    ``time`` -> ``priority`` -> ``sequence``.
    """

    time: float
    priority: int
    sequence: int
    callback: Callable[[Any], None] = field(compare=False)
    payload: Any = field(default=None, compare=False)


class SimClock:
    """Mutable simulation clock with floating-point time."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    @property
    def now(self) -> float:
        """Return current simulation time."""
        return self._now

    def advance_to(self, timestamp: float) -> None:
        """Advance simulation time to ``timestamp``.

        Raises:
            ValueError: If ``timestamp`` is earlier than current time.
        """

        next_time = float(timestamp)
        if next_time < self._now:
            raise ValueError("Simulation clock cannot go backwards.")
        self._now = next_time

    def reset(self, start: float = 0.0) -> None:
        """Reset clock time."""
        self._now = float(start)


class Scheduler:
    """Minimal deterministic discrete-event scheduler.

    Args:
        seed: Optional seed for deterministic random number generation.
        trace: Optional trace logger for debug/validation visibility.
    """

    def __init__(self, seed: int | None = None, trace: TraceLogger | None = None) -> None:
        self.clock = SimClock()
        self.rng = np.random.default_rng(seed)
        self._queue: list[ScheduledEvent] = []
        self._sequence = count()
        self._running = False
        self.trace = trace if trace is not None else TraceLogger(enabled=False)

    def schedule(
        self,
        time: float,
        callback: Callable[[Any], None],
        priority: int = 0,
        payload: Any = None,
    ) -> ScheduledEvent:
        """Schedule a new event at absolute simulation ``time``.

        Lower numeric ``priority`` executes earlier for identical timestamps.
        """

        event_time = float(time)
        if event_time < self.clock.now:
            raise ValueError("Cannot schedule events in the past.")

        event = ScheduledEvent(
            time=event_time,
            priority=priority,
            sequence=next(self._sequence),
            callback=callback,
            payload=payload,
        )
        heapq.heappush(self._queue, event)
        self.trace.log(
            sim_time=self.clock.now,
            message="event_scheduled",
            event_time=event.time,
            priority=event.priority,
            sequence=event.sequence,
        )
        return event

    def run(self, until: float | None = None) -> int:
        """Run queued events in chronological order.

        Args:
            until: Optional time bound; events strictly after it are not executed.

        Returns:
            Number of executed events.
        """

        executed = 0
        self._running = True

        while self._queue and self._running:
            next_event = self._queue[0]
            if until is not None and next_event.time > float(until):
                break

            event = heapq.heappop(self._queue)
            self.clock.advance_to(event.time)
            self.trace.log(
                sim_time=self.clock.now,
                message="event_executed",
                event_time=event.time,
                priority=event.priority,
                sequence=event.sequence,
            )
            event.callback(event.payload)
            executed += 1

        return executed

    def stop(self) -> None:
        """Stop event processing on next loop iteration."""
        self._running = False

    @property
    def queued_events(self) -> int:
        """Return number of pending events."""
        return len(self._queue)
