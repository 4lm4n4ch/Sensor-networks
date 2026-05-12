"""Event and EventQueue primitives."""

from dataclasses import dataclass, field
import heapq
from typing import Any, Callable, List, Tuple


@dataclass(order=True)
class Event:
    time: float
    priority: int
    action: Callable = field(compare=False)
    args: tuple = field(default=(), compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)


class EventQueue:
    def __init__(self):
        self._queue: List[Tuple[float, int, Event]] = []
        self._counter = 0

    def push(self, event: Event):
        heapq.heappush(self._queue, (event.time, self._counter, event))
        self._counter += 1

    def pop(self) -> Event:
        _, _, event = heapq.heappop(self._queue)
        return event

    def peek(self) -> Event:
        return self._queue[0][2]

    def empty(self) -> bool:
        return len(self._queue) == 0
