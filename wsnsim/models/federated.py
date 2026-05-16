"""Week 12 federated learning communication-cost model for WSNs.

The implementation is intentionally lightweight. It models local node updates
as movement of a small numeric model vector toward deterministic synthetic
local statistics, then aggregates participating node models with FedAvg. The
main purpose is communication accounting rather than ML accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class FederatedConfig:
    """Configuration for a deterministic toy FedAvg simulation."""

    seed: int = 42069
    n_nodes: int = 25
    model_size_params: int = 8
    rounds: int = 20
    local_steps: int = 1
    update_period: int = 1
    participation_rate: float = 1.0
    learning_rate: float = 0.35
    bytes_per_param: int = 4
    message_overhead_bytes: int = 16
    samples_per_node: int = 200
    raw_sample_bytes: int = 16
    target_mean: float = 1.0
    local_stat_std: float = 0.15

    def __post_init__(self) -> None:
        """Validate FL configuration values."""
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if self.n_nodes <= 0:
            raise ValueError("n_nodes must be positive")
        if self.model_size_params <= 0:
            raise ValueError("model_size_params must be positive")
        if self.rounds <= 0:
            raise ValueError("rounds must be positive")
        if self.local_steps <= 0:
            raise ValueError("local_steps must be positive")
        if self.update_period <= 0:
            raise ValueError("update_period must be positive")
        if self.participation_rate <= 0.0 or self.participation_rate > 1.0:
            raise ValueError("participation_rate must be in (0, 1]")
        if self.learning_rate <= 0.0 or self.learning_rate > 1.0:
            raise ValueError("learning_rate must be in (0, 1]")
        if self.bytes_per_param <= 0:
            raise ValueError("bytes_per_param must be positive")
        if self.message_overhead_bytes < 0:
            raise ValueError("message_overhead_bytes must be non-negative")
        if self.samples_per_node <= 0:
            raise ValueError("samples_per_node must be positive")
        if self.raw_sample_bytes <= 0:
            raise ValueError("raw_sample_bytes must be positive")
        if self.local_stat_std < 0.0:
            raise ValueError("local_stat_std must be non-negative")

    @property
    def participating_nodes_per_round(self) -> int:
        """Return the deterministic number of clients selected per FL round."""
        return max(1, int(round(self.n_nodes * self.participation_rate)))

    @property
    def active_rounds(self) -> int:
        """Return the number of rounds that trigger communication."""
        return sum(
            1
            for round_index in range(self.rounds)
            if round_index % self.update_period == 0
        )

    @property
    def model_payload_bytes(self) -> int:
        """Return payload bytes for one model vector."""
        return self.model_size_params * self.bytes_per_param

    @property
    def model_message_bytes(self) -> int:
        """Return bytes for one model message including framing overhead."""
        return self.message_overhead_bytes + self.model_payload_bytes


@dataclass(frozen=True)
class FederatedNode:
    """One WSN node with local data statistics and sample weight."""

    node_id: int
    local_target: np.ndarray
    sample_count: int

    def __post_init__(self) -> None:
        """Validate node fields."""
        if self.node_id < 0:
            raise ValueError("node_id must be non-negative")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if self.local_target.ndim != 1:
            raise ValueError("local_target must be a 1D vector")

    def local_update(
        self,
        global_model: np.ndarray,
        *,
        local_steps: int,
        learning_rate: float,
    ) -> np.ndarray:
        """Move a copy of the global model toward this node's local target."""
        if global_model.shape != self.local_target.shape:
            raise ValueError("global_model shape must match local_target")
        if local_steps <= 0:
            raise ValueError("local_steps must be positive")
        if learning_rate <= 0.0 or learning_rate > 1.0:
            raise ValueError("learning_rate must be in (0, 1]")

        model = np.array(global_model, dtype=float, copy=True)
        for _ in range(local_steps):
            model += learning_rate * (self.local_target - model)
        return model


@dataclass(frozen=True)
class FederatedRoundMetrics:
    """Communication and quality metrics for one FL round."""

    round_index: int
    participating_nodes: int
    fl_upload_bytes: int
    fl_download_bytes: int
    fl_total_bytes: int
    cumulative_fl_bytes: int
    distance_to_target: float
    proxy_loss: float
    proxy_accuracy: float


