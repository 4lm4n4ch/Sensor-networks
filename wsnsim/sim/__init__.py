"""Discrete-event simulation engine for wsnsim.

Contains event queue, clock and scheduler primitives.
"""

from .sim import ScheduledEvent, Scheduler, SimClock

__all__ = [
    "ScheduledEvent",
    "Scheduler",
    "SimClock",
]
