from wsnsim.models import Channel


def test_channel_transmit():
    ch = Channel(loss_rate=0.0)
    assert ch.transmit(object()) is True
