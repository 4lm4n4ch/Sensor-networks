import pytest

from wsnsim.models import Channel
from wsnsim.utils.rng import RNG


def test_channel_transmit_no_loss():
    # Test with no loss, all packets should be transmitted
    ch = Channel(loss_rate=0.0)
    for _ in range(10):
        assert ch.transmit(object()) is True


def test_channel_transmit_full_loss():
    # Test with full loss, no packets should be transmitted
    ch = Channel(loss_rate=1.0)
    for _ in range(10):
        assert ch.transmit(object()) is False


def test_channel_transmit_with_loss_rate_reproducibility():
    # Test with a specific loss rate and seed for reproducibility
    rng = RNG(seed=42)
    ch1 = Channel(loss_rate=0.5, rng=rng)
    
    rng = RNG(seed=42)
    ch2 = Channel(loss_rate=0.5, rng=rng)

    results1 = [ch1.transmit(object()) for _ in range(20)]
    results2 = [ch2.transmit(object()) for _ in range(20)]

    assert results1 == results2
    # Expect some True and some False due to 0.5 loss rate and deterministic RNG
    assert True in results1
    assert False in results1


def test_channel_invalid_loss_rate():
    # Test that an invalid loss rate raises a ValueError
    with pytest.raises(ValueError, match="Loss rate must be between 0.0 and 1.0"):
        Channel(loss_rate=1.1)
    with pytest.raises(ValueError, match="Loss rate must be between 0.0 and 1.0"):
        Channel(loss_rate=-0.1)
