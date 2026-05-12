"""Energy-related metrics."""

def energy_per_bit(energy_joule: float, bits: int) -> float:
    """Calculate energy consumption per bit.

    Args:
        energy_joule: Total energy consumed in Joules.
        bits: Total number of bits transmitted/received.

    Returns:
        Energy per bit in Joules/bit. Returns infinity if bits is zero or negative.
    """
    if bits <= 0:
        return float('inf')
    return energy_joule / bits
