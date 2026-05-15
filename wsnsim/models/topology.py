"""Topology generation and connectivity graph helpers for WSN deployments."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import ceil, hypot, sqrt
from typing import Literal

import numpy as np


SinkPosition = Literal["center", "corner", "random", "none"] | tuple[float, float]


@dataclass(frozen=True)
class Node:
    """One deployed WSN node.

    Attributes:
        id: Stable integer node identifier.
        x_m: X coordinate in meters.
        y_m: Y coordinate in meters.
        role: Node role, for example ``"sensor"`` or ``"sink"``.
    """

    id: int
    x_m: float
    y_m: float
    role: str = "sensor"


@dataclass(frozen=True)
class TopologyConfig:
    """Configuration for deterministic topology generation.

    ``node_count`` is the total number of nodes. When ``sink_position`` is not
    ``"none"``, node ``0`` is reserved as the sink and remaining nodes are
    deployed as sensors.
    """

    node_count: int
    area_width_m: float
    area_height_m: float
    seed: int | None = 42
    sink_position: SinkPosition = "center"
    communication_range_m: float | None = None
    prr_threshold: float | None = None

    def __post_init__(self) -> None:
        """Validate topology generation parameters."""
        if self.node_count <= 0:
            raise ValueError("node_count must be positive")
        if self.area_width_m <= 0.0:
            raise ValueError("area_width_m must be positive")
        if self.area_height_m <= 0.0:
            raise ValueError("area_height_m must be positive")
        if (
            self.communication_range_m is not None
            and self.communication_range_m < 0.0
        ):
            raise ValueError("communication_range_m must be non-negative")
        if self.prr_threshold is not None and not 0.0 <= self.prr_threshold <= 1.0:
            raise ValueError("prr_threshold must be in [0, 1]")


class Topology:
    """Node deployment and undirected neighbor graph for a WSN scenario."""

    def __init__(
        self,
        nodes: list[Node] | dict[int, Node],
        *,
        sink_id: int | None = None,
        config: TopologyConfig | None = None,
    ) -> None:
        """Create a topology from nodes and optional sink/config metadata."""
        if isinstance(nodes, dict):
            node_map = dict(nodes)
        else:
            node_map = {node.id: node for node in nodes}

        if len(node_map) != len(nodes):
            raise ValueError("node ids must be unique")
        if sink_id is not None and sink_id not in node_map:
            raise ValueError("sink_id must refer to an existing node")

        self.nodes: dict[int, Node] = node_map
        self.sink_id = sink_id
        self.config = config
        self._neighbors: dict[int, set[int]] = {
            node_id: set() for node_id in self.nodes
        }

    @classmethod
    def random_uniform(cls, config: TopologyConfig) -> "Topology":
        """Generate a uniformly random deployment using ``config.seed``."""
        rng = np.random.default_rng(config.seed)
        nodes: list[Node] = []
        sink_id = _append_sink_node(nodes, config, rng)

        for node_id in range(len(nodes), config.node_count):
            nodes.append(
                Node(
                    id=node_id,
                    x_m=float(rng.uniform(0.0, config.area_width_m)),
                    y_m=float(rng.uniform(0.0, config.area_height_m)),
                )
            )

        return cls(nodes, sink_id=sink_id, config=config)

    @classmethod
    def grid(cls, config: TopologyConfig) -> "Topology":
        """Generate a deterministic row-major grid deployment."""
        rng = np.random.default_rng(config.seed)
        nodes: list[Node] = []
        sink_id = _append_sink_node(nodes, config, rng)
        sensor_count = config.node_count - len(nodes)
        first_sensor_id = len(nodes)

        for offset, (x_m, y_m) in enumerate(
            _grid_coordinates(
                sensor_count,
                config.area_width_m,
                config.area_height_m,
            )
        ):
            nodes.append(
                Node(
                    id=first_sensor_id + offset,
                    x_m=x_m,
                    y_m=y_m,
                )
            )

        return cls(nodes, sink_id=sink_id, config=config)

    @classmethod
    def clustered(
        cls,
        config: TopologyConfig,
        *,
        cluster_count: int = 3,
        cluster_std_m: float | None = None,
    ) -> "Topology":
        """Generate sensors around random cluster centers.

        Coordinates are clipped to the configured deployment area.
        """
        if cluster_count <= 0:
            raise ValueError("cluster_count must be positive")
        if cluster_std_m is not None and cluster_std_m < 0.0:
            raise ValueError("cluster_std_m must be non-negative")

        rng = np.random.default_rng(config.seed)
        nodes: list[Node] = []
        sink_id = _append_sink_node(nodes, config, rng)
        sensor_count = config.node_count - len(nodes)
        spread_m = (
            cluster_std_m
            if cluster_std_m is not None
            else min(config.area_width_m, config.area_height_m) / 10.0
        )
        centers = np.column_stack(
            (
                rng.uniform(0.0, config.area_width_m, cluster_count),
                rng.uniform(0.0, config.area_height_m, cluster_count),
            )
        )

        for _ in range(sensor_count):
            center = centers[int(rng.integers(0, cluster_count))]
            x_m = float(
                np.clip(rng.normal(center[0], spread_m), 0.0, config.area_width_m)
            )
            y_m = float(
                np.clip(rng.normal(center[1], spread_m), 0.0, config.area_height_m)
            )
            nodes.append(Node(id=len(nodes), x_m=x_m, y_m=y_m))

        return cls(nodes, sink_id=sink_id, config=config)

    def node_list(self) -> list[Node]:
        """Return nodes sorted by node id."""
        return [self.nodes[node_id] for node_id in sorted(self.nodes)]

    def distance_between(self, source_id: int, target_id: int) -> float:
        """Return Euclidean distance between two nodes, in meters."""
        return self.distance(self.nodes[source_id], self.nodes[target_id])

    @staticmethod
    def distance(source: Node, target: Node) -> float:
        """Return Euclidean distance between two node objects, in meters."""
        return hypot(source.x_m - target.x_m, source.y_m - target.y_m)

    def build_distance_graph(
        self,
        communication_range_m: float | None = None,
    ) -> dict[int, set[int]]:
        """Build an undirected graph from a communication range threshold."""
        range_m = self._resolve_communication_range(communication_range_m)
        adjacency = {node_id: set() for node_id in self.nodes}

        node_ids = sorted(self.nodes)
        for index, source_id in enumerate(node_ids):
            for target_id in node_ids[index + 1 :]:
                if self.distance_between(source_id, target_id) <= range_m:
                    adjacency[source_id].add(target_id)
                    adjacency[target_id].add(source_id)

        self._neighbors = adjacency
        return self.adjacency()

    def build_prr_graph(
        self,
        channel: object,
        *,
        prr_threshold: float | None = None,
        packet_size_bytes: int = 64,
        prr_metric: Literal["logistic", "ber"] = "logistic",
        include_shadowing: bool = False,
    ) -> dict[int, set[int]]:
        """Build an undirected graph by thresholding channel PRR by distance."""
        if prr_metric not in ("logistic", "ber"):
            raise ValueError("prr_metric must be 'logistic' or 'ber'")

        threshold = self._resolve_prr_threshold(prr_threshold)
        adjacency = {node_id: set() for node_id in self.nodes}

        node_ids = sorted(self.nodes)
        for index, source_id in enumerate(node_ids):
            for target_id in node_ids[index + 1 :]:
                distance_m = self.distance_between(source_id, target_id)
                stats = channel.calculate_link_stats(
                    distance_m,
                    packet_size_bytes,
                    include_shadowing=include_shadowing,
                )
                prr = (
                    stats.prr_logistic
                    if prr_metric == "logistic"
                    else stats.prr_ber
                )
                if prr >= threshold:
                    adjacency[source_id].add(target_id)
                    adjacency[target_id].add(source_id)

        self._neighbors = adjacency
        return self.adjacency()

    def adjacency(self) -> dict[int, set[int]]:
        """Return a copy of the current adjacency map."""
        return {
            node_id: set(neighbors)
            for node_id, neighbors in self._neighbors.items()
        }

    def neighbors(self, node_id: int) -> set[int]:
        """Return a copy of one node's neighbor set."""
        if node_id not in self.nodes:
            raise KeyError(f"unknown node id: {node_id}")
        return set(self._neighbors[node_id])

    def connected_components(self) -> list[set[int]]:
        """Return connected components of the current neighbor graph."""
        unseen = set(self.nodes)
        components: list[set[int]] = []

        while unseen:
            start_id = min(unseen)
            component = self._reachable_from(start_id)
            components.append(component)
            unseen -= component

        return components

    def all_nodes_can_reach_sink(self, sink_id: int | None = None) -> bool:
        """Return True when every node is connected to the sink component."""
        resolved_sink_id = self.sink_id if sink_id is None else sink_id
        if resolved_sink_id is None or resolved_sink_id not in self.nodes:
            return False
        return self._reachable_from(resolved_sink_id) == set(self.nodes)

    def sink_reachability_ratio(self, sink_id: int | None = None) -> float:
        """Return the fraction of nodes in the sink's connected component."""
        resolved_sink_id = self.sink_id if sink_id is None else sink_id
        if resolved_sink_id is None or resolved_sink_id not in self.nodes:
            return 0.0
        if not self.nodes:
            return 0.0
        return len(self._reachable_from(resolved_sink_id)) / len(self.nodes)

    def average_degree(self) -> float:
        """Return the mean undirected graph degree."""
        if not self.nodes:
            return 0.0
        return sum(len(neighbors) for neighbors in self._neighbors.values()) / len(
            self.nodes
        )

    def _reachable_from(self, start_id: int) -> set[int]:
        """Return node ids reachable from ``start_id`` in the current graph."""
        visited = {start_id}
        queue: deque[int] = deque([start_id])

        while queue:
            node_id = queue.popleft()
            for neighbor_id in self._neighbors[node_id]:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append(neighbor_id)

        return visited

    def _resolve_communication_range(
        self,
        communication_range_m: float | None,
    ) -> float:
        """Resolve and validate the range threshold for distance graphs."""
        range_m = (
            communication_range_m
            if communication_range_m is not None
            else self.config.communication_range_m if self.config is not None else None
        )
        if range_m is None:
            raise ValueError("communication_range_m is required")
        if range_m < 0.0:
            raise ValueError("communication_range_m must be non-negative")
        return range_m

    def _resolve_prr_threshold(self, prr_threshold: float | None) -> float:
        """Resolve and validate the PRR threshold for PRR graphs."""
        threshold = (
            prr_threshold
            if prr_threshold is not None
            else self.config.prr_threshold if self.config is not None else None
        )
        if threshold is None:
            raise ValueError("prr_threshold is required")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("prr_threshold must be in [0, 1]")
        return threshold


