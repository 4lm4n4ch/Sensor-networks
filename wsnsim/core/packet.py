"""Packet representation shared by simulator modules."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Packet:
    """Neutral packet metadata for WSN simulations."""

    src: int
    dst: int
    size_bytes: int
    created_at: float = 0.0
