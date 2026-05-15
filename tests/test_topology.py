"""Tests for Week 5 topology generation and connectivity graphs."""

import pytest

from wsnsim.models.channel import ChannelConfig, LogDistanceChannel
from wsnsim.models.topology import Node, Topology, TopologyConfig


def coordinates(topology: Topology) -> list[tuple[int, float, float, str]]:
    """Return stable coordinates for reproducibility assertions."""
    return [
        (node.id, node.x_m, node.y_m, node.role)
        for node in topology.node_list()
    ]


def test_random_uniform_deployment_is_reproducible_with_fixed_seed():
    config = TopologyConfig(
        node_count=6,
        area_width_m=100.0,
        area_height_m=50.0,
        seed=123,
        sink_position="center",
    )

    first = Topology.random_uniform(config)
    second = Topology.random_uniform(config)

    assert coordinates(first) == coordinates(second)
    assert first.sink_id == 0
    assert first.nodes[0].role == "sink"


def test_random_uniform_coordinates_are_inside_area():
    config = TopologyConfig(
        node_count=20,
        area_width_m=80.0,
        area_height_m=40.0,
        seed=77,
        sink_position="random",
    )

    topology = Topology.random_uniform(config)

    for node in topology.node_list():
        assert 0.0 <= node.x_m <= config.area_width_m
        assert 0.0 <= node.y_m <= config.area_height_m


def test_grid_deployment_creates_expected_coordinates_without_sink():
    config = TopologyConfig(
        node_count=4,
        area_width_m=10.0,
        area_height_m=20.0,
        sink_position="none",
    )

    topology = Topology.grid(config)

    assert coordinates(topology) == [
        (0, 0.0, 0.0, "sensor"),
        (1, 10.0, 0.0, "sensor"),
        (2, 0.0, 20.0, "sensor"),
        (3, 10.0, 20.0, "sensor"),
    ]
    assert topology.sink_id is None


def test_distance_calculation_uses_euclidean_3_4_5_triangle():
    topology = Topology(
        [
            Node(id=0, x_m=0.0, y_m=0.0, role="sink"),
            Node(id=1, x_m=3.0, y_m=4.0),
        ],
        sink_id=0,
    )

    assert topology.distance_between(0, 1) == pytest.approx(5.0)


def test_distance_graph_connects_nodes_within_range_only():
    topology = Topology(
        [
            Node(id=0, x_m=0.0, y_m=0.0, role="sink"),
            Node(id=1, x_m=3.0, y_m=4.0),
            Node(id=2, x_m=10.0, y_m=0.0),
        ],
        sink_id=0,
    )

    graph = topology.build_distance_graph(communication_range_m=5.0)

    assert graph[0] == {1}
    assert graph[1] == {0}
    assert graph[2] == set()
    assert topology.average_degree() == pytest.approx(2 / 3)
    assert topology.connected_components() == [{0, 1}, {2}]


def test_connectivity_to_sink_for_known_connected_and_disconnected_cases():
    topology = Topology(
        [
            Node(id=0, x_m=0.0, y_m=0.0, role="sink"),
            Node(id=1, x_m=3.0, y_m=0.0),
            Node(id=2, x_m=6.0, y_m=0.0),
        ],
        sink_id=0,
    )

    topology.build_distance_graph(communication_range_m=3.1)
    assert topology.all_nodes_can_reach_sink()
    assert topology.sink_reachability_ratio() == pytest.approx(1.0)

    topology.build_distance_graph(communication_range_m=2.9)
    assert not topology.all_nodes_can_reach_sink()
    assert topology.sink_reachability_ratio() == pytest.approx(1 / 3)


def test_prr_threshold_graph_uses_channel_prr_by_distance():
    topology = Topology(
        [
            Node(id=0, x_m=0.0, y_m=0.0, role="sink"),
            Node(id=1, x_m=10.0, y_m=0.0),
            Node(id=2, x_m=120.0, y_m=0.0),
        ],
        sink_id=0,
    )
    channel = LogDistanceChannel(
        ChannelConfig(shadowing_sigma_db=0.0, seed=5)
    )

    graph = topology.build_prr_graph(
        channel,
        prr_threshold=0.9,
        packet_size_bytes=64,
        include_shadowing=False,
    )

    assert 1 in graph[0]
    assert 2 not in graph[0]
