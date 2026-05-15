"""Tests for Week 8 clock drift and RSSI localization."""

import pytest

from wsnsim.models.sync_localization import (
    AnchorNode,
    ClockConfig,
    LocalizationError,
    NodeClock,
    RSSILocalizationConfig,
    UnknownNode,
    distance_between_points,
    distance_from_rssi,
    generate_rssi_measurements,
    localize_from_measurements,
    rssi_from_distance,
    trilaterate_2d,
)


def test_zero_drift_and_zero_offset_gives_exact_true_time():
    clock = NodeClock(ClockConfig(node_id=1))

    assert clock.local_time(123.45) == pytest.approx(123.45)
    assert clock.drift_error_s(123.45) == pytest.approx(0.0)


def test_positive_drift_increases_local_time():
    clock = NodeClock(ClockConfig(node_id=1, drift_ppm=50.0))

    assert clock.local_time(1000.0) > 1000.0


def test_negative_drift_decreases_local_time():
    clock = NodeClock(ClockConfig(node_id=1, drift_ppm=-50.0))

    assert clock.local_time(1000.0) < 1000.0


def test_ppm_conversion_sanity_check():
    clock = NodeClock(ClockConfig(node_id=1, drift_ppm=100.0))

    assert clock.drift_error_s(1000.0) == pytest.approx(0.1)


def test_offset_is_applied_correctly():
    clock = NodeClock(ClockConfig(node_id=1, drift_ppm=0.0, offset_s=2.5))

    assert clock.local_time(10.0) == pytest.approx(12.5)
    assert clock.drift_error_s(10.0) == pytest.approx(2.5)


def test_inverse_conversion_from_local_time_to_true_time():
    clock = NodeClock(ClockConfig(node_id=1, drift_ppm=75.0, offset_s=-0.25))
    true_time_s = 4321.0

    local_time_s = clock.local_time(true_time_s)

    assert clock.true_time(local_time_s) == pytest.approx(true_time_s)


def test_simple_offset_synchronization_reduces_instantaneous_error():
    clock = NodeClock(ClockConfig(node_id=1, drift_ppm=100.0, offset_s=0.5))

    result = clock.synchronize_offset(1000.0)

    assert result.error_before_s == pytest.approx(0.6)
    assert result.error_after_s == pytest.approx(0.0)
    assert clock.corrected_local_time(1000.0) == pytest.approx(1000.0)


def test_distance_between_known_coordinates_uses_3_4_5_triangle():
    assert distance_between_points(0.0, 0.0, 3.0, 4.0) == pytest.approx(5.0)


def test_rssi_to_distance_inverse_is_correct_without_noise():
    config = RSSILocalizationConfig(
        tx_power_dbm=0.0,
        d0_m=1.0,
        path_loss_d0_db=40.0,
        path_loss_exponent=2.0,
        sigma_db=0.0,
    )

    rssi_dbm = rssi_from_distance(25.0, config)

    assert distance_from_rssi(rssi_dbm, config) == pytest.approx(25.0)


def test_trilateration_with_three_anchors_recovers_known_point():
    anchors = [
        AnchorNode(0, 0.0, 0.0),
        AnchorNode(1, 10.0, 0.0),
        AnchorNode(2, 0.0, 10.0),
    ]
    x_m, y_m = 3.0, 4.0
    distances = [
        distance_between_points(anchor.x_m, anchor.y_m, x_m, y_m)
        for anchor in anchors
    ]

    estimate = trilaterate_2d(anchors, distances)

    assert estimate[0] == pytest.approx(x_m)
    assert estimate[1] == pytest.approx(y_m)


def test_trilateration_with_four_anchors_uses_least_squares():
    anchors = [
        AnchorNode(0, 0.0, 0.0),
        AnchorNode(1, 10.0, 0.0),
        AnchorNode(2, 0.0, 10.0),
        AnchorNode(3, 10.0, 10.0),
    ]
    x_m, y_m = 6.0, 2.5
    distances = [
        distance_between_points(anchor.x_m, anchor.y_m, x_m, y_m)
        for anchor in anchors
    ]

    estimate = trilaterate_2d(anchors, distances)

    assert estimate[0] == pytest.approx(x_m)
    assert estimate[1] == pytest.approx(y_m)


def test_fewer_than_three_anchors_raises_clear_error():
    anchors = [
        AnchorNode(0, 0.0, 0.0),
        AnchorNode(1, 10.0, 0.0),
    ]

    with pytest.raises(LocalizationError, match="at least 3 anchors"):
        trilaterate_2d(anchors, [5.0, 5.0])


def test_collinear_anchor_geometry_is_handled():
    anchors = [
        AnchorNode(0, 0.0, 0.0),
        AnchorNode(1, 10.0, 0.0),
        AnchorNode(2, 20.0, 0.0),
    ]

    with pytest.raises(LocalizationError, match="rank-deficient|collinear"):
        trilaterate_2d(anchors, [5.0, 5.0, 15.0])


def test_localization_error_is_near_zero_in_noiseless_case():
    anchors = [
        AnchorNode(0, 0.0, 0.0),
        AnchorNode(1, 100.0, 0.0),
        AnchorNode(2, 0.0, 100.0),
        AnchorNode(3, 100.0, 100.0),
    ]
    unknown = UnknownNode(10, 30.0, 40.0)
    config = RSSILocalizationConfig(
        path_loss_exponent=2.0,
        sigma_db=0.0,
        seed=2026,
    )
    measurements = generate_rssi_measurements(anchors, unknown, config)

    result = localize_from_measurements(anchors, unknown, measurements)

    assert result.success
    assert result.estimated_x_m == pytest.approx(unknown.true_x_m)
    assert result.estimated_y_m == pytest.approx(unknown.true_y_m)
    assert result.error_m == pytest.approx(0.0, abs=1e-9)


def test_rssi_measurement_noise_is_deterministic_with_fixed_seed():
    anchors = [
        AnchorNode(0, 0.0, 0.0),
        AnchorNode(1, 100.0, 0.0),
        AnchorNode(2, 0.0, 100.0),
    ]
    unknown = UnknownNode(10, 30.0, 40.0)
    config = RSSILocalizationConfig(sigma_db=4.0, seed=99)

    first = generate_rssi_measurements(anchors, unknown, config)
    second = generate_rssi_measurements(anchors, unknown, config)

    assert [m.rssi_dbm for m in first] == pytest.approx(
        [m.rssi_dbm for m in second]
    )
    assert [m.estimated_distance_m for m in first] == pytest.approx(
        [m.estimated_distance_m for m in second]
    )
