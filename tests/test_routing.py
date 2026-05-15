"""Tests for Week 6 routing and data collection baselines."""

import pytest

from wsnsim.models.routing import (
    FloodingRouting,
    RoutingConfig,
    RoutingPacket,
    SinkTreeRouting,
)
from wsnsim.models.topology import Node, Topology


def make_packet(
    packet_id: int | str = 1,
    *,
    source_id: int = 1,
    sink_id: int = 0,
    ttl: int = 8,
    payload_bits: int = 800,
) -> RoutingPacket:
    """Create a routing packet with the common test defaults."""
    return RoutingPacket(
        packet_id=packet_id,
        source_id=source_id,
        destination_id=sink_id,
        current_node_id=source_id,
        previous_node_id=None,
        created_time_s=0.0,
        ttl=ttl,
        payload_bits=payload_bits,
    )


def line_topology() -> Topology:
    """Return 0--1--2--3 with node 0 as the sink."""
    topology = Topology(
        [
            Node(id=0, x_m=0.0, y_m=0.0, role="sink"),
            Node(id=1, x_m=1.0, y_m=0.0),
            Node(id=2, x_m=2.0, y_m=0.0),
            Node(id=3, x_m=3.0, y_m=0.0),
        ],
        sink_id=0,
    )
    topology.build_distance_graph(communication_range_m=1.1)
    return topology


def diamond_topology() -> Topology:
    """Return a diamond graph where source 3 has two paths to sink 0."""
    topology = Topology(
        [
            Node(id=0, x_m=0.0, y_m=0.0, role="sink"),
            Node(id=1, x_m=1.0, y_m=0.0),
            Node(id=2, x_m=0.0, y_m=1.0),
            Node(id=3, x_m=1.0, y_m=1.0),
        ],
        sink_id=0,
    )
    topology.build_distance_graph(communication_range_m=1.1)
    return topology


def test_flooding_with_ttl_does_not_loop_forever():
    routing = FloodingRouting(diamond_topology())

    metrics = routing.route_packet(make_packet(source_id=3, ttl=2))

    assert metrics.generated_packets == 1
    assert metrics.delivered_packets == 1
    assert metrics.control_overhead_packets <= 4
    assert len(routing.seen_cache) <= 4


def test_flooding_seen_cache_suppresses_duplicates():
    routing = FloodingRouting(diamond_topology())

    metrics = routing.route_packet(make_packet(source_id=3, ttl=4))

    assert metrics.delivered_packets == 1
    assert metrics.duplicate_packets >= 1
    assert metrics.drop_reasons["duplicate"] >= 1


def test_flooding_delivers_to_sink_in_connected_graph():
    routing = FloodingRouting(line_topology())

    metrics = routing.route_packet(make_packet(source_id=3, ttl=4))

    assert metrics.pdr == pytest.approx(1.0)
    assert metrics.delivered_packets == 1
    assert metrics.average_hop_count == pytest.approx(3.0)


def test_sink_tree_builds_correct_parent_map_on_simple_topology():
    routing = SinkTreeRouting(line_topology())

    assert routing.parent_map == {0: None, 1: 0, 2: 1, 3: 2}
    assert routing.hop_distance_map[3] == 3


def test_sink_tree_drops_packets_from_unreachable_nodes():
    topology = Topology(
        [
            Node(id=0, x_m=0.0, y_m=0.0, role="sink"),
            Node(id=1, x_m=1.0, y_m=0.0),
            Node(id=2, x_m=10.0, y_m=0.0),
        ],
        sink_id=0,
    )
    topology.build_distance_graph(communication_range_m=1.1)
    routing = SinkTreeRouting(topology)

    metrics = routing.route_packet(make_packet(source_id=2, ttl=4))

    assert metrics.delivered_packets == 0
    assert metrics.dropped_packets == 1
    assert metrics.drop_reasons == {"unreachable_to_sink": 1}


def test_sink_tree_path_has_expected_hop_count():
    routing = SinkTreeRouting(line_topology())

    metrics = routing.route_packet(make_packet(source_id=3, ttl=4))

    assert metrics.delivered_packets == 1
    assert metrics.total_hops == 3
    assert metrics.average_latency_s == pytest.approx(0.03)


def test_routing_behavior_is_deterministic_with_fixed_seed_and_config():
    config = RoutingConfig(seed=123, hop_delay_s=0.02)

    first = FloodingRouting(diamond_topology(), config=config)
    second = FloodingRouting(diamond_topology(), config=config)
    for packet_id in range(3):
        first.route_packet(make_packet(packet_id, source_id=3, ttl=4))
        second.route_packet(make_packet(packet_id, source_id=3, ttl=4))

    assert first.metrics == second.metrics
    assert first.seen_cache == second.seen_cache


def test_metrics_calculation_sanity_for_pdr_hops_and_energy():
    config = RoutingConfig(
        hop_delay_s=0.5,
        tx_energy_per_bit_j=1e-6,
        rx_energy_per_bit_j=2e-6,
    )
    routing = SinkTreeRouting(line_topology(), config=config)

    metrics = routing.route_packet(make_packet(source_id=2, ttl=4, payload_bits=100))

    assert metrics.generated_packets == 1
    assert metrics.delivered_packets == 1
    assert metrics.pdr == pytest.approx(1.0)
    assert metrics.total_hops == 2
    assert metrics.average_hop_count == pytest.approx(2.0)
    assert metrics.average_latency_s == pytest.approx(1.0)
    assert metrics.total_energy_j == pytest.approx(2 * 100 * (1e-6 + 2e-6))
    assert metrics.energy_per_delivered_bit_j == pytest.approx(6e-6)
