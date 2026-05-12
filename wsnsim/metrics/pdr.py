"""Packet delivery ratio metric."""

def compute_pdr(sent: int, received: int) -> float:
    if sent <= 0:
        return 0.0
    return float(received) / float(sent)
