"""Week 9 in-network aggregation and lightweight compression models.

The aggregation layer is deliberately analytic rather than a full packet-level
routing simulation. When a topology is supplied, communication cost is counted
as link-layer transmissions over the Week 6 BFS sink tree. Without a topology,
one application packet is counted per transmitted reading or aggregate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import inf, sin
from typing import Iterable, Literal, Sequence

import numpy as np

from wsnsim.models.routing import SinkTreeRouting
from wsnsim.models.topology import Topology


AggregationMethod = Literal["average", "min", "max", "sum", "count"]


@dataclass(frozen=True)
class SensorReading:
    """One scalar sensor sample produced by a WSN node."""

    node_id: int
    timestamp_s: float
    value: float
    true_value: float | None = None

    def __post_init__(self) -> None:
        """Validate reading fields."""
        if self.timestamp_s < 0.0:
            raise ValueError("timestamp_s must be non-negative")

    @property
    def ground_truth(self) -> float:
        """Return the physical value used for error calculations."""
        return self.value if self.true_value is None else self.true_value


@dataclass(frozen=True)
class AggregationConfig:
    """Configuration and packet-size assumptions for aggregation experiments."""

    aggregation_method: AggregationMethod = "average"
    delta_threshold: float = 0.25
    quantization_step: float = 0.0
    seed: int | None = 42
    reading_payload_bytes: int = 8
    aggregate_payload_bytes: int = 8
    packet_overhead_bytes: int = 16

    def __post_init__(self) -> None:
        """Validate aggregation parameters."""
        _normalize_method(self.aggregation_method)
        if self.delta_threshold < 0.0:
            raise ValueError("delta_threshold must be non-negative")
        if self.quantization_step < 0.0:
            raise ValueError("quantization_step must be non-negative")
        if self.reading_payload_bytes <= 0:
            raise ValueError("reading_payload_bytes must be positive")
        if self.aggregate_payload_bytes <= 0:
            raise ValueError("aggregate_payload_bytes must be positive")
        if self.packet_overhead_bytes < 0:
            raise ValueError("packet_overhead_bytes must be non-negative")

    @property
    def raw_packet_bytes(self) -> int:
        """Return bytes for one forwarded raw sensor reading."""
        return self.packet_overhead_bytes + self.reading_payload_bytes

    @property
    def aggregate_packet_bytes(self) -> int:
        """Return bytes for one forwarded aggregate packet."""
        return self.packet_overhead_bytes + self.aggregate_payload_bytes


@dataclass(frozen=True)
class AggregationResult:
    """Metrics produced by one aggregation/compression strategy."""

    aggregate_value: float
    transmitted_packets: int
    transmitted_bytes: int
    mse: float
    mae: float
    compression_ratio: float
    communication_saving_ratio: float


def aggregate_values(
    values: Sequence[float],
    method: AggregationMethod = "average",
) -> float:
    """Aggregate scalar values with a supported WSN collection function."""
    if not values:
        raise ValueError("values must not be empty")

    normalized_method = _normalize_method(method)
    if normalized_method == "average":
        return float(sum(values) / len(values))
    if normalized_method == "min":
        return float(min(values))
    if normalized_method == "max":
        return float(max(values))
    if normalized_method == "sum":
        return float(sum(values))
    if normalized_method == "count":
        return float(len(values))
    raise AssertionError("unreachable aggregation method")


def calculate_error(
    estimated_values: Sequence[float],
    true_values: Sequence[float],
) -> tuple[float, float]:
    """Return mean squared error and mean absolute error."""
    if len(estimated_values) != len(true_values):
        raise ValueError("estimated_values and true_values must have equal length")
    if not estimated_values:
        return 0.0, 0.0

    squared_error = 0.0
    absolute_error = 0.0
    for estimated, true in zip(estimated_values, true_values):
        error = estimated - true
        squared_error += error * error
        absolute_error += abs(error)
    count = len(estimated_values)
    return squared_error / count, absolute_error / count


def communication_metrics(
    *,
    transmitted_bytes: int,
    raw_reference_bytes: int,
) -> tuple[float, float]:
    """Return compression ratio and saving ratio versus raw forwarding.

    ``compression_ratio`` is defined as original raw bytes divided by compressed
    bytes, so values above 1.0 indicate fewer transmitted bytes than raw.
    ``communication_saving_ratio`` is ``1 - compressed_bytes / raw_bytes``.
    """
    if raw_reference_bytes < 0:
        raise ValueError("raw_reference_bytes must be non-negative")
    if transmitted_bytes < 0:
        raise ValueError("transmitted_bytes must be non-negative")
    if raw_reference_bytes == 0:
        return 1.0, 0.0
    if transmitted_bytes == 0:
        return inf, 1.0

    compression_ratio = raw_reference_bytes / transmitted_bytes
    saving_ratio = 1.0 - (transmitted_bytes / raw_reference_bytes)
    return compression_ratio, saving_ratio


def raw_forwarding(
    readings: Sequence[SensorReading],
    config: AggregationConfig | None = None,
    *,
    topology: Topology | None = None,
    sink_id: int | None = None,
) -> AggregationResult:
    """Forward every reading to the sink and compute collection metrics."""
    if not readings:
        return _empty_result()

    resolved_config = config if config is not None else AggregationConfig()
    transmitted_packets = _raw_packet_count(readings, topology, sink_id)
    transmitted_bytes = transmitted_packets * resolved_config.raw_packet_bytes
    estimated = _aggregate_series(readings, use_truth=False, config=resolved_config)
    truth = _aggregate_series(readings, use_truth=True, config=resolved_config)
    mse, mae = calculate_error(estimated, truth)
    compression_ratio, saving_ratio = communication_metrics(
        transmitted_bytes=transmitted_bytes,
        raw_reference_bytes=transmitted_bytes,
    )

    return AggregationResult(
        aggregate_value=estimated[-1],
        transmitted_packets=transmitted_packets,
        transmitted_bytes=transmitted_bytes,
        mse=mse,
        mae=mae,
        compression_ratio=compression_ratio,
        communication_saving_ratio=saving_ratio,
    )


def tree_aggregation(
    readings: Sequence[SensorReading],
    config: AggregationConfig | None = None,
    *,
    topology: Topology | None = None,
    sink_id: int | None = None,
) -> AggregationResult:
    """Aggregate readings in-network along a BFS sink tree."""
    if not readings:
        return _empty_result()

    resolved_config = config if config is not None else AggregationConfig()
    if topology is None:
        transmitted_packets = len(_readings_by_timestamp(readings))
    else:
        transmitted_packets = _tree_packet_count(readings, topology, sink_id)
    transmitted_bytes = transmitted_packets * resolved_config.aggregate_packet_bytes

    estimated = _aggregate_series(readings, use_truth=False, config=resolved_config)
    truth = _aggregate_series(readings, use_truth=True, config=resolved_config)
    mse, mae = calculate_error(estimated, truth)
    raw_reference_bytes = (
        _raw_packet_count(readings, topology, sink_id)
        * resolved_config.raw_packet_bytes
    )
    compression_ratio, saving_ratio = communication_metrics(
        transmitted_bytes=transmitted_bytes,
        raw_reference_bytes=raw_reference_bytes,
    )

    return AggregationResult(
        aggregate_value=estimated[-1],
        transmitted_packets=transmitted_packets,
        transmitted_bytes=transmitted_bytes,
        mse=mse,
        mae=mae,
        compression_ratio=compression_ratio,
        communication_saving_ratio=saving_ratio,
    )


def delta_suppression(
    readings: Sequence[SensorReading],
    config: AggregationConfig | None = None,
    *,
    topology: Topology | None = None,
    sink_id: int | None = None,
) -> AggregationResult:
    """Transmit only readings whose change exceeds the configured threshold."""
    if not readings:
        return _empty_result()

    resolved_config = config if config is not None else AggregationConfig()
    ordered_readings = sorted(
        readings,
        key=lambda reading: (reading.timestamp_s, reading.node_id),
    )
    reconstructed_by_node: dict[int, float] = {}
    reconstructed_values: list[float] = []
    true_values: list[float] = []
    transmitted_readings: list[SensorReading] = []

    for reading in ordered_readings:
        quantized_value = _quantize(reading.value, resolved_config.quantization_step)
        previous_value = reconstructed_by_node.get(reading.node_id)
        if (
            previous_value is None
            or abs(quantized_value - previous_value)
            > resolved_config.delta_threshold
        ):
            reconstructed_by_node[reading.node_id] = quantized_value
            transmitted_readings.append(reading)

        reconstructed_values.append(reconstructed_by_node[reading.node_id])
        true_values.append(reading.ground_truth)

    transmitted_packets = _raw_packet_count(transmitted_readings, topology, sink_id)
    transmitted_bytes = transmitted_packets * resolved_config.raw_packet_bytes
    raw_reference_bytes = (
        _raw_packet_count(readings, topology, sink_id)
        * resolved_config.raw_packet_bytes
    )
    mse, mae = calculate_error(reconstructed_values, true_values)
    compression_ratio, saving_ratio = communication_metrics(
        transmitted_bytes=transmitted_bytes,
        raw_reference_bytes=raw_reference_bytes,
    )

    return AggregationResult(
        aggregate_value=aggregate_values(
            reconstructed_values,
            resolved_config.aggregation_method,
        ),
        transmitted_packets=transmitted_packets,
        transmitted_bytes=transmitted_bytes,
        mse=mse,
        mae=mae,
        compression_ratio=compression_ratio,
        communication_saving_ratio=saving_ratio,
    )


def generate_synthetic_readings(
    node_ids: Iterable[int],
    timestamps_s: Iterable[float],
    *,
    seed: int | None = 42,
    base_value: float = 20.0,
    amplitude: float = 2.0,
    period_s: float = 60.0,
    noise_std: float = 0.05,
    anomaly_time_s: float | None = None,
    anomaly_delta: float = 1.5,
) -> list[SensorReading]:
    """Generate reproducible smooth sensor readings with optional change event."""
    if period_s <= 0.0:
        raise ValueError("period_s must be positive")
    if noise_std < 0.0:
        raise ValueError("noise_std must be non-negative")

    rng = np.random.default_rng(seed)
    sorted_node_ids = sorted(node_ids)
    sorted_timestamps = sorted(float(timestamp_s) for timestamp_s in timestamps_s)
    readings: list[SensorReading] = []

    for timestamp_s in sorted_timestamps:
        time_component = amplitude * sin((2.0 * np.pi * timestamp_s) / period_s)
        for node_id in sorted_node_ids:
            spatial_component = 0.015 * node_id
            anomaly_component = (
                anomaly_delta
                if anomaly_time_s is not None
                and timestamp_s >= anomaly_time_s
                and node_id % 7 == 0
                else 0.0
            )
            true_value = base_value + time_component + spatial_component + anomaly_component
            measured_value = true_value + float(rng.normal(0.0, noise_std))
            readings.append(
                SensorReading(
                    node_id=node_id,
                    timestamp_s=timestamp_s,
                    value=measured_value,
                    true_value=true_value,
                )
            )

    return readings


def _aggregate_series(
    readings: Sequence[SensorReading],
    *,
    use_truth: bool,
    config: AggregationConfig,
) -> list[float]:
    """Return one aggregate per timestamp."""
    aggregates: list[float] = []
    grouped_readings = _readings_by_timestamp(readings)
    for timestamp_s in sorted(grouped_readings):
        timestamp_readings = grouped_readings[timestamp_s]
        values = [
            reading.ground_truth
            if use_truth
            else _quantize(reading.value, config.quantization_step)
            for reading in timestamp_readings
        ]
        aggregates.append(aggregate_values(values, config.aggregation_method))
    return aggregates


def _raw_packet_count(
    readings: Sequence[SensorReading],
    topology: Topology | None,
    sink_id: int | None,
) -> int:
    """Count raw-reading link transmissions."""
    if topology is None:
        return len(readings)

    tree = SinkTreeRouting(topology, sink_id=sink_id)
    return sum(
        tree.hop_distance_map.get(reading.node_id, 0)
        for reading in readings
        if reading.node_id != tree.sink_id
    )


def _tree_packet_count(
    readings: Sequence[SensorReading],
    topology: Topology,
    sink_id: int | None,
) -> int:
    """Count one aggregate transmission per active tree edge and timestamp."""
    tree = SinkTreeRouting(topology, sink_id=sink_id)
    total_packets = 0
    for timestamp_readings in _readings_by_timestamp(readings).values():
        active_nodes = {
            reading.node_id
            for reading in timestamp_readings
            if reading.node_id != tree.sink_id
        }
        forwarding_nodes: set[int] = set()
        for node_id in active_nodes:
            current_id = node_id
            while current_id in tree.parent_map and current_id != tree.sink_id:
                forwarding_nodes.add(current_id)
                parent_id = tree.parent_map[current_id]
                if parent_id is None:
                    break
                current_id = parent_id
        total_packets += len(forwarding_nodes)
    return total_packets


def _readings_by_timestamp(
    readings: Sequence[SensorReading],
) -> dict[float, list[SensorReading]]:
    """Group readings by timestamp with deterministic node ordering."""
    grouped: dict[float, list[SensorReading]] = defaultdict(list)
    for reading in readings:
        grouped[reading.timestamp_s].append(reading)
    return {
        timestamp_s: sorted(group, key=lambda reading: reading.node_id)
        for timestamp_s, group in grouped.items()
    }


def _quantize(value: float, step: float) -> float:
    """Quantize a scalar value when a positive step is configured."""
    if step <= 0.0:
        return float(value)
    return float(round(value / step) * step)


def _empty_result() -> AggregationResult:
    """Return a zero-valued aggregation result."""
    return AggregationResult(
        aggregate_value=0.0,
        transmitted_packets=0,
        transmitted_bytes=0,
        mse=0.0,
        mae=0.0,
        compression_ratio=1.0,
        communication_saving_ratio=0.0,
    )


def _normalize_method(method: str) -> AggregationMethod:
    """Validate and return a normalized aggregation method."""
    if method not in ("average", "min", "max", "sum", "count"):
        raise ValueError(
            "aggregation_method must be one of: average, min, max, sum, count"
        )
    return method  # type: ignore[return-value]
