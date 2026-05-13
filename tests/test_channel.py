"""Tests for Week 2 radio channel models."""

import math

import pytest

from wsnsim.models.channel import ChannelConfig, LogDistanceChannel


def make_channel(*, seed: int | None = 42) -> LogDistanceChannel:
    """Create a deterministic channel for tests."""
    config = ChannelConfig(shadowing_sigma_db=4.0, seed=seed)
    return LogDistanceChannel(config)


def test_path_loss_increases_with_distance_fixed_shadowing():
    channel = make_channel()

    near = channel.calculate_link_stats(
        5.0,
        32,
        shadowing_db=0.0,
    )
    far = channel.calculate_link_stats(
        50.0,
        32,
        shadowing_db=0.0,
    )

    assert far.path_loss_db > near.path_loss_db


def test_rssi_decreases_with_distance_fixed_shadowing():
    channel = make_channel()

    near = channel.calculate_link_stats(
        5.0,
        32,
        shadowing_db=0.0,
    )
    far = channel.calculate_link_stats(
        50.0,
        32,
        shadowing_db=0.0,
    )

    assert far.rssi_dbm < near.rssi_dbm


def test_snr_decreases_with_distance_fixed_shadowing():
    channel = make_channel()

    near = channel.calculate_link_stats(
        5.0,
        32,
        shadowing_db=0.0,
    )
    far = channel.calculate_link_stats(
        50.0,
        32,
        shadowing_db=0.0,
    )

    assert far.snr_db < near.snr_db


def test_prr_values_are_probabilities():
    channel = make_channel()

    for distance_m in [1.0, 10.0, 50.0, 100.0, 150.0]:
        stats = channel.calculate_link_stats(
            distance_m,
            64,
            shadowing_db=0.0,
        )

        assert 0.0 <= stats.prr_logistic <= 1.0
        assert 0.0 <= stats.prr_ber <= 1.0
        assert 0.0 <= stats.per <= 1.0
        assert 0.0 <= stats.ber <= 1.0


def test_same_seed_reproduces_shadowing_and_link_statistics():
    channel_a = make_channel(seed=123)
    channel_b = make_channel(seed=123)

    stats_a = channel_a.calculate_link_stats(25.0, 64)
    stats_b = channel_b.calculate_link_stats(25.0, 64)

    assert stats_a == stats_b


def test_negative_distance_raises_value_error():
    channel = make_channel()

    with pytest.raises(ValueError, match="distance_m must not be negative"):
        channel.calculate_link_stats(-1.0, 32)


def test_invalid_d0_m_raises_value_error():
    with pytest.raises(ValueError, match="d0_m must be positive"):
        ChannelConfig(d0_m=0.0)


def test_invalid_path_loss_exponent_raises_value_error():
    with pytest.raises(ValueError, match="path_loss_exponent must be positive"):
        ChannelConfig(path_loss_exponent=0.0)


def test_invalid_shadowing_sigma_raises_value_error():
    with pytest.raises(
        ValueError,
        match="shadowing_sigma_db must be non-negative",
    ):
        ChannelConfig(shadowing_sigma_db=-0.1)


def test_invalid_transition_width_raises_value_error():
    with pytest.raises(ValueError, match="transition_width_db must be positive"):
        ChannelConfig(transition_width_db=0.0)


def test_distance_below_d0_uses_reference_distance():
    config = ChannelConfig(d0_m=5.0, shadowing_sigma_db=0.0)
    channel = LogDistanceChannel(config)

    below_d0 = channel.calculate_link_stats(
        2.0,
        32,
        shadowing_db=0.0,
    )
    at_d0 = channel.calculate_link_stats(
        5.0,
        32,
        shadowing_db=0.0,
    )

    assert below_d0.effective_distance_m == 5.0
    assert below_d0.path_loss_db == pytest.approx(at_d0.path_loss_db)
    assert below_d0.rssi_dbm == pytest.approx(at_d0.rssi_dbm)
    assert below_d0.snr_db == pytest.approx(at_d0.snr_db)


def test_ber_mode_larger_packet_has_lower_or_equal_prr():
    channel = make_channel()

    small = channel.calculate_link_stats(
        60.0,
        16,
        shadowing_db=0.0,
        include_success=True,
        prr_mode="ber",
    )
    large = channel.calculate_link_stats(
        60.0,
        128,
        shadowing_db=0.0,
        include_success=True,
        prr_mode="ber",
    )

    assert large.prr_ber <= small.prr_ber


def test_calculate_link_stats_uses_one_pinned_shadowing_value():
    config = ChannelConfig(
        tx_power_dbm=2.0,
        d0_m=1.0,
        path_loss_d0_db=40.0,
        path_loss_exponent=2.7,
        noise_floor_dbm=-100.0,
        seed=42,
    )
    channel = LogDistanceChannel(config)
    stats = channel.calculate_link_stats(
        20.0,
        32,
        shadowing_db=3.5,
    )

    expected_path_loss_db = (
        config.path_loss_d0_db
        + 10.0 * config.path_loss_exponent * math.log10(
            stats.effective_distance_m / config.d0_m
        )
        + stats.shadowing_db
    )
    expected_rssi_dbm = config.tx_power_dbm - expected_path_loss_db
    expected_snr_db = expected_rssi_dbm - config.noise_floor_dbm
    expected_snr_linear = 10.0 ** (expected_snr_db / 10.0)

    assert stats.shadowing_db == 3.5
    assert stats.path_loss_db == pytest.approx(expected_path_loss_db)
    assert stats.rssi_dbm == pytest.approx(expected_rssi_dbm)
    assert stats.snr_db == pytest.approx(expected_snr_db)
    assert stats.snr_linear == pytest.approx(expected_snr_linear)


def test_manual_validation_two_points_fixed_shadowing():
    config = ChannelConfig(
        tx_power_dbm=0.0,
        d0_m=1.0,
        path_loss_d0_db=40.0,
        path_loss_exponent=2.7,
        shadowing_sigma_db=0.0,
        noise_floor_dbm=-100.0,
        snr_threshold_db=10.0,
        transition_width_db=2.0,
        seed=42,
    )
    channel = LogDistanceChannel(config)

    manual_points = [
        {
            "distance_m": 10.0,
            "path_loss_db": 67.0,
            "rssi_dbm": -67.0,
            "snr_db": 33.0,
            "prr_logistic": 0.9999898700090192,
        },
        {
            "distance_m": 50.0,
            "path_loss_db": 85.8721901170725,
            "rssi_dbm": -85.8721901170725,
            "snr_db": 14.127809882927494,
            "prr_logistic": 0.887345113400099,
        },
    ]

    for point in manual_points:
        stats = channel.calculate_link_stats(
            point["distance_m"],
            64,
            shadowing_db=0.0,
        )

        assert stats.path_loss_db == pytest.approx(point["path_loss_db"])
        assert stats.rssi_dbm == pytest.approx(point["rssi_dbm"])
        assert stats.snr_db == pytest.approx(point["snr_db"])
        assert stats.prr_logistic == pytest.approx(point["prr_logistic"])
