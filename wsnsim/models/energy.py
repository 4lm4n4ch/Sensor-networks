"""Energy and lifetime models for WSN nodes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import inf


class EnergyState(Enum):
    """Power states used by the node energy model."""

    TX = "tx"
    RX = "rx"
    IDLE = "idle"
    SLEEP = "sleep"


@dataclass(frozen=True)
class PowerProfile:
    """Power consumption for each node state, in watts."""

    tx_w: float
    rx_w: float
    idle_w: float
    sleep_w: float

    def __post_init__(self) -> None:
        """Validate power values."""
        for name, value_w in (
            ("tx_w", self.tx_w),
            ("rx_w", self.rx_w),
            ("idle_w", self.idle_w),
            ("sleep_w", self.sleep_w),
        ):
            if value_w < 0.0:
                raise ValueError(f"{name} must be non-negative")

    def power_w(self, state: EnergyState) -> float:
        """Return the power draw for one energy state."""
        if state == EnergyState.TX:
            return self.tx_w
        if state == EnergyState.RX:
            return self.rx_w
        if state == EnergyState.IDLE:
            return self.idle_w
        if state == EnergyState.SLEEP:
            return self.sleep_w
        raise ValueError(f"Unsupported energy state: {state!r}")


@dataclass
class Battery:
    """Battery energy bookkeeping, in joules."""

    capacity_j: float
    initial_energy_j: float | None = None
    remaining_energy_j: float | None = None

    def __post_init__(self) -> None:
        """Validate and initialize battery energy fields."""
        if self.capacity_j <= 0.0:
            raise ValueError("capacity_j must be positive")

        if self.initial_energy_j is None:
            self.initial_energy_j = self.capacity_j
        if self.initial_energy_j < 0.0:
            raise ValueError("initial_energy_j must be non-negative")
        if self.initial_energy_j > self.capacity_j:
            raise ValueError("initial_energy_j must not exceed capacity_j")

        if self.remaining_energy_j is None:
            self.remaining_energy_j = self.initial_energy_j
        if self.remaining_energy_j < 0.0:
            raise ValueError("remaining_energy_j must be non-negative")
        if self.remaining_energy_j > self.initial_energy_j:
            raise ValueError("remaining_energy_j must not exceed initial_energy_j")

    @property
    def is_depleted(self) -> bool:
        """Return True when no usable energy remains."""
        return self.remaining_energy_j <= 0.0

    def drain(self, energy_j: float) -> float:
        """Drain energy from the battery and return the actual drained amount."""
        if energy_j < 0.0:
            raise ValueError("energy_j must be non-negative")
        drained_j = min(energy_j, self.remaining_energy_j)
        self.remaining_energy_j -= drained_j
        if self.remaining_energy_j <= 0.0:
            self.remaining_energy_j = 0.0
        return drained_j


@dataclass(frozen=True)
class DutyCycleConfig:
    """Per-cycle state durations for lifetime estimation."""

    tx_time_s: float
    rx_time_s: float
    idle_time_s: float
    sleep_time_s: float
    battery_capacity_j: float | None = None

    def __post_init__(self) -> None:
        """Validate duty-cycle durations and optional battery capacity."""
        durations_s = (
            self.tx_time_s,
            self.rx_time_s,
            self.idle_time_s,
            self.sleep_time_s,
        )
        if any(duration_s < 0.0 for duration_s in durations_s):
            raise ValueError("duty-cycle durations must be non-negative")
        if self.cycle_time_s <= 0.0:
            raise ValueError("cycle time must be positive")
        if self.battery_capacity_j is not None and self.battery_capacity_j <= 0.0:
            raise ValueError("battery_capacity_j must be positive")

    @property
    def cycle_time_s(self) -> float:
        """Return total cycle duration in seconds."""
        return (
            self.tx_time_s
            + self.rx_time_s
            + self.idle_time_s
            + self.sleep_time_s
        )

    @property
    def active_time_ratio(self) -> float:
        """Return fraction of cycle spent outside sleep."""
        active_time_s = self.tx_time_s + self.rx_time_s + self.idle_time_s
        return active_time_s / self.cycle_time_s


@dataclass(frozen=True)
class LifetimeEstimate:
    """Duty-cycle lifetime estimate."""

    average_power_w: float
    lifetime_seconds: float
    lifetime_hours: float
    lifetime_days: float
    active_time_ratio: float
    cycle_time_s: float


@dataclass
class EnergyModel:
    """Integrate node energy consumption over simulated time."""

    power_profile: PowerProfile
    battery: Battery
    current_state: EnergyState = EnergyState.SLEEP
    last_update_time_s: float = 0.0
    consumed_energy_j: float = 0.0

    def __post_init__(self) -> None:
        """Validate initial model state."""
        if self.last_update_time_s < 0.0:
            raise ValueError("last_update_time_s must be non-negative")
        if self.consumed_energy_j < 0.0:
            raise ValueError("consumed_energy_j must be non-negative")

    @property
    def remaining_energy_j(self) -> float:
        """Return remaining battery energy in joules."""
        return self.battery.remaining_energy_j

    @property
    def is_depleted(self) -> bool:
        """Return True when the battery has reached zero joules."""
        return self.battery.is_depleted

    def transition_to(self, new_state: EnergyState, time_s: float) -> None:
        """Integrate current-state energy then switch to a new state."""
        self.update(time_s)
        self.current_state = new_state

    def update(self, time_s: float) -> None:
        """Integrate energy consumption from the last update to ``time_s``."""
        if time_s < self.last_update_time_s:
            raise ValueError("time_s must be monotonically non-decreasing")

        duration_s = time_s - self.last_update_time_s
        if duration_s > 0.0:
            self.consume(duration_s, self.current_state)
        self.last_update_time_s = time_s

    def consume(self, duration_s: float, state: EnergyState) -> float:
        """Consume energy for ``duration_s`` in ``state``.

        Returns the actual consumed energy in joules. If the battery depletes
        during the interval, the returned value is clamped to the available
        remaining energy.
        """
        if duration_s < 0.0:
            raise ValueError("duration_s must be non-negative")

        requested_energy_j = self.power_profile.power_w(state) * duration_s
        drained_j = self.battery.drain(requested_energy_j)
        self.consumed_energy_j += drained_j
        return drained_j

    def estimate_lifetime_seconds(
        self,
        duty_cycle_config: DutyCycleConfig,
    ) -> float:
        """Estimate lifetime in seconds from a duty-cycle configuration."""
        return self.estimate_lifetime(duty_cycle_config).lifetime_seconds

    def estimate_lifetime(
        self,
        duty_cycle_config: DutyCycleConfig,
    ) -> LifetimeEstimate:
        """Estimate average power and lifetime for a duty-cycle configuration."""
        average_power_w = average_power_for_duty_cycle(
            self.power_profile,
            duty_cycle_config,
        )
        capacity_j = (
            duty_cycle_config.battery_capacity_j
            if duty_cycle_config.battery_capacity_j is not None
            else self.battery.capacity_j
        )

        lifetime_seconds = (
            inf if average_power_w == 0.0 else capacity_j / average_power_w
        )
        return LifetimeEstimate(
            average_power_w=average_power_w,
            lifetime_seconds=lifetime_seconds,
            lifetime_hours=lifetime_seconds / 3600.0,
            lifetime_days=lifetime_seconds / 86400.0,
            active_time_ratio=duty_cycle_config.active_time_ratio,
            cycle_time_s=duty_cycle_config.cycle_time_s,
        )


def average_power_for_duty_cycle(
    power_profile: PowerProfile,
    duty_cycle_config: DutyCycleConfig,
) -> float:
    """Return average power in watts for one duty cycle."""
    energy_per_cycle_j = (
        power_profile.tx_w * duty_cycle_config.tx_time_s
        + power_profile.rx_w * duty_cycle_config.rx_time_s
        + power_profile.idle_w * duty_cycle_config.idle_time_s
        + power_profile.sleep_w * duty_cycle_config.sleep_time_s
    )
    return energy_per_cycle_j / duty_cycle_config.cycle_time_s
