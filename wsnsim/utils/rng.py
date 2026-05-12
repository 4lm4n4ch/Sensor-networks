"""Random number generator helpers using NumPy."""

import numpy as np


class RNG:
    """Wrapper for NumPy's default_rng to ensure consistent seeding."""

    def __init__(self, seed: int | None = None):
        self._rng = np.random.default_rng(seed)

    def rand(self) -> float:
        """Return a random float in [0.0, 1.0)."""
        return self._rng.random()

    def choice(self, seq: list | np.ndarray) -> any:
        """Return a random element from a non-empty sequence."""
        return self._rng.choice(seq)

    def uniform(self, low: float, high: float) -> float:
        """Return a random float N such that low <= N <= high."""
        return self._rng.uniform(low, high)