@dataclass(frozen=True)
class FederatedSimulationResult:
    """Complete output from a deterministic FL run."""

    config: FederatedConfig
    global_model: np.ndarray
    target_model: np.ndarray
    centralized_total_bytes: int
    total_fl_upload_bytes: int
    total_fl_download_bytes: int
    total_fl_bytes: int
    communication_saving_ratio: float
    distance_to_target: float
    proxy_loss: float
    proxy_accuracy: float
    round_metrics: tuple[FederatedRoundMetrics, ...]


class FederatedServer:
    """Server-side global model and FedAvg aggregation state."""

    def __init__(self, initial_model: Sequence[float]) -> None:
        """Initialize the server with a numeric global model vector."""
        model = np.asarray(initial_model, dtype=float)
        if model.ndim != 1 or model.size == 0:
            raise ValueError("initial_model must be a non-empty 1D vector")
        self.global_model = model.copy()

    def aggregate(
        self,
        node_models: Sequence[Sequence[float] | np.ndarray],
        weights: Sequence[float] | None = None,
    ) -> np.ndarray:
        """Apply FedAvg and store the new global model."""
        self.global_model = fedavg(node_models, weights)
        return self.global_model.copy()


def fedavg(
    models: Sequence[Sequence[float] | np.ndarray],
    weights: Sequence[float] | None = None,
) -> np.ndarray:
    """Return the FedAvg weighted or unweighted average of model vectors."""
    if len(models) == 0:
        raise ValueError("models must not be empty")

    array = np.asarray(models, dtype=float)
    if array.ndim != 2:
        raise ValueError("models must be a sequence of equally sized 1D vectors")

    if weights is None:
        return np.mean(array, axis=0)

    weight_array = np.asarray(weights, dtype=float)
    if weight_array.ndim != 1 or weight_array.size != array.shape[0]:
        raise ValueError("weights length must match number of models")
    if np.any(weight_array < 0.0):
        raise ValueError("weights must be non-negative")
    total_weight = float(np.sum(weight_array))
    if total_weight <= 0.0:
        raise ValueError("weights must sum to a positive value")

    return np.average(array, axis=0, weights=weight_array)


def estimate_fl_comm_bytes(
    *,
    n_nodes: int,
    model_size_params: int,
    rounds: int,
    bytes_per_param: int = 4,
    message_overhead_bytes: int = 16,
    include_download: bool = True,
) -> tuple[int, int, int]:
    """Return upload, download, and total bytes for FL model exchange."""
    _validate_comm_inputs(
        n_nodes=n_nodes,
        model_size_params=model_size_params,
        rounds=rounds,
        bytes_per_param=bytes_per_param,
        message_overhead_bytes=message_overhead_bytes,
    )
    message_bytes = message_overhead_bytes + model_size_params * bytes_per_param
    upload_bytes = n_nodes * rounds * message_bytes
    download_bytes = n_nodes * rounds * message_bytes if include_download else 0
    return upload_bytes, download_bytes, upload_bytes + download_bytes


def estimate_centralized_comm_bytes(
    *,
    n_nodes: int,
    samples_per_node: int,
    raw_sample_bytes: int,
    message_overhead_bytes: int = 16,
) -> int:
    """Return bytes for uploading all raw samples to a central server."""
    if n_nodes <= 0:
        raise ValueError("n_nodes must be positive")
    if samples_per_node <= 0:
        raise ValueError("samples_per_node must be positive")
    if raw_sample_bytes <= 0:
        raise ValueError("raw_sample_bytes must be positive")
    if message_overhead_bytes < 0:
        raise ValueError("message_overhead_bytes must be non-negative")
    return n_nodes * samples_per_node * (raw_sample_bytes + message_overhead_bytes)


