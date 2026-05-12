"""Energy model placeholder."""

class EnergyModel:
    def __init__(self, initial_joule: float = 100.0):
        self.energy = initial_joule

    def consume(self, amount: float):
        self.energy = max(0.0, self.energy - amount)
