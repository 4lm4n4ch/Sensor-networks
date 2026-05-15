"""Week 10 WSN security and replay-protection model.

The module simulates authentication metadata and processing overhead; it does
not implement cryptography. Replay protection is a deterministic high-water
mark per ``(sender_id, receiver_id)`` flow: sequence numbers must strictly
increase to be accepted. This keeps the model small and predictable for M3
security experiments while still exercising the main replay-abuse case.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class SecurityConfig:
    """Configuration for simulated WSN authentication overhead.

    ``sequence_window`` is documented for future sliding-window work. Week 10
    uses strict in-order sequence checks, so packets at or below the last
    accepted sequence number are rejected as replay/old packets.
    """

    enabled: bool = True
    replay_protection: bool = True
    auth_tag_bytes: int = 8
    nonce_bytes: int = 4
    sequence_window: int = 0
    cpu_cost_per_byte_j: float = 2.0e-9
    verify_cost_per_byte_j: float = 3.0e-9
    seed: int = 2026
    latency_cost_per_byte_s: float = 2.0e-6

    def __post_init__(self) -> None:
        """Validate model parameters."""
        if self.auth_tag_bytes < 0:
            raise ValueError("auth_tag_bytes must be non-negative")
        if self.nonce_bytes < 0:
            raise ValueError("nonce_bytes must be non-negative")
        if self.sequence_window < 0:
            raise ValueError("sequence_window must be non-negative")
        if self.cpu_cost_per_byte_j < 0.0:
            raise ValueError("cpu_cost_per_byte_j must be non-negative")
        if self.verify_cost_per_byte_j < 0.0:
            raise ValueError("verify_cost_per_byte_j must be non-negative")
        if self.latency_cost_per_byte_s < 0.0:
            raise ValueError("latency_cost_per_byte_s must be non-negative")

    @property
    def overhead_bytes_per_packet(self) -> int:
        """Return nonce plus authentication-tag bytes for secured packets."""
        if not self.enabled:
            return 0
        return self.auth_tag_bytes + self.nonce_bytes


@dataclass(frozen=True)
class SecurePacketMetadata:
    """Security metadata carried by a simulated packet."""

    sender_id: int
    receiver_id: int
    sequence_number: int
    nonce: int | bytes | str
    auth_tag_bytes: int
    timestamp_s: float | None = None

    def __post_init__(self) -> None:
        """Validate packet metadata."""
        if self.sequence_number < 0:
            raise ValueError("sequence_number must be non-negative")
        if self.auth_tag_bytes < 0:
            raise ValueError("auth_tag_bytes must be non-negative")
        if self.timestamp_s is not None and self.timestamp_s < 0.0:
            raise ValueError("timestamp_s must be non-negative")


@dataclass(frozen=True)
class SecurityDecision:
    """Result of checking one packet at the security layer."""

    accepted: bool
    reason: str
    overhead_bytes: int
    cpu_energy_j: float
    latency_overhead_s: float


@dataclass
class SecurityMetrics:
    """Cumulative counters for security checks and overhead."""

    packets_checked: int = 0
    packets_accepted: int = 0
    packets_rejected: int = 0
    replay_rejected: int = 0
    overhead_bytes_total: int = 0
    cpu_energy_j_total: float = 0.0
    latency_overhead_s_total: float = 0.0


@dataclass
class SecurityLayer:
    """Deterministic replay protection and security-overhead accounting."""

    config: SecurityConfig = field(default_factory=SecurityConfig)

    def __post_init__(self) -> None:
        """Initialize deterministic state."""
        self.metrics = SecurityMetrics()
        self._last_sequence_by_flow: dict[tuple[int, int], int] = {}
        self._next_sequence_by_flow: dict[tuple[int, int], int] = {}
        self._rng = np.random.default_rng(self.config.seed)

    def make_metadata(
        self,
        *,
        sender_id: int,
        receiver_id: int,
        sequence_number: int | None = None,
        timestamp_s: float | None = None,
    ) -> SecurePacketMetadata:
        """Create deterministic packet-security metadata for one flow."""
        flow = (sender_id, receiver_id)
        if sequence_number is None:
            sequence_number = self._next_sequence_by_flow.get(flow, 0)
            self._next_sequence_by_flow[flow] = sequence_number + 1

        return SecurePacketMetadata(
            sender_id=sender_id,
            receiver_id=receiver_id,
            sequence_number=sequence_number,
            nonce=self._next_nonce(),
            auth_tag_bytes=self.config.auth_tag_bytes if self.config.enabled else 0,
            timestamp_s=timestamp_s,
        )

    def check_packet(
        self,
        metadata: SecurePacketMetadata,
        *,
        payload_bytes: int,
        include_auth_generation: bool = True,
    ) -> SecurityDecision:
        """Check one packet and update cumulative security metrics.

        ``include_auth_generation`` accounts for sender-side MAC/auth-tag
        generation. Replayed packets can set it to ``False`` to model an
        attacker retransmitting old bytes while the receiver still pays
        verification cost.
        """
        if payload_bytes < 0:
            raise ValueError("payload_bytes must be non-negative")

        if not self.config.enabled:
            decision = SecurityDecision(
                accepted=True,
                reason="security_disabled",
                overhead_bytes=0,
                cpu_energy_j=0.0,
                latency_overhead_s=0.0,
            )
            self._record(decision)
            return decision

        overhead_bytes = self.config.overhead_bytes_per_packet
        processed_bytes = payload_bytes + overhead_bytes
        cpu_energy_j = processed_bytes * self.config.verify_cost_per_byte_j
        if include_auth_generation:
            cpu_energy_j += processed_bytes * self.config.cpu_cost_per_byte_j
        latency_overhead_s = processed_bytes * self.config.latency_cost_per_byte_s

        accepted, reason = self._replay_decision(metadata)
        decision = SecurityDecision(
            accepted=accepted,
            reason=reason,
            overhead_bytes=overhead_bytes,
            cpu_energy_j=cpu_energy_j,
            latency_overhead_s=latency_overhead_s,
        )
        self._record(decision)
        return decision

    def reset(self) -> None:
        """Clear replay state and cumulative metrics, preserving the config."""
        self.metrics = SecurityMetrics()
        self._last_sequence_by_flow.clear()
        self._next_sequence_by_flow.clear()
        self._rng = np.random.default_rng(self.config.seed)

    def _replay_decision(
        self,
        metadata: SecurePacketMetadata,
    ) -> tuple[bool, str]:
        """Return replay-protection decision for one packet."""
        if not self.config.replay_protection:
            return True, "accepted_no_replay_protection"

        flow = (metadata.sender_id, metadata.receiver_id)
        last_sequence = self._last_sequence_by_flow.get(flow)
        if last_sequence is None or metadata.sequence_number > last_sequence:
            self._last_sequence_by_flow[flow] = metadata.sequence_number
            return True, "accepted"

        if metadata.sequence_number == last_sequence:
            return False, "replay_duplicate_sequence"
        return False, "replay_old_sequence"

    def _record(self, decision: SecurityDecision) -> None:
        """Update cumulative metrics from a decision."""
        self.metrics.packets_checked += 1
        if decision.accepted:
            self.metrics.packets_accepted += 1
        else:
            self.metrics.packets_rejected += 1
            if decision.reason.startswith("replay_"):
                self.metrics.replay_rejected += 1
        self.metrics.overhead_bytes_total += decision.overhead_bytes
        self.metrics.cpu_energy_j_total += decision.cpu_energy_j
        self.metrics.latency_overhead_s_total += decision.latency_overhead_s

    def _next_nonce(self) -> int:
        """Return a deterministic nonce value with the configured byte width."""
        if self.config.nonce_bytes == 0:
            return 0

        return int.from_bytes(self._rng.bytes(self.config.nonce_bytes), "big")
