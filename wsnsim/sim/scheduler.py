"""Simple scheduler driving the event queue and clock."""

from typing import Optional
from .event import Event, EventQueue


class Scheduler:
    def __init__(self):
        self.time = 0.0
        self.queue = EventQueue()
        self.running = False

    def schedule(self, delay: float, action, *args, priority: int = 0, **kwargs):
        ev = Event(time=self.time + delay, priority=priority, action=action, args=args, kwargs=kwargs)
        self.queue.push(ev)

    def run(self, until: Optional[float] = None):
        self.running = True
        while not self.queue.empty() and self.running:
            event = self.queue.pop()
            if until is not None and event.time > until:
                break
            self.time = event.time
            event.action(*event.args, **event.kwargs)

    def stop(self):
        self.running = False
