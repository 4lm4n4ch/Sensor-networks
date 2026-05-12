"""Simple channel model placeholder."""

from wsnsim.utils.rng import RNG


class Channel:
    """A simple channel model with a packet loss rate."""

    def __init__(self, loss_rate: float = 0.0, rng: RNG | None = None):
        if not 0.0 <= loss_rate <= 1.0:
            raise ValueError("Loss rate must be between 0.0 and 1.0")
        self.loss_rate = loss_rate
        self.rng = rng if rng is not None else RNG()

    def transmit(self, packet: Any) -> bool:
        """Simulate transmitting a packet.

        Args:
            packet: The packet to transmit (can be any object).

        Returns:
            True if the packet is delivered successfully, False otherwise.
        """
        return self.rng.rand() >= self.loss_rate
