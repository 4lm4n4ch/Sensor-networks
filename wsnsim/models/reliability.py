"""Link-level ACK/retry reliability model for Week 7.

The model is intentionally scoped to one hop. It schedules data attempts,
optional ACK arrivals, ACK timeouts, and deterministic seeded backoff events.
It is not an end-to-end transport protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal, Protocol

import numpy as np

from wsnsim.sim import Scheduler


FrameType = Literal["data", "ack"]


SEND_PRIORITY = 0
ACK_ARRIVAL_PRIORITY = -1
TIMEOUT_PRIORITY = 1
RETRY_PRIORITY = 2


class AttemptStatus(Enum):
    """Lifecycle state for one ARQ transmission attempt."""

    PENDING = "pending"
    DATA_LOST = "data_lost"
    ACK_LOST = "ack_lost"
    ACKED = "acked"
    TIMED_OUT = "timed_out"
    SUPERSEDED = "superseded"


class ReliabilityEventType(Enum):
    """Traceable reliability-layer events."""

    DATA_SEND = "data_send"
    DATA_DELIVERED = "data_delivered"
    DATA_LOST = "data_lost"
    ACK_SEND = "ack_send"
    ACK_RECEIVED = "ack_received"
    ACK_LOST = "ack_lost"
    TIMEOUT = "timeout"
    BACKOFF = "backoff"
    PACKET_DELIVERED = "packet_delivered"
    PACKET_DROPPED = "packet_dropped"


@dataclass(frozen=True)
class ReliabilityConfig:
    """Configuration for link-level ACK/retry ARQ."""

    ack_enabled: bool = True
    retry_limit: int = 3
    ack_timeout_s: float = 0.02
    base_backoff_s: float = 0.005
    max_backoff_s: float = 0.1
    backoff_multiplier: float = 2.0
    seed: int | None = 42
    ack_size_bytes: int = 8
    bitrate_bps: float = 250_000.0
    processing_delay_s: float = 0.001
    propagation_delay_s: float = 0.001
    tx_energy_per_bit_j: float = 50e-9
    rx_energy_per_bit_j: float = 50e-9
    channel_prr_mode: str = "logistic"
    include_shadowing: bool = False

    @property
    def ack_payload_bytes(self) -> int:
        """Compatibility alias for ACK payload size."""
        return self.ack_size_bytes

    def __post_init__(self) -> None:
        """Validate timing, retry, energy, and size parameters."""
        if self.retry_limit < 0:
            raise ValueError("retry_limit must be non-negative")
        if self.ack_timeout_s <= 0.0:
            raise ValueError("ack_timeout_s must be positive")
        if self.base_backoff_s < 0.0:
            raise ValueError("base_backoff_s must be non-negative")
        if self.max_backoff_s < self.base_backoff_s:
            raise ValueError("max_backoff_s must be >= base_backoff_s")
        if self.backoff_multiplier < 1.0:
            raise ValueError("backoff_multiplier must be >= 1.0")
        if self.ack_size_bytes <= 0:
            raise ValueError("ack_size_bytes must be positive")
        if self.bitrate_bps <= 0.0:
            raise ValueError("bitrate_bps must be positive")
        if self.processing_delay_s < 0.0 or self.propagation_delay_s < 0.0:
            raise ValueError("processing/propagation delays must be non-negative")
        if self.tx_energy_per_bit_j < 0.0 or self.rx_energy_per_bit_j < 0.0:
            raise ValueError("energy costs must be non-negative")
        if self.channel_prr_mode not in ("logistic", "ber"):
            raise ValueError("channel_prr_mode must be 'logistic' or 'ber'")


@dataclass
class TransmissionAttempt:
    """One data attempt and the ACK window associated with it."""

    packet_id: int | str
    source_id: int
    destination_id: int
    attempt_index: int
    send_time_s: float
    ack_deadline_s: float
    status: AttemptStatus = AttemptStatus.PENDING
    data_success: bool | None = None
    ack_success: bool | None = None
    failure_reason: str | None = None

    @property
    def success(self) -> bool:
        """Return True when the attempt was acknowledged."""
        return self.status == AttemptStatus.ACKED

    @property
    def failed(self) -> bool:
        """Return True when this attempt failed to produce a usable ACK."""
        return self.status in {
            AttemptStatus.DATA_LOST,
            AttemptStatus.ACK_LOST,
            AttemptStatus.TIMED_OUT,
        }


@dataclass
class ReliabilityMetrics:
    """Aggregate metrics for a link-level ARQ run."""

    generated_packets: int = 0
    delivered_packets: int = 0
    failed_packets: int = 0
    total_attempts: int = 0
    total_retries: int = 0
    ack_packets: int = 0
    timeout_count: int = 0
    total_latency_s: float = 0.0
    total_energy_j: float = 0.0

    @property
    def pdr(self) -> float:
        """Return delivered/generated packet delivery ratio."""
        if self.generated_packets == 0:
            return 0.0
        return self.delivered_packets / self.generated_packets

    @property
    def average_attempts_per_packet(self) -> float:
        """Return the average number of data attempts per generated packet."""
        if self.generated_packets == 0:
            return 0.0
        return self.total_attempts / self.generated_packets

    @property
    def average_latency_s(self) -> float:
        """Return mean latency for delivered packets."""
        if self.delivered_packets == 0:
            return 0.0
        return self.total_latency_s / self.delivered_packets


ReliabilityResult = ReliabilityMetrics


@dataclass(frozen=True)
class ReliabilityEvent:
    """Small structured event record for tests and experiments."""

    time_s: float
    event_type: ReliabilityEventType
    packet_id: int | str
    attempt_index: int
    details: dict[str, float | int | str | bool] = field(default_factory=dict)


@dataclass
class _PacketState:
    packet_id: int | str
    source_id: int
    destination_id: int
    size_bytes: int
    generated_time_s: float
    active_attempt_index: int = 0
    delivered: bool = False
    failed: bool = False


class DeliveryDecision(Protocol):
    """Callable protocol for deterministic test or experiment link outcomes."""

    def __call__(
        self,
        attempt: TransmissionAttempt,
        frame_type: FrameType,
        size_bytes: int,
    ) -> bool:
        """Return True when the frame is received successfully."""


SimpleDecision = Callable[[TransmissionAttempt], bool]


class LinkReliabilityARQ:
    """Scheduler-compatible link-level ARQ with ACK timeout and backoff."""

    def __init__(
        self,
        *,
        scheduler: Scheduler,
        config: ReliabilityConfig | None = None,
        channel: Any | None = None,
        distance_m: float | None = None,
        delivery_decision: DeliveryDecision | None = None,
        data_success: SimpleDecision | None = None,
        ack_success: SimpleDecision | None = None,
    ) -> None:
        """Create an ARQ model for a single logical link."""
        self.scheduler = scheduler
        self.config = config if config is not None else ReliabilityConfig()
        self.channel = channel
        self.distance_m = distance_m
        self.delivery_decision = delivery_decision
        self.data_success = data_success
        self.ack_success = ack_success
        self.metrics = ReliabilityMetrics()
        self.attempts: list[TransmissionAttempt] = []
        self.events: list[ReliabilityEvent] = []
        self.packet_states: dict[int | str, _PacketState] = {}
        self._rng = np.random.default_rng(self.config.seed)

    def send_packet(
        self,
        *,
        packet_id: int | str,
        source_id: int,
        destination_id: int,
        size_bytes: int = 64,
        at_time_s: float | None = None,
    ) -> None:
        """Schedule one generated data packet for link-level transmission."""
        if size_bytes <= 0:
            raise ValueError("size_bytes must be positive")
        send_time_s = self.scheduler.clock.now if at_time_s is None else at_time_s
        if send_time_s < self.scheduler.clock.now:
            raise ValueError("Cannot schedule reliability send in the past")
        if packet_id in self.packet_states:
            raise ValueError("packet_id must be unique for generated packets")

        self.packet_states[packet_id] = _PacketState(
            packet_id=packet_id,
            source_id=source_id,
            destination_id=destination_id,
            size_bytes=size_bytes,
            generated_time_s=send_time_s,
        )
        self.metrics.generated_packets += 1
        self.scheduler.schedule(
            send_time_s,
            self._handle_send_attempt,
            priority=SEND_PRIORITY,
            payload={"packet_id": packet_id, "attempt_index": 0},
        )

    def reset(self) -> None:
        """Reset metrics, attempt history, events, and RNG state."""
        self.metrics = ReliabilityMetrics()
        self.attempts.clear()
        self.events.clear()
        self.packet_states.clear()
        self._rng = np.random.default_rng(self.config.seed)

    def packet_duration_s(self, size_bytes: int) -> float:
        """Return frame airtime in seconds."""
        return (size_bytes * 8.0) / self.config.bitrate_bps

    def _handle_send_attempt(self, payload: dict[str, object]) -> None:
        packet_id = payload["packet_id"]
        attempt_index = int(payload["attempt_index"])
        state = self.packet_states[packet_id]
        if state.delivered or state.failed:
            return

        now_s = self.scheduler.clock.now
        state.active_attempt_index = attempt_index
        attempt = TransmissionAttempt(
            packet_id=state.packet_id,
            source_id=state.source_id,
            destination_id=state.destination_id,
            attempt_index=attempt_index,
            send_time_s=now_s,
            ack_deadline_s=now_s + self.config.ack_timeout_s,
        )
        self.attempts.append(attempt)
        self.metrics.total_attempts += 1
        if attempt_index > 0:
            self.metrics.total_retries += 1
        self._charge_tx(state.size_bytes)
        self._record(
            ReliabilityEventType.DATA_SEND,
            attempt,
            size_bytes=state.size_bytes,
        )

        data_arrival_s = (
            now_s
            + self.packet_duration_s(state.size_bytes)
            + self.config.propagation_delay_s
        )
        attempt.data_success = self._frame_delivers(
            attempt,
            "data",
            state.size_bytes,
        )
        if not attempt.data_success:
            attempt.status = AttemptStatus.DATA_LOST
            attempt.failure_reason = "data_lost"
            self._record(ReliabilityEventType.DATA_LOST, attempt)
            if not self.config.ack_enabled:
                state.failed = True
                self.metrics.failed_packets += 1
                self._record(
                    ReliabilityEventType.PACKET_DROPPED,
                    attempt,
                    reason="data_lost",
                )
                return
            self._schedule_timeout(attempt)
            return

        self._charge_rx(state.size_bytes)
        self.scheduler.schedule(
            data_arrival_s,
            self._handle_data_delivered,
            priority=ACK_ARRIVAL_PRIORITY,
            payload=attempt,
        )
        if self.config.ack_enabled:
            self._schedule_ack(attempt, data_arrival_s)
            self._schedule_timeout(attempt)
        else:
            self.scheduler.schedule(
                data_arrival_s,
                self._handle_unacknowledged_delivery,
                priority=ACK_ARRIVAL_PRIORITY,
                payload=attempt,
            )

    def _handle_data_delivered(self, payload: TransmissionAttempt) -> None:
        attempt = payload
        self._record(ReliabilityEventType.DATA_DELIVERED, attempt)

    def _schedule_ack(
        self,
        attempt: TransmissionAttempt,
        data_arrival_s: float,
    ) -> None:
        ack_send_s = data_arrival_s + self.config.processing_delay_s
        ack_arrival_s = (
            ack_send_s
            + self.packet_duration_s(self.config.ack_size_bytes)
            + self.config.propagation_delay_s
        )
        attempt.ack_success = self._frame_delivers(
            attempt,
            "ack",
            self.config.ack_size_bytes,
        )
        self.metrics.ack_packets += 1
        self._charge_ack_tx()
        self.scheduler.schedule(
            ack_send_s,
            self._handle_ack_send,
            priority=ACK_ARRIVAL_PRIORITY,
            payload=attempt,
        )
        if attempt.ack_success:
            self._charge_ack_rx()
            self.scheduler.schedule(
                ack_arrival_s,
                self._handle_ack_received,
                priority=ACK_ARRIVAL_PRIORITY,
                payload=attempt,
            )
        else:
            attempt.status = AttemptStatus.ACK_LOST
            attempt.failure_reason = "ack_lost"
            self.scheduler.schedule(
                ack_send_s,
                self._handle_ack_lost,
                priority=ACK_ARRIVAL_PRIORITY,
                payload=attempt,
            )

    def _handle_ack_send(self, payload: TransmissionAttempt) -> None:
        self._record(
            ReliabilityEventType.ACK_SEND,
            payload,
            size_bytes=self.config.ack_size_bytes,
        )

    def _handle_ack_lost(self, payload: TransmissionAttempt) -> None:
        self._record(ReliabilityEventType.ACK_LOST, payload)

    def _handle_ack_received(self, payload: TransmissionAttempt) -> None:
        attempt = payload
        state = self.packet_states[attempt.packet_id]
        if (
            state.delivered
            or state.failed
            or state.active_attempt_index != attempt.attempt_index
        ):
            if attempt.status != AttemptStatus.ACKED:
                attempt.status = AttemptStatus.SUPERSEDED
            return

        attempt.status = AttemptStatus.ACKED
        state.delivered = True
        self.metrics.delivered_packets += 1
        self.metrics.total_latency_s += (
            self.scheduler.clock.now - state.generated_time_s
        )
        self._record(ReliabilityEventType.ACK_RECEIVED, attempt)
        self._record(ReliabilityEventType.PACKET_DELIVERED, attempt)

    def _handle_unacknowledged_delivery(self, payload: TransmissionAttempt) -> None:
        attempt = payload
        state = self.packet_states[attempt.packet_id]
        if state.delivered or state.failed:
            return
        attempt.status = AttemptStatus.ACKED
        state.delivered = True
        self.metrics.delivered_packets += 1
        self.metrics.total_latency_s += (
            self.scheduler.clock.now - state.generated_time_s
        )
        self._record(ReliabilityEventType.PACKET_DELIVERED, attempt)

    def _schedule_timeout(self, attempt: TransmissionAttempt) -> None:
        self.scheduler.schedule(
            attempt.ack_deadline_s,
            self._handle_timeout,
            priority=TIMEOUT_PRIORITY,
            payload=attempt,
        )

    def _handle_timeout(self, payload: TransmissionAttempt) -> None:
        attempt = payload
        state = self.packet_states[attempt.packet_id]
        if (
            state.delivered
            or state.failed
            or state.active_attempt_index != attempt.attempt_index
        ):
            if attempt.status != AttemptStatus.ACKED:
                attempt.status = AttemptStatus.SUPERSEDED
            return

        self.metrics.timeout_count += 1
        if attempt.status == AttemptStatus.PENDING:
            attempt.status = AttemptStatus.TIMED_OUT
            attempt.failure_reason = "timeout"
        self._record(
            ReliabilityEventType.TIMEOUT,
            attempt,
            reason=attempt.failure_reason or "timeout",
        )

        if attempt.attempt_index >= self.config.retry_limit:
            state.failed = True
            self.metrics.failed_packets += 1
            self._record(
                ReliabilityEventType.PACKET_DROPPED,
                attempt,
                reason=attempt.failure_reason or "retry_limit_exceeded",
            )
            return

        backoff_s = self._next_backoff_s(attempt.attempt_index)
        retry_time_s = self.scheduler.clock.now + backoff_s
        self._record(
            ReliabilityEventType.BACKOFF,
            attempt,
            backoff_s=backoff_s,
            next_attempt=attempt.attempt_index + 1,
        )
        self.scheduler.schedule(
            retry_time_s,
            self._handle_send_attempt,
            priority=RETRY_PRIORITY,
            payload={
                "packet_id": attempt.packet_id,
                "attempt_index": attempt.attempt_index + 1,
            },
        )

    def _next_backoff_s(self, attempt_index: int) -> float:
        window_s = min(
            self.config.max_backoff_s,
            self.config.base_backoff_s
            * (self.config.backoff_multiplier ** attempt_index),
        )
        if window_s == 0.0:
            return 0.0
        return float(window_s * (0.5 + 0.5 * self._rng.random()))

    def _frame_delivers(
        self,
        attempt: TransmissionAttempt,
        frame_type: FrameType,
        size_bytes: int,
    ) -> bool:
        if self.delivery_decision is not None:
            return bool(self.delivery_decision(attempt, frame_type, size_bytes))
        if frame_type == "data" and self.data_success is not None:
            return bool(self.data_success(attempt))
        if frame_type == "ack" and self.ack_success is not None:
            return bool(self.ack_success(attempt))
        if self.channel is None:
            return True
        if self.distance_m is None:
            raise ValueError("distance_m is required when channel is supplied")

        stats = self.channel.calculate_link_stats(
            self.distance_m,
            size_bytes,
            include_shadowing=self.config.include_shadowing,
            include_success=False,
            prr_mode=self.config.channel_prr_mode,
        )
        prr = (
            stats.prr_logistic
            if self.config.channel_prr_mode == "logistic"
            else stats.prr_ber
        )
        return bool(self._rng.random() < prr)

    def _charge_tx(self, size_bytes: int) -> None:
        self.metrics.total_energy_j += (
            size_bytes * 8 * self.config.tx_energy_per_bit_j
        )

    def _charge_rx(self, size_bytes: int) -> None:
        self.metrics.total_energy_j += (
            size_bytes * 8 * self.config.rx_energy_per_bit_j
        )

    def _charge_ack_tx(self) -> None:
        self._charge_tx(self.config.ack_size_bytes)

    def _charge_ack_rx(self) -> None:
        self._charge_rx(self.config.ack_size_bytes)

    def _record(
        self,
        event_type: ReliabilityEventType,
        attempt: TransmissionAttempt,
        **details: float | int | str | bool,
    ) -> None:
        self.events.append(
            ReliabilityEvent(
                time_s=self.scheduler.clock.now,
                event_type=event_type,
                packet_id=attempt.packet_id,
                attempt_index=attempt.attempt_index,
                details=dict(details),
            )
        )


ReliabilityARQ = LinkReliabilityARQ
