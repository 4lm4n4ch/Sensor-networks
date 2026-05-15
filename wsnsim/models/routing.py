"""Week 6 routing baselines for WSN data collection.

The routing layer intentionally uses the static Week 5 neighbor graph as the
default data-plane link model. A channel can be supplied for optional
probabilistic one-hop delivery, but Week 6 does not model ACKs, retransmissions,
queues, congestion, or full RPL/6LoWPAN behavior.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

import numpy as np

from wsnsim.models.topology import Topology


class RoutingAction(Enum):
    """Routing action returned by one routing decision."""

    FORWARD = "forward"
    DELIVER = "deliver"
    DROP = "drop"


@dataclass(frozen=True)
class RoutingPacket:
    """Packet metadata used by routing protocols."""

    packet_id: int | str
    source_id: int
    destination_id: int
    current_node_id: int
    previous_node_id: int | None
    created_time_s: float
    ttl: int
    payload_bits: int
    hop_count: int = 0

    def __post_init__(self) -> None:
        """Validate packet fields."""
        if self.created_time_s < 0.0:
            raise ValueError("created_time_s must be non-negative")
        if self.ttl < 0:
            raise ValueError("ttl must be non-negative")
        if self.payload_bits <= 0:
            raise ValueError("payload_bits must be positive")
        if self.hop_count < 0:
            raise ValueError("hop_count must be non-negative")


@dataclass(frozen=True)
class RouteDecision:
    """Result of a routing decision for one packet at one node."""

    action: RoutingAction
    reason: str
    next_hop_ids: tuple[int, ...] = ()

    @property
    def next_hop_id(self) -> int | None:
        """Return the single next hop, or ``None`` for multi-hop decisions."""
        if len(self.next_hop_ids) == 1:
            return self.next_hop_ids[0]
        return None


@dataclass
class RoutingMetrics:
    """Aggregate metrics for routing experiments."""

    generated_packets: int = 0
    delivered_packets: int = 0
    dropped_packets: int = 0
    duplicate_packets: int = 0
    total_hops: int = 0
    total_latency_s: float = 0.0
    total_energy_j: float = 0.0
    control_overhead_packets: int = 0
    generated_payload_bits: int = 0
    delivered_payload_bits: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def pdr(self) -> float:
        """Return packet delivery ratio."""
        if self.generated_packets == 0:
            return 0.0
        return self.delivered_packets / self.generated_packets

    @property
    def average_latency_s(self) -> float:
        """Return average delivered-packet latency in seconds."""
        if self.delivered_packets == 0:
            return 0.0
        return self.total_latency_s / self.delivered_packets

    @property
    def average_hop_count(self) -> float:
        """Return average delivered-packet hop count."""
        if self.delivered_packets == 0:
            return 0.0
        return self.total_hops / self.delivered_packets

    @property
    def energy_per_delivered_bit_j(self) -> float:
        """Return energy per delivered payload bit in joules/bit."""
        if self.delivered_payload_bits <= 0:
            return float("inf")
        return self.total_energy_j / self.delivered_payload_bits

    @property
    def energy_per_generated_bit_j(self) -> float:
        """Return energy per generated payload bit in joules/bit."""
        if self.generated_payload_bits <= 0:
            return float("inf")
        return self.total_energy_j / self.generated_payload_bits

    def record_drop(self, reason: str) -> None:
        """Record one dropped packet or forwarding copy."""
        self.dropped_packets += 1
        self.drop_reasons[reason] = self.drop_reasons.get(reason, 0) + 1


@dataclass(frozen=True)
class RoutingConfig:
    """Shared deterministic routing parameters."""

    hop_delay_s: float = 0.01
    tx_energy_per_bit_j: float = 50e-9
    rx_energy_per_bit_j: float = 50e-9
    use_link_success: bool = False
    channel_prr_mode: str = "logistic"
    include_shadowing: bool = False
    seed: int | None = 42

    def __post_init__(self) -> None:
        """Validate routing configuration."""
        if self.hop_delay_s < 0.0:
            raise ValueError("hop_delay_s must be non-negative")
        if self.tx_energy_per_bit_j < 0.0:
            raise ValueError("tx_energy_per_bit_j must be non-negative")
        if self.rx_energy_per_bit_j < 0.0:
            raise ValueError("rx_energy_per_bit_j must be non-negative")
        if self.channel_prr_mode not in ("logistic", "ber"):
            raise ValueError("channel_prr_mode must be 'logistic' or 'ber'")


class FloodingRouting:
    """Flooding routing with TTL and per-node seen-cache duplicate suppression."""

    def __init__(
        self,
        topology: Topology,
        *,
        sink_id: int | None = None,
        config: RoutingConfig | None = None,
        channel: Any | None = None,
    ) -> None:
        """Create a flooding router for a static topology."""
        self.topology = topology
        self.sink_id = _resolve_sink_id(topology, sink_id)
        self.config = config if config is not None else RoutingConfig()
        self.channel = channel
        self.metrics = RoutingMetrics()
        self.seen_cache: set[tuple[int | str, int]] = set()
        self._rng = np.random.default_rng(self.config.seed)

    def reset(self) -> None:
        """Clear metrics and duplicate state."""
        self.metrics = RoutingMetrics()
        self.seen_cache.clear()
        self._rng = np.random.default_rng(self.config.seed)

    def route_packet(self, packet: RoutingPacket) -> RoutingMetrics:
        """Route one generated packet and return cumulative metrics."""
        self.metrics.generated_packets += 1
        self.metrics.generated_payload_bits += packet.payload_bits
        start_packet = replace(
            packet,
            destination_id=self.sink_id,
            current_node_id=packet.source_id,
            previous_node_id=None,
            hop_count=0,
        )
        queue: deque[RoutingPacket] = deque([start_packet])

        while queue:
            current_packet = queue.popleft()
            decision = self.decide(current_packet)

            if decision.action == RoutingAction.DELIVER:
                self._record_delivery(current_packet)
                continue
            if decision.action == RoutingAction.DROP:
                self.metrics.record_drop(decision.reason)
                continue

            self.metrics.control_overhead_packets += len(decision.next_hop_ids)
            self._charge_tx(current_packet.payload_bits)
            for next_hop_id in decision.next_hop_ids:
                if self._link_delivers(
                    current_packet.current_node_id,
                    next_hop_id,
                    current_packet.payload_bits,
                ):
                    self._charge_rx(current_packet.payload_bits)
                    queue.append(
                        replace(
                            current_packet,
                            current_node_id=next_hop_id,
                            previous_node_id=current_packet.current_node_id,
                            ttl=current_packet.ttl - 1,
                            hop_count=current_packet.hop_count + 1,
                        )
                    )
                else:
                    self.metrics.record_drop("link_failure")

        return self.metrics

    def decide(self, packet: RoutingPacket) -> RouteDecision:
        """Return the flooding decision for a packet at its current node."""
        seen_key = (packet.packet_id, packet.current_node_id)
        if seen_key in self.seen_cache:
            self.metrics.duplicate_packets += 1
            return RouteDecision(RoutingAction.DROP, "duplicate")
        self.seen_cache.add(seen_key)

        if packet.current_node_id == self.sink_id:
            return RouteDecision(RoutingAction.DELIVER, "reached_sink")
        if packet.ttl <= 0:
            return RouteDecision(RoutingAction.DROP, "ttl_expired")

        next_hops = tuple(
            neighbor_id
            for neighbor_id in sorted(self.topology.neighbors(packet.current_node_id))
            if neighbor_id != packet.previous_node_id
        )
        if not next_hops:
            return RouteDecision(RoutingAction.DROP, "no_forwarding_neighbor")
        return RouteDecision(RoutingAction.FORWARD, "flood", next_hops)

    def _record_delivery(self, packet: RoutingPacket) -> None:
        """Record a sink delivery."""
        self.metrics.delivered_packets += 1
        self.metrics.total_hops += packet.hop_count
        self.metrics.total_latency_s += packet.hop_count * self.config.hop_delay_s
        self.metrics.delivered_payload_bits += packet.payload_bits

    def _link_delivers(
        self,
        source_id: int,
        target_id: int,
        payload_bits: int,
    ) -> bool:
        """Return whether a one-hop transmission succeeds."""
        if not self.config.use_link_success:
            return True
        if self.channel is None:
            raise ValueError("channel is required when use_link_success=True")

        distance_m = self.topology.distance_between(source_id, target_id)
        packet_size_bytes = max(1, (payload_bits + 7) // 8)
        stats = self.channel.calculate_link_stats(
            distance_m,
            packet_size_bytes,
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

    def _charge_tx(self, payload_bits: int) -> None:
        """Add one packet transmission energy."""
        self.metrics.total_energy_j += (
            payload_bits * self.config.tx_energy_per_bit_j
        )

    def _charge_rx(self, payload_bits: int) -> None:
        """Add one packet reception energy."""
        self.metrics.total_energy_j += (
            payload_bits * self.config.rx_energy_per_bit_j
        )


class SinkTreeRouting:
    """Shortest-hop sink-tree routing using BFS parent selection."""

    def __init__(
        self,
        topology: Topology,
        *,
        sink_id: int | None = None,
        config: RoutingConfig | None = None,
        channel: Any | None = None,
    ) -> None:
        """Build a BFS parent map rooted at the sink."""
        self.topology = topology
        self.sink_id = _resolve_sink_id(topology, sink_id)
        self.config = config if config is not None else RoutingConfig()
        self.channel = channel
        self.metrics = RoutingMetrics()
        self.parent_map = self.build_parent_map()
        self.hop_distance_map = self._build_hop_distance_map()
        self._rng = np.random.default_rng(self.config.seed)

    def reset(self) -> None:
        """Clear metrics and rebuild deterministic state."""
        self.metrics = RoutingMetrics()
        self.parent_map = self.build_parent_map()
        self.hop_distance_map = self._build_hop_distance_map()
        self._rng = np.random.default_rng(self.config.seed)

    def build_parent_map(self) -> dict[int, int | None]:
        """Return node-to-parent table from a BFS tree rooted at the sink."""
        parent_map: dict[int, int | None] = {self.sink_id: None}
        visited = {self.sink_id}
        queue: deque[int] = deque([self.sink_id])

        while queue:
            node_id = queue.popleft()
            for neighbor_id in sorted(self.topology.neighbors(node_id)):
                if neighbor_id in visited:
                    continue
                visited.add(neighbor_id)
                parent_map[neighbor_id] = node_id
                queue.append(neighbor_id)

        return parent_map

    def route_packet(self, packet: RoutingPacket) -> RoutingMetrics:
        """Route one generated packet up the sink tree."""
        self.metrics.generated_packets += 1
        self.metrics.generated_payload_bits += packet.payload_bits
        current_packet = replace(
            packet,
            destination_id=self.sink_id,
            current_node_id=packet.source_id,
            previous_node_id=None,
            hop_count=0,
        )

        while True:
            decision = self.decide(current_packet)
            if decision.action == RoutingAction.DELIVER:
                self._record_delivery(current_packet)
                return self.metrics
            if decision.action == RoutingAction.DROP:
                self.metrics.record_drop(decision.reason)
                return self.metrics

            next_hop_id = decision.next_hop_id
            if next_hop_id is None:
                self.metrics.record_drop("missing_next_hop")
                return self.metrics

            self.metrics.control_overhead_packets += 1
            self._charge_tx(current_packet.payload_bits)
            if not self._link_delivers(
                current_packet.current_node_id,
                next_hop_id,
                current_packet.payload_bits,
            ):
                self.metrics.record_drop("link_failure")
                return self.metrics

            self._charge_rx(current_packet.payload_bits)
            current_packet = replace(
                current_packet,
                current_node_id=next_hop_id,
                previous_node_id=current_packet.current_node_id,
                ttl=current_packet.ttl - 1,
                hop_count=current_packet.hop_count + 1,
            )

    def decide(self, packet: RoutingPacket) -> RouteDecision:
        """Return the sink-tree decision for a packet at its current node."""
        if packet.current_node_id == self.sink_id:
            return RouteDecision(RoutingAction.DELIVER, "reached_sink")
        if packet.ttl <= 0:
            return RouteDecision(RoutingAction.DROP, "ttl_expired")
        if packet.current_node_id not in self.parent_map:
            return RouteDecision(RoutingAction.DROP, "unreachable_to_sink")

        parent_id = self.parent_map[packet.current_node_id]
        if parent_id is None:
            return RouteDecision(RoutingAction.DROP, "missing_parent")
        return RouteDecision(RoutingAction.FORWARD, "parent", (parent_id,))

    def _build_hop_distance_map(self) -> dict[int, int]:
        """Return shortest-hop distance to the sink for reachable nodes."""
        distances = {self.sink_id: 0}
        queue: deque[int] = deque([self.sink_id])
        while queue:
            node_id = queue.popleft()
            for neighbor_id in sorted(self.topology.neighbors(node_id)):
                if neighbor_id in distances:
                    continue
                distances[neighbor_id] = distances[node_id] + 1
                queue.append(neighbor_id)
        return distances

    def _record_delivery(self, packet: RoutingPacket) -> None:
        """Record a sink delivery."""
        self.metrics.delivered_packets += 1
        self.metrics.total_hops += packet.hop_count
        self.metrics.total_latency_s += packet.hop_count * self.config.hop_delay_s
        self.metrics.delivered_payload_bits += packet.payload_bits

    def _link_delivers(
        self,
        source_id: int,
        target_id: int,
        payload_bits: int,
    ) -> bool:
        """Return whether a one-hop transmission succeeds."""
        if not self.config.use_link_success:
            return True
        if self.channel is None:
            raise ValueError("channel is required when use_link_success=True")

        distance_m = self.topology.distance_between(source_id, target_id)
        packet_size_bytes = max(1, (payload_bits + 7) // 8)
        stats = self.channel.calculate_link_stats(
            distance_m,
            packet_size_bytes,
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

    def _charge_tx(self, payload_bits: int) -> None:
        """Add one packet transmission energy."""
        self.metrics.total_energy_j += (
            payload_bits * self.config.tx_energy_per_bit_j
        )

    def _charge_rx(self, payload_bits: int) -> None:
        """Add one packet reception energy."""
        self.metrics.total_energy_j += (
            payload_bits * self.config.rx_energy_per_bit_j
        )


def _resolve_sink_id(topology: Topology, sink_id: int | None) -> int:
    """Resolve and validate the sink id used by a routing protocol."""
    resolved_sink_id = topology.sink_id if sink_id is None else sink_id
    if resolved_sink_id is None:
        raise ValueError("sink_id is required")
    if resolved_sink_id not in topology.nodes:
        raise ValueError("sink_id must refer to an existing node")
    return resolved_sink_id