def _append_sink_node(
    nodes: list[Node],
    config: TopologyConfig,
    rng: np.random.Generator,
) -> int | None:
    """Append the configured sink node and return its id, if enabled."""
    if config.sink_position == "none":
        return None

    x_m, y_m = _sink_coordinates(config, rng)
    nodes.append(Node(id=0, x_m=x_m, y_m=y_m, role="sink"))
    return 0


def _sink_coordinates(
    config: TopologyConfig,
    rng: np.random.Generator,
) -> tuple[float, float]:
    """Return sink coordinates according to the configured placement option."""
    if config.sink_position == "center":
        return config.area_width_m / 2.0, config.area_height_m / 2.0
    if config.sink_position == "corner":
        return 0.0, 0.0
    if config.sink_position == "random":
        return (
            float(rng.uniform(0.0, config.area_width_m)),
            float(rng.uniform(0.0, config.area_height_m)),
        )
    if isinstance(config.sink_position, tuple):
        x_m, y_m = config.sink_position
        if not 0.0 <= x_m <= config.area_width_m:
            raise ValueError("sink x coordinate must be inside the deployment area")
        if not 0.0 <= y_m <= config.area_height_m:
            raise ValueError("sink y coordinate must be inside the deployment area")
        return float(x_m), float(y_m)
    raise ValueError(
        "sink_position must be 'center', 'corner', 'random', 'none', or a tuple"
    )


def _grid_coordinates(
    count: int,
    area_width_m: float,
    area_height_m: float,
) -> list[tuple[float, float]]:
    """Return up to ``count`` row-major grid coordinates."""
    if count <= 0:
        return []

    cols = ceil(sqrt(count))
    rows = ceil(count / cols)
    x_values = _axis_grid_values(cols, area_width_m)
    y_values = _axis_grid_values(rows, area_height_m)

    coordinates: list[tuple[float, float]] = []
    for y_m in y_values:
        for x_m in x_values:
            coordinates.append((x_m, y_m))
            if len(coordinates) == count:
                return coordinates

    return coordinates


def _axis_grid_values(count: int, length_m: float) -> list[float]:
    """Return deterministic coordinates along one axis."""
    if count == 1:
        return [length_m / 2.0]
    return [float(value) for value in np.linspace(0.0, length_m, count)]
