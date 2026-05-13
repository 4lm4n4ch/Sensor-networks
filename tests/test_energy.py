"""Tests for Week 3 energy and lifetime models."""

import pytest

from wsnsim.models.energy import (
    Battery,
    DutyCycleConfig,
    EnergyModel,
    EnergyState,
    PowerProfile,
)


def make_energy_model(
    *,
    capacity_j: float = 100.0,
    tx_w: float = 0.06,
    rx_w: float = 0.045,
    idle_w: float = 0.01,
    sleep_w: float = 0.0001,
) -> EnergyModel:
    """Create a small deterministic energy model for tests."""
    return EnergyModel(
        power_profile=PowerProfile(
            tx_w=tx_w,
            rx_w=rx_w,
            idle_w=idle_w,
            sleep_w=sleep_w,
        ),
        battery=Battery(capacity_j=capacity_j),
        current_state=EnergyState.SLEEP,
    )


def test_manual_one_watt_for_ten_seconds_consumes_ten_joules():
    model = make_energy_model(
        capacity_j=100.0,
        tx_w=1.0,
        rx_w=1.0,
        idle_w=1.0,
        sleep_w=1.0,
    )

    consumed_j = model.consume(10.0, EnergyState.TX)

    assert consumed_j == pytest.approx(10.0)
    assert model.consumed_energy_j == pytest.approx(10.0)
    assert model.remaining_energy_j == pytest.approx(90.0)


def test_consumed_energy_increases_monotonically():
    model = make_energy_model(tx_w=1.0)

    model.consume(1.0, EnergyState.TX)
    first_j = model.consumed_energy_j
    model.consume(2.0, EnergyState.TX)
    second_j = model.consumed_energy_j

    assert first_j > 0.0
    assert second_j >= first_j


def test_remaining_energy_decreases_monotonically():
    model = make_energy_model(tx_w=1.0)

    initial_j = model.remaining_energy_j
    model.consume(1.0, EnergyState.TX)
    after_first_j = model.remaining_energy_j
    model.consume(2.0, EnergyState.TX)
    after_second_j = model.remaining_energy_j

    assert after_first_j <= initial_j
    assert after_second_j <= after_first_j


def test_remaining_energy_never_becomes_negative():
    model = make_energy_model(capacity_j=5.0, tx_w=2.0)

    consumed_j = model.consume(10.0, EnergyState.TX)

    assert consumed_j == pytest.approx(5.0)
    assert model.remaining_energy_j == pytest.approx(0.0)
    assert model.consumed_energy_j == pytest.approx(5.0)
    assert model.is_depleted is True


def test_battery_validation():
    """Verify that Battery rejects invalid capacities and energies."""
    with pytest.raises(ValueError, match="capacity_j must be positive"):
        Battery(capacity_j=0.0)
    with pytest.raises(ValueError, match="initial_energy_j must be non-negative"):
        Battery(capacity_j=10.0, initial_energy_j=-1.0)
    with pytest.raises(
        ValueError,
        match="initial_energy_j must not exceed capacity_j",
    ):
        Battery(capacity_j=10.0, initial_energy_j=11.0)
    with pytest.raises(ValueError, match="remaining_energy_j must be non-negative"):
        Battery(capacity_j=10.0, remaining_energy_j=-1.0)
    with pytest.raises(
        ValueError,
        match="remaining_energy_j must not exceed initial_energy_j",
    ):
        Battery(
            capacity_j=10.0,
            initial_energy_j=5.0,
            remaining_energy_j=6.0,
        )


def test_power_profile_validation():
    """Verify that PowerProfile rejects negative power values."""
    with pytest.raises(ValueError, match="tx_w must be non-negative"):
        PowerProfile(tx_w=-0.1, rx_w=0.0, idle_w=0.0, sleep_w=0.0)
    with pytest.raises(ValueError, match="rx_w must be non-negative"):
        PowerProfile(tx_w=0.0, rx_w=-0.1, idle_w=0.0, sleep_w=0.0)
    with pytest.raises(ValueError, match="idle_w must be non-negative"):
        PowerProfile(tx_w=0.0, rx_w=0.0, idle_w=-0.1, sleep_w=0.0)
    with pytest.raises(ValueError, match="sleep_w must be non-negative"):
        PowerProfile(tx_w=0.0, rx_w=0.0, idle_w=0.0, sleep_w=-0.1)


def test_no_consumption_after_depletion():
    """Verify that a depleted battery stays at zero and returns 0 energy."""
    battery = Battery(capacity_j=1.0)

    drained_1_j = battery.drain(2.0)
    drained_2_j = battery.drain(1.0)

    assert drained_1_j == pytest.approx(1.0)
    assert drained_2_j == pytest.approx(0.0)
    assert battery.remaining_energy_j == pytest.approx(0.0)
    assert battery.is_depleted is True


def test_negative_duration_raises_value_error():
    model = make_energy_model()

    with pytest.raises(ValueError, match="duration_s must be non-negative"):
        model.consume(-1.0, EnergyState.TX)


def test_negative_time_step_raises_value_error():
    model = make_energy_model()

    model.update(5.0)

    with pytest.raises(ValueError, match="time_s must be monotonically"):
        model.update(4.0)


def test_transition_integrates_previous_state_before_switching():
    model = make_energy_model(capacity_j=100.0, tx_w=1.0, rx_w=0.5)
    model.transition_to(EnergyState.TX, 0.0)
    model.transition_to(EnergyState.RX, 10.0)

    assert model.consumed_energy_j == pytest.approx(10.0)
    assert model.remaining_energy_j == pytest.approx(90.0)
    assert model.current_state == EnergyState.RX
    assert model.last_update_time_s == pytest.approx(10.0)


def test_higher_active_duty_cycle_reduces_lifetime():
    model = make_energy_model(
        capacity_j=1000.0,
        tx_w=1.0,
        rx_w=0.5,
        idle_w=0.1,
        sleep_w=0.001,
    )
    low_active = DutyCycleConfig(
        tx_time_s=0.1,
        rx_time_s=0.1,
        idle_time_s=0.0,
        sleep_time_s=9.8,
    )
    high_active = DutyCycleConfig(
        tx_time_s=2.0,
        rx_time_s=2.0,
        idle_time_s=0.0,
        sleep_time_s=6.0,
    )

    low_estimate = model.estimate_lifetime(low_active)
    high_estimate = model.estimate_lifetime(high_active)

    assert high_estimate.active_time_ratio > low_estimate.active_time_ratio
    assert high_estimate.average_power_w > low_estimate.average_power_w
    assert high_estimate.lifetime_seconds < low_estimate.lifetime_seconds
