"""Simple channel model placeholder."""

class Channel:
    def __init__(self, loss_rate: float = 0.0):
        self.loss_rate = loss_rate

    def transmit(self, packet):
        """Simulate transmitting a packet. Return True if delivered."""
        # Placeholder: real model would use RNG and propagation delays
        return True
