"""Tests for Week 9 data aggregation and compression."""

import pytest

from wsnsim.models.aggregation import (
    AggregationConfig,
    SensorReading,
    aggregate_values,
    calculate_error,
    communication_metrics,
    delta_suppression,
    generate_synthetic_readings,
    raw_forwarding,
    tree_aggregation,
)
from wsnsim.models.topology import Node, Topology


def readings(values: list[float]) -> list[SensorReading]:
    """Create one timestamp of deterministic readings."""
    return [
        SensorReading(node_id=node_id + 1, timestamp_s=0.0, value=value)
        for node_id, value in enumerate(values)
    ]


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


def test_average_aggregation_gives_correct_value_on_known_inputs():
    assert aggregate_values([1.0, 2.0, 3.0], "average") == pytest.approx(2.0)


def test_min_aggregation_gives_correct_value():
    assert aggregate_values([4.0, -1.0, 7.0], "min") == pytest.approx(-1.0)


def test_max_aggregation_gives_correct_value():
    assert aggregate_values([4.0, -1.0, 7.0], "max") == pytest.approx(7.0)


def test_raw_forwarding_transmits_one_reading_per_node_without_topology():
    result = raw_forwarding(readings([10.0, 11.0, 12.0]))

    assert result.transmitted_packets == 3
    assert result.aggregate_value == pytest.approx(11.0)


def test_tree_aggregation_reduces_packets_and_bytes_compared_with_raw_forwarding():
    config = AggregationConfig(packet_overhead_bytes=4, reading_payload_bytes=8)
    samples = readings([10.0, 11.0, 12.0])
    topology = line_topology()

    raw = raw_forwarding(samples, config, topology=topology)
    tree = tree_aggregation(samples, config, topology=topology)

    assert raw.transmitted_packets == 6
    assert tree.transmitted_packets == 3
    assert tree.transmitted_packets < raw.transmitted_packets
    assert tree.transmitted_bytes < raw.transmitted_bytes


def test_delta_coding_suppresses_unchanged_and_small_change_values():
    config = AggregationConfig(delta_threshold=0.5, packet_overhead_bytes=0)
    samples = [
        SensorReading(node_id=1, timestamp_s=0.0, value=10.0),
        SensorReading(node_id=1, timestamp_s=1.0, value=10.1),
        SensorReading(node_id=1, timestamp_s=2.0, value=10.4),
    ]

    result = delta_suppression(samples, config)

    assert result.transmitted_packets == 1
    assert result.transmitted_bytes == config.raw_packet_bytes


def test_delta_coding_transmits_large_changes():
    config = AggregationConfig(delta_threshold=0.5)
    samples = [
        SensorReading(node_id=1, timestamp_s=0.0, value=10.0),
        SensorReading(node_id=1, timestamp_s=1.0, value=10.6),
    ]

    result = delta_suppression(samples, config)

    assert result.transmitted_packets == 2


def test_mse_calculation_is_correct_on_known_small_example():
    mse, mae = calculate_error([1.0, 2.0], [1.0, 4.0])

    assert mse == pytest.approx(2.0)
    assert mae == pytest.approx(1.0)


def test_compression_ratio_and_communication_saving_formula_are_correct():
    compression_ratio, saving_ratio = communication_metrics(
        transmitted_bytes=20,
        raw_reference_bytes=40,
    )

    assert compression_ratio == pytest.approx(2.0)
    assert saving_ratio == pytest.approx(0.5)


def test_delta_result_uses_expected_compression_formula():
    config = AggregationConfig(
        delta_threshold=1.0,
        packet_overhead_bytes=0,
        reading_payload_bytes=10,
    )
    samples = [
        SensorReading(node_id=1, timestamp_s=0.0, value=1.0),
        SensorReading(node_id=2, timestamp_s=0.0, value=5.0),
        SensorReading(node_id=1, timestamp_s=1.0, value=1.2),
        SensorReading(node_id=2, timestamp_s=1.0, value=5.3),
    ]

    result = delta_suppression(samples, config)

    assert result.transmitted_bytes == 20
    assert result.compression_ratio == pytest.approx(2.0)
    assert result.communication_saving_ratio == pytest.approx(0.5)


def test_deterministic_behavior_with_fixed_seed_for_synthetic_readings():
    first = generate_synthetic_readings(
        [3, 1, 2],
        [2.0, 0.0, 1.0],
        seed=42069,
        noise_std=0.1,
    )
    second = generate_synthetic_readings(
        [3, 1, 2],
        [2.0, 0.0, 1.0],
        seed=42069,
        noise_std=0.1,
    )

    assert first == second
