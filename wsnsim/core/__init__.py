"""Core dataclasses shared across simulator modules."""

from .link import LinkStats
from .packet import Packet

__all__ = ["LinkStats", "Packet"]