def run_federated_simulation(
    config: FederatedConfig,
) -> FederatedSimulationResult:
    """Run deterministic toy FedAvg and return communication metrics."""
    rng = np.random.default_rng(config.seed)
    target_model = np.full(config.model_size_params, config.target_mean, dtype=float)
    nodes = _make_nodes(config, rng, target_model)
    server = FederatedServer(np.zeros(config.model_size_params, dtype=float))

    total_upload = 0
    total_download = 0
    round_metrics: list[FederatedRoundMetrics] = []

    for round_index in range(config.rounds):
        if round_index % config.update_period == 0:
            selected = _select_nodes(nodes, config.participating_nodes_per_round, rng)
            local_models = [
                node.local_update(
                    server.global_model,
                    local_steps=config.local_steps,
                    learning_rate=config.learning_rate,
                )
                for node in selected
            ]
            weights = [node.sample_count for node in selected]
            server.aggregate(local_models, weights)
            upload, download, total = estimate_fl_comm_bytes(
                n_nodes=len(selected),
                model_size_params=config.model_size_params,
                rounds=1,
                bytes_per_param=config.bytes_per_param,
                message_overhead_bytes=config.message_overhead_bytes,
            )
        else:
            selected = []
            upload = download = total = 0

        total_upload += upload
        total_download += download
        distance, loss, accuracy = _quality_metrics(server.global_model, target_model)
        round_metrics.append(
            FederatedRoundMetrics(
                round_index=round_index,
                participating_nodes=len(selected),
                fl_upload_bytes=upload,
                fl_download_bytes=download,
                fl_total_bytes=total,
                cumulative_fl_bytes=total_upload + total_download,
                distance_to_target=distance,
                proxy_loss=loss,
                proxy_accuracy=accuracy,
            )
        )

    centralized_total = estimate_centralized_comm_bytes(
        n_nodes=config.n_nodes,
        samples_per_node=config.samples_per_node,
        raw_sample_bytes=config.raw_sample_bytes,
        message_overhead_bytes=config.message_overhead_bytes,
    )
    total_fl = total_upload + total_download
    saving_ratio = 1.0 - (total_fl / centralized_total)
    distance, loss, accuracy = _quality_metrics(server.global_model, target_model)

    return FederatedSimulationResult(
        config=config,
        global_model=server.global_model.copy(),
        target_model=target_model,
        centralized_total_bytes=centralized_total,
        total_fl_upload_bytes=total_upload,
        total_fl_download_bytes=total_download,
        total_fl_bytes=total_fl,
        communication_saving_ratio=saving_ratio,
        distance_to_target=distance,
        proxy_loss=loss,
        proxy_accuracy=accuracy,
        round_metrics=tuple(round_metrics),
    )


def _make_nodes(
    config: FederatedConfig,
    rng: np.random.Generator,
    target_model: np.ndarray,
) -> list[FederatedNode]:
    """Create deterministic non-IID local targets around the global target."""
    shifts = rng.normal(
        0.0,
        config.local_stat_std,
        size=(config.n_nodes, config.model_size_params),
    )
    sample_counts = np.array(
        [
            max(1, config.samples_per_node + int(rng.integers(-10, 11)))
            for _ in range(config.n_nodes)
        ],
        dtype=float,
    )
    weighted_shift = np.average(shifts, axis=0, weights=sample_counts)
    shifts = shifts - weighted_shift

    nodes: list[FederatedNode] = []
    for node_id in range(config.n_nodes):
        local_target = target_model + shifts[node_id]
        nodes.append(
            FederatedNode(
                node_id=node_id,
                local_target=local_target,
                sample_count=int(sample_counts[node_id]),
            )
        )
    return nodes


def _select_nodes(
    nodes: Sequence[FederatedNode],
    count: int,
    rng: np.random.Generator,
) -> list[FederatedNode]:
    """Select a deterministic seeded subset of nodes without replacement."""
    if count >= len(nodes):
        return list(nodes)
    indexes = rng.choice(len(nodes), size=count, replace=False)
    return [nodes[int(index)] for index in indexes]


def _quality_metrics(
    global_model: np.ndarray,
    target_model: np.ndarray,
) -> tuple[float, float, float]:
    """Return distance, squared-loss proxy, and bounded accuracy proxy."""
    error = global_model - target_model
    distance = float(np.linalg.norm(error))
    loss = float(np.mean(error * error))
    accuracy = float(1.0 / (1.0 + distance))
    return distance, loss, accuracy


def _validate_comm_inputs(
    *,
    n_nodes: int,
    model_size_params: int,
    rounds: int,
    bytes_per_param: int,
    message_overhead_bytes: int,
) -> None:
    """Validate common communication-cost inputs."""
    if n_nodes <= 0:
        raise ValueError("n_nodes must be positive")
    if model_size_params <= 0:
        raise ValueError("model_size_params must be positive")
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if bytes_per_param <= 0:
        raise ValueError("bytes_per_param must be positive")
    if message_overhead_bytes < 0:
        raise ValueError("message_overhead_bytes must be non-negative")
