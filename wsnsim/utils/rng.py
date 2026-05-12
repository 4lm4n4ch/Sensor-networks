"""Random number generator helpers."""

import random


class RNG:
    def __init__(self, seed=None):
        self._r = random.Random(seed)

    def rand(self):
        return self._r.random()

    def choice(self, seq):
        return self._r.choice(seq)
