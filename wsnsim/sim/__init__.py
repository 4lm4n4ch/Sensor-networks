"""Discrete-event simulation engine for wsnsim.

Contains event queue, clock and scheduler primitives.
"""

from .event import Event, EventQueue
from .scheduler import Scheduler

__all__ = ["Event", "EventQueue", "Scheduler"]
