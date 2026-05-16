"""Week 11 edge anomaly detection for WSN sensor readings.

The model is deliberately small and deterministic: synthetic readings are
generated from a local ``numpy.random.default_rng`` and edge inference is a
streaming per-node detector. Undefined precision/recall-style metrics are
reported as ``0.0`` when their denominator is empty, which keeps experiment
rows numeric and avoids divide-by-zero failures.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import inf, sin
from typing import Deque, Literal, Sequence

import numpy as np


DetectorType = Literal["zscore", "ewma"]


@dataclass(frozen=True)
class SensorSample:
    """One scalar sensor sample with anomaly ground truth."""

    node_id: int
    timestamp_s: float
    value: float
    is_anomaly: bool

    def __post_init__(self) -> None:
        """Validate sample fields."""
        if self.timestamp_s < 0.0:
            raise ValueError("timestamp_s must be non-negative")


@dataclass(frozen=True)
class SignalGeneratorConfig:
    """Configuration for deterministic synthetic WSN sensor signals."""

    seed: int = 42069
    n_nodes: int = 25
    n_timesteps: int = 200
    baseline_mean: float = 20.0
    baseline_std: float = 1.0
    anomaly_probability: float = 0.05
    anomaly_magnitude: float = 3.0

    def __post_init__(self) -> None:
        """Validate signal generation parameters."""
        if self.n_nodes < 0:
            raise ValueError("n_nodes must be non-negative")
        if self.n_timesteps < 0:
            raise ValueError("n_timesteps must be non-negative")
        if self.baseline_std < 0.0:
            raise ValueError("baseline_std must be non-negative")
        if self.anomaly_probability < 0.0 or self.anomaly_probability > 1.0:
            raise ValueError("anomaly_probability must be in [0, 1]")
        if self.anomaly_magnitude < 0.0:
            raise ValueError("anomaly_magnitude must be non-negative")


@dataclass(frozen=True)
class DetectorConfig:
    """Configuration for a streaming edge anomaly detector."""

    detector_type: DetectorType = "zscore"
    threshold: float = 2.5
    window_size: int = 20
    ewma_alpha: float = 0.2

    def __post_init__(self) -> None:
        """Validate detector parameters."""
        if self.detector_type not in ("zscore", "ewma"):
            raise ValueError("detector_type must be 'zscore' or 'ewma'")
        if self.threshold < 0.0:
            raise ValueError("threshold must be non-negative")
        if self.window_size <= 0:
            raise ValueError("window_size must be positive")
        if self.ewma_alpha <= 0.0 or self.ewma_alpha > 1.0:
            raise ValueError("ewma_alpha must be in (0, 1]")


@dataclass(frozen=True)
class DetectionResult:
    """Prediction for one sensor sample."""

    predicted_anomaly: bool
    score: float
    threshold: float
    reason: str


@dataclass(frozen=True)
class EdgeAIMetrics:
    """Detection and communication metrics for edge anomaly reporting."""

    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    false_negative_rate: float
    transmitted_packets: int
    baseline_packets: int
    communication_saving_ratio: float
    energy_saved_j: float | None = None


def generate_sensor_samples(config: SignalGeneratorConfig) -> list[SensorSample]:
    """Generate reproducible smooth sensor samples with injected anomalies.

    The baseline signal combines a slow sinusoid, a small node-specific offset,
    and Gaussian measurement noise. Anomalies are positive spikes of
    ``anomaly_magnitude`` above the local baseline and are labeled in
    ``SensorSample.is_anomaly``. Randomness is local to the configured seed.
    """
    rng = np.random.default_rng(config.seed)
    samples: list[SensorSample] = []
    period_s = max(12.0, config.n_timesteps / 3.0)

    for timestep in range(config.n_timesteps):
        timestamp_s = float(timestep)
        time_component = 0.35 * config.baseline_std * sin(
            (2.0 * np.pi * timestamp_s) / period_s
        )
        for node_id in range(config.n_nodes):
            spatial_component = 0.03 * config.baseline_std * node_id
            baseline = (
                config.baseline_mean
                + time_component
                + spatial_component
            )
            noise = float(rng.normal(0.0, config.baseline_std))
            is_anomaly = bool(rng.random() < config.anomaly_probability)
            anomaly_component = (
                config.anomaly_magnitude if is_anomaly else 0.0
            )
            samples.append(
                SensorSample(
                    node_id=node_id,
                    timestamp_s=timestamp_s,
                    value=baseline + noise + anomaly_component,
                    is_anomaly=is_anomaly,
                )
            )

    return samples


def detect_sample_zscore(
    sample: SensorSample,
    history: Sequence[float],
    config: DetectorConfig,
) -> DetectionResult:
    """Classify one sample using z-score against prior same-node history."""
    if len(history) < 2:
        return DetectionResult(
            predicted_anomaly=False,
            score=0.0,
            threshold=config.threshold,
            reason="insufficient_history",
        )

    mean = float(np.mean(history))
    std = float(np.std(history))
    if std == 0.0:
        score = inf if sample.value != mean else 0.0
    else:
        score = abs(sample.value - mean) / std

    predicted = bool(score > config.threshold)
    return DetectionResult(
        predicted_anomaly=predicted,
        score=float(score),
        threshold=config.threshold,
        reason="zscore_threshold" if predicted else "zscore_normal",
    )


def detect_samples(
    samples: Sequence[SensorSample],
    config: DetectorConfig,
) -> list[DetectionResult]:
    """Run a streaming per-node detector over ordered samples."""
    if config.detector_type == "zscore":
        return _detect_samples_zscore(samples, config)
    if config.detector_type == "ewma":
        return _detect_samples_ewma(samples, config)
    raise AssertionError("unreachable detector type")


def calculate_edge_ai_metrics(
    samples: Sequence[SensorSample],
    results: Sequence[DetectionResult],
    *,
    energy_per_packet_j: float | None = None,
) -> EdgeAIMetrics:
    """Return confusion-matrix, detection, and communication metrics.

    Edge mode transmits only samples classified as anomalies. Baseline mode
    transmits every sample. Undefined rates with an empty denominator are
    returned as ``0.0`` to keep experiment output numeric and robust.
    """
    if len(samples) != len(results):
        raise ValueError("samples and results must have equal length")
    if energy_per_packet_j is not None and energy_per_packet_j < 0.0:
        raise ValueError("energy_per_packet_j must be non-negative")

    true_positive = false_positive = true_negative = false_negative = 0
    for sample, result in zip(samples, results):
        if sample.is_anomaly and result.predicted_anomaly:
            true_positive += 1
        elif not sample.is_anomaly and result.predicted_anomaly:
            false_positive += 1
        elif not sample.is_anomaly and not result.predicted_anomaly:
            true_negative += 1
        else:
            false_negative += 1

    transmitted_packets = sum(
        1 for result in results if result.predicted_anomaly
    )
    baseline_packets = len(samples)
    communication_saving_ratio = (
        1.0 - transmitted_packets / baseline_packets
        if baseline_packets
        else 0.0
    )
    energy_saved_j = (
        (baseline_packets - transmitted_packets) * energy_per_packet_j
        if energy_per_packet_j is not None
        else None
    )

    precision = _safe_divide(
        true_positive,
        true_positive + false_positive,
    )
    recall = _safe_divide(true_positive, true_positive + false_negative)
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    false_positive_rate = _safe_divide(
        false_positive,
        false_positive + true_negative,
    )
    false_negative_rate = _safe_divide(
        false_negative,
        false_negative + true_positive,
    )

    return EdgeAIMetrics(
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_rate=false_positive_rate,
        false_negative_rate=false_negative_rate,
        transmitted_packets=transmitted_packets,
        baseline_packets=baseline_packets,
        communication_saving_ratio=communication_saving_ratio,
        energy_saved_j=energy_saved_j,
    )


def _detect_samples_zscore(
    samples: Sequence[SensorSample],
    config: DetectorConfig,
) -> list[DetectionResult]:
    """Detect anomalies with rolling z-scores per node."""
    history_by_node: dict[int, Deque[float]] = defaultdict(
        lambda: deque(maxlen=config.window_size)
    )
    results: list[DetectionResult] = []

    for sample in samples:
        history = history_by_node[sample.node_id]
        result = detect_sample_zscore(sample, list(history), config)
        results.append(result)
        history.append(sample.value)

    return results


def _detect_samples_ewma(
    samples: Sequence[SensorSample],
    config: DetectorConfig,
) -> list[DetectionResult]:
    """Detect anomalies against an EWMA baseline with rolling residual scale."""
    mean_by_node: dict[int, float] = {}
    residuals_by_node: dict[int, Deque[float]] = defaultdict(
        lambda: deque(maxlen=config.window_size)
    )
    results: list[DetectionResult] = []

    for sample in samples:
        previous_mean = mean_by_node.get(sample.node_id)
        if previous_mean is None:
            mean_by_node[sample.node_id] = sample.value
            residuals_by_node[sample.node_id].append(0.0)
            results.append(
                DetectionResult(
                    predicted_anomaly=False,
                    score=0.0,
                    threshold=config.threshold,
                    reason="insufficient_history",
                )
            )
            continue

        residual = abs(sample.value - previous_mean)
        residual_history = residuals_by_node[sample.node_id]
        residual_std = float(np.std(residual_history)) if residual_history else 0.0
        if residual_std == 0.0:
            score = inf if residual else 0.0
        else:
            score = residual / residual_std
        predicted = bool(score > config.threshold)
        results.append(
            DetectionResult(
                predicted_anomaly=predicted,
                score=float(score),
                threshold=config.threshold,
                reason="ewma_threshold" if predicted else "ewma_normal",
            )
        )

        mean_by_node[sample.node_id] = (
            config.ewma_alpha * sample.value
            + (1.0 - config.ewma_alpha) * previous_mean
        )
        residual_history.append(residual)

    return results


def _safe_divide(numerator: int, denominator: int) -> float:
    """Return a numeric ratio, using 0.0 for undefined empty denominators."""
    return numerator / denominator if denominator else 0.0
