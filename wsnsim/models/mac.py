"""MAC protocols and collision-domain logic for Week 4.

This module intentionally models a small MAC layer, not a full IEEE 802.15.4
implementation. Transmissions occupy half-open time intervals
``[start_time_s, end_time_s)`` on a channel. Two packets collide when their
active intervals overlap on the same channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import numpy as np

from wsnsim.models.energy import EnergyModel, EnergyState
from wsnsim.sim import Scheduler


TRANSMISSION_END_PRIORITY = -10
SEND_REQUEST_PRIORITY = 0
RETRY_PRIORITY = 1


class PacketStatus(Enum):
    """Lifecycle states for one MAC packet."""

    PENDING = "pending"
    TRANSMITTING = "transmitting"
    DELIVERED = "delivered"
    COLLIDED = "collided"
    DROPPED = "dropped"


class MacEventType(Enum):
    """Traceable MAC events."""

    SEND_REQUEST = "send_request"
    CARRIER_SENSE = "carrier_sense"
    TRANSMISSION_START = "transmission_start"
    TRANSMISSION_END = "transmission_end"
    BACKOFF = "backoff"
    PACKET_DELIVERED = "packet_delivered"
    PACKET_COLLIDED = "packet_collided"
    PACKET_DROPPED = "packet_dropped"


@dataclass(frozen=True)
class MACPacket:
    """Packet metadata needed by the MAC layer."""

    packet_id: int
    source_id: int
    destination_id: int
    created_at_s: float = 0.0
    size_bytes: int = 64
    channel_id: str = "default"

    def __post_init__(self) -> None:
        """Validate packet fields."""
        if self.created_at_s < 0.0:
            raise ValueError("created_at_s must be non-negative")
        if self.size_bytes <= 0:
            raise ValueError("size_bytes must be positive")


@dataclass
class Transmission:
    """One active or completed transmission interval."""

    packet: MACPacket
    start_time_s: float
    duration_s: float
    attempt: int = 0
    collided: bool = False

    def __post_init__(self) -> None:
        """Validate timing values."""
        if self.start_time_s < 0.0:
            raise ValueError("start_time_s must be non-negative")
        if self.duration_s <= 0.0:
            raise ValueError("duration_s must be positive")
        if self.attempt < 0:
            raise ValueError("attempt must be non-negative")

    @property
    def end_time_s(self) -> float:
        """Return exclusive transmission end time."""
        return self.start_time_s + self.duration_s


@dataclass
class MACResult:
    """Final and intermediate state for a packet handled by a MAC protocol."""

    packet: MACPacket
    status: PacketStatus = PacketStatus.PENDING
    attempts: int = 0
    first_request_time_s: float | None = None
    start_times_s: list[float] = field(default_factory=list)
    end_time_s: float | None = None
    delivered_time_s: float | None = None
    collision_count: int = 0
    backoffs_s: list[float] = field(default_factory=list)
    drop_reason: str | None = None

    @property
    def delay_s(self) -> float | None:
        """Return request-to-delivery delay for delivered packets."""
        if self.delivered_time_s is None or self.first_request_time_s is None:
            return None
        return self.delivered_time_s - self.first_request_time_s


@dataclass(frozen=True)
class MACEvent:
    """Small structured trace record for tests and experiments."""

    time_s: float
    event_type: MacEventType
    packet_id: int
    source_id: int
    attempt: int = 0
    details: dict[str, float | int | str | bool] = field(default_factory=dict)


class ChannelSuccessModel(Protocol):
    """Protocol for optional packet-level channel acceptance hooks."""

    def __call__(self, packet: MACPacket) -> bool:
        """Return True if the channel allows this packet to be delivered."""


def transmission_intervals_overlap(
    start_a_s: float,
    duration_a_s: float,
    start_b_s: float,
    duration_b_s: float,
) -> bool:
    """Return True when two half-open transmission intervals overlap."""
    if duration_a_s <= 0.0 or duration_b_s <= 0.0:
        raise ValueError("transmission durations must be positive")

    end_a_s = start_a_s + duration_a_s
    end_b_s = start_b_s + duration_b_s
    return start_a_s < end_b_s and start_b_s < end_a_s


class CollisionDomain:
    """Shared medium that tracks active transmissions and marks collisions."""

    def __init__(self) -> None:
        self.active_transmissions: list[Transmission] = []
        self.completed_transmissions: list[Transmission] = []

    def is_busy(self, time_s: float, channel_id: str = "default") -> bool:
        """Return True if any active transmission overlaps ``time_s``."""
        return any(
            tx.packet.channel_id == channel_id
            and tx.start_time_s <= time_s < tx.end_time_s
            for tx in self.active_transmissions
        )

    def start_transmission(self, transmission: Transmission) -> Transmission:
        """Register a new transmission and mark all overlapping packets."""
        for active in self.active_transmissions:
            if active.packet.channel_id != transmission.packet.channel_id:
                continue
            if transmission_intervals_overlap(
                active.start_time_s,
                active.duration_s,
                transmission.start_time_s,
                transmission.duration_s,
            ):
                active.collided = True
                transmission.collided = True

        self.active_transmissions.append(transmission)
        return transmission

    def finish_transmission(self, transmission: Transmission) -> Transmission:
        """Remove an active transmission and store it as completed."""
        self.active_transmissions = [
            active
            for active in self.active_transmissions
            if active is not transmission
        ]
        self.completed_transmissions.append(transmission)
        return transmission


class BaseMAC:
    """Base class for scheduler-compatible MAC protocol strategies."""

    def __init__(
        self,
        *,
        scheduler: Scheduler,
        medium: CollisionDomain,
        bitrate_bps: float = 250_000.0,
        energy_models: dict[int, EnergyModel] | None = None,
        channel_success: ChannelSuccessModel | None = None,
    ) -> None:
        if bitrate_bps <= 0.0:
            raise ValueError("bitrate_bps must be positive")

        self.scheduler = scheduler
        self.medium = medium
        self.bitrate_bps = bitrate_bps
        self.energy_models = energy_models if energy_models is not None else {}
        self.channel_success = channel_success
        self.results: dict[int, MACResult] = {}
        self.events: list[MACEvent] = []

    def send(
        self,
        packet: MACPacket,
        *,
        at_time_s: float | None = None,
        duration_s: float | None = None,
    ) -> None:
        """Schedule a MAC send request for ``packet``."""
        request_time_s = self.scheduler.clock.now if at_time_s is None else at_time_s
        if request_time_s < self.scheduler.clock.now:
            raise ValueError("Cannot schedule MAC send request in the past")

        result = self.results.setdefault(packet.packet_id, MACResult(packet=packet))
        result.first_request_time_s = request_time_s

        self.scheduler.schedule(
            request_time_s,
            self._handle_send_request,
            priority=SEND_REQUEST_PRIORITY,
            payload={
                "packet": packet,
                "duration_s": duration_s,
                "attempt": 0,
                "cw": None,
            },
        )

    def packet_duration_s(self, packet: MACPacket) -> float:
        """Return packet airtime from packet size and configured bitrate."""
        return (packet.size_bytes * 8.0) / self.bitrate_bps

    def _handle_send_request(self, payload: dict[str, object]) -> None:
        raise NotImplementedError

    def _start_transmission(
        self,
        packet: MACPacket,
        *,
        duration_s: float | None,
        attempt: int,
    ) -> Transmission:
        now_s = self.scheduler.clock.now
        tx_duration_s = (
            self.packet_duration_s(packet) if duration_s is None else duration_s
        )
        transmission = Transmission(
            packet=packet,
            start_time_s=now_s,
            duration_s=tx_duration_s,
            attempt=attempt,
        )
        self.medium.start_transmission(transmission)

        result = self.results.setdefault(packet.packet_id, MACResult(packet=packet))
        result.status = PacketStatus.TRANSMITTING
        result.attempts += 1
        result.start_times_s.append(now_s)

        self._transition_energy(packet.source_id, EnergyState.TX, now_s)
        self._record(
            MacEventType.TRANSMISSION_START,
            packet,
            attempt,
            duration_s=tx_duration_s,
            collided=transmission.collided,
        )

        self.scheduler.schedule(
            transmission.end_time_s,
            self._handle_transmission_end,
            priority=TRANSMISSION_END_PRIORITY,
            payload=transmission,
        )
        return transmission

    def _handle_transmission_end(self, payload: Transmission) -> None:
        transmission = payload
        now_s = self.scheduler.clock.now
        self.medium.finish_transmission(transmission)
        self._transition_energy(transmission.packet.source_id, EnergyState.IDLE, now_s)
        self._record(
            MacEventType.TRANSMISSION_END,
            transmission.packet,
            transmission.attempt,
            collided=transmission.collided,
        )
        self._finalize_attempt(transmission)

    def _finalize_attempt(self, transmission: Transmission) -> None:
        packet = transmission.packet
        result = self.results[packet.packet_id]
        result.end_time_s = self.scheduler.clock.now

        channel_allows = (
            True if self.channel_success is None else self.channel_success(packet)
        )
        if not transmission.collided and channel_allows:
            result.status = PacketStatus.DELIVERED
            result.delivered_time_s = self.scheduler.clock.now
            self._record(
                MacEventType.PACKET_DELIVERED,
                packet,
                transmission.attempt,
            )
            return

        result.collision_count += int(transmission.collided)
        result.status = PacketStatus.COLLIDED
        result.drop_reason = (
            "collision" if transmission.collided else "channel_rejected"
        )
        self._record(
            MacEventType.PACKET_COLLIDED,
            packet,
            transmission.attempt,
            reason=result.drop_reason,
        )

    def _transition_energy(
        self,
        node_id: int,
        state: EnergyState,
        time_s: float,
    ) -> None:
        """Hook MAC events into the Week 3 state-based energy model."""
        energy_model = self.energy_models.get(node_id)
        if energy_model is not None:
            energy_model.transition_to(state, time_s)

    def _record(
        self,
        event_type: MacEventType,
        packet: MACPacket,
        attempt: int,
        **details: float | int | str | bool,
    ) -> None:
        self.events.append(
            MACEvent(
                time_s=self.scheduler.clock.now,
                event_type=event_type,
                packet_id=packet.packet_id,
                source_id=packet.source_id,
                attempt=attempt,
                details=dict(details),
            )
        )


class AlohaMAC(BaseMAC):
    """Pure ALOHA-style MAC: send immediately without carrier sensing."""

    def _handle_send_request(self, payload: dict[str, object]) -> None:
        packet = payload["packet"]
        duration_s = payload["duration_s"]
        attempt = int(payload["attempt"])
        if not isinstance(packet, MACPacket):
            raise TypeError("payload packet must be a MACPacket")

        self._record(MacEventType.SEND_REQUEST, packet, attempt)
        self._start_transmission(
            packet,
            duration_s=None if duration_s is None else float(duration_s),
            attempt=attempt,
        )


class CSMAMAC(BaseMAC):
    """Simplified CSMA MAC with carrier sensing and exponential backoff.

    Simplifications versus IEEE 802.15.4 CSMA/CA:
    - no superframes, beacons, ACK frames, turnaround time, or CCA timing;
    - no RSSI/energy-detection threshold, hidden terminals, or capture effect;
    - channel sensing is instantaneous and only checks active interval overlap;
    - backoff uses a direct contention window in slots rather than the full
      802.15.4 NB/BE state machine.
    """

    def __init__(
        self,
        *,
        scheduler: Scheduler,
        medium: CollisionDomain,
        slot_time_s: float = 0.001,
        cw_min: int = 3,
        cw_max: int = 31,
        max_retries: int = 4,
        seed: int | None = 42,
        bitrate_bps: float = 250_000.0,
        energy_models: dict[int, EnergyModel] | None = None,
        channel_success: ChannelSuccessModel | None = None,
    ) -> None:
        if slot_time_s <= 0.0:
            raise ValueError("slot_time_s must be positive")
        if cw_min < 0:
            raise ValueError("cw_min must be non-negative")
        if cw_max < cw_min:
            raise ValueError("cw_max must be greater than or equal to cw_min")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        super().__init__(
            scheduler=scheduler,
            medium=medium,
            bitrate_bps=bitrate_bps,
            energy_models=energy_models,
            channel_success=channel_success,
        )
        self.slot_time_s = slot_time_s
        self.cw_min = cw_min
        self.cw_max = cw_max
        self.max_retries = max_retries
        self.rng = np.random.default_rng(seed)

    def _handle_send_request(self, payload: dict[str, object]) -> None:
        packet = payload["packet"]
        duration_s = payload["duration_s"]
        attempt = int(payload["attempt"])
        cw = self.cw_min if payload["cw"] is None else int(payload["cw"])
        if not isinstance(packet, MACPacket):
            raise TypeError("payload packet must be a MACPacket")

        self._record(MacEventType.SEND_REQUEST, packet, attempt)
        self._carrier_sense(packet, duration_s=duration_s, attempt=attempt, cw=cw)

    def _carrier_sense(
        self,
        packet: MACPacket,
        *,
        duration_s: float | None,
        attempt: int,
        cw: int,
    ) -> None:
        now_s = self.scheduler.clock.now
        self._transition_energy(packet.source_id, EnergyState.RX, now_s)
        busy = self.medium.is_busy(now_s, packet.channel_id)
        self._record(
            MacEventType.CARRIER_SENSE,
            packet,
            attempt,
            busy=busy,
            cw=cw,
        )

        if busy:
            self._transition_energy(packet.source_id, EnergyState.IDLE, now_s)
            if attempt >= self.max_retries:
                self._drop_packet(packet, attempt, reason="max_retries_busy")
                return
            self._schedule_backoff(
                packet,
                duration_s=duration_s,
                attempt=attempt,
                cw=cw,
            )
            return

        self._start_transmission(
            packet,
            duration_s=None if duration_s is None else float(duration_s),
            attempt=attempt,
        )

    def _schedule_backoff(
        self,
        packet: MACPacket,
        *,
        duration_s: float | None,
        attempt: int,
        cw: int,
    ) -> None:
        random_slots = int(self.rng.integers(0, cw + 1))
        backoff_time_s = random_slots * self.slot_time_s
        next_cw = min(self.cw_max, max(1, (cw + 1) * 2 - 1))
        result = self.results.setdefault(packet.packet_id, MACResult(packet=packet))
        result.backoffs_s.append(backoff_time_s)

        self._record(
            MacEventType.BACKOFF,
            packet,
            attempt,
            random_slots=random_slots,
            backoff_time_s=backoff_time_s,
            next_cw=next_cw,
        )

        self.scheduler.schedule(
            self.scheduler.clock.now + backoff_time_s,
            self._handle_send_request,
            priority=RETRY_PRIORITY,
            payload={
                "packet": packet,
                "duration_s": duration_s,
                "attempt": attempt + 1,
                "cw": next_cw,
            },
        )

    def _finalize_attempt(self, transmission: Transmission) -> None:
        packet = transmission.packet
        result = self.results[packet.packet_id]
        result.end_time_s = self.scheduler.clock.now

        channel_allows = (
            True if self.channel_success is None else self.channel_success(packet)
        )
        if not transmission.collided and channel_allows:
            result.status = PacketStatus.DELIVERED
            result.delivered_time_s = self.scheduler.clock.now
            self._record(
                MacEventType.PACKET_DELIVERED,
                packet,
                transmission.attempt,
            )
            return

        result.collision_count += int(transmission.collided)
        reason = "collision" if transmission.collided else "channel_rejected"
        if transmission.attempt >= self.max_retries:
            self._drop_packet(packet, transmission.attempt, reason=reason)
            return

        result.status = PacketStatus.PENDING
        result.drop_reason = reason
        cw = min(
            self.cw_max,
            max(1, (self.cw_min + 1) * (2 ** (transmission.attempt + 1)) - 1),
        )
        self._record(
            MacEventType.PACKET_COLLIDED,
            packet,
            transmission.attempt,
            reason=reason,
            retry=True,
        )
        self._schedule_backoff(
            packet,
            duration_s=transmission.duration_s,
            attempt=transmission.attempt,
            cw=cw,
        )

    def _drop_packet(self, packet: MACPacket, attempt: int, *, reason: str) -> None:
        result = self.results.setdefault(packet.packet_id, MACResult(packet=packet))
        result.status = PacketStatus.DROPPED
        result.end_time_s = self.scheduler.clock.now
        result.drop_reason = reason
        self._record(
            MacEventType.PACKET_DROPPED,
            packet,
            attempt,
            reason=reason,
        )


# Backwards-compatible name for the old placeholder class.
MAC = BaseMAC
