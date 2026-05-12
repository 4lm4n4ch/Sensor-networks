"""Energy-related metrics."""

def energy_per_bit(energy_joule, bits):
    if bits <= 0:
        return float('inf')
    return energy_joule / bits
