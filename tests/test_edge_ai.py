"""Tests for Week 11 edge AI anomaly detection."""

import pytest

from wsnsim.models.edge_ai import (
    DetectionResult,
    DetectorConfig,
    SensorSample,
    SignalGeneratorConfig,
    calculate_edge_ai_metrics,
    detect_samples,
    detect_sample_zscore,
    generate_sensor_samples,
)


def sample(value: float, *, anomaly: bool = False, timestamp: float = 0.0) -> SensorSample:
    """Create a compact single-node sample for detector tests."""
    return SensorSample(
        node_id=1,
        timestamp_s=timestamp,
        value=value,
        is_anomaly=anomaly,
    )


def test_signal_generation_is_deterministic_with_fixed_seed():
    config = SignalGeneratorConfig(
        seed=2026,
        n_nodes=4,
        n_timesteps=5,
        anomaly_probability=0.2,
    )

    assert generate_sensor_samples(config) == generate_sensor_samples(config)


def test_generated_samples_include_ground_truth_anomaly_labels():
    samples = generate_sensor_samples(
        SignalGeneratorConfig(
            seed=1,
            n_nodes=3,
            n_timesteps=2,
            anomaly_probability=1.0,
        )
    )

    assert len(samples) == 6
    assert all(sample.is_anomaly for sample in samples)


def test_zscore_detector_detects_clear_anomaly():
    config = DetectorConfig(detector_type="zscore", threshold=3.0)
    result = detect_sample_zscore(
        sample(20.0, anomaly=True),
        history=[10.0, 10.0, 10.0, 10.0],
        config=config,
    )

    assert result.predicted_anomaly
    assert result.score == float("inf")


def test_normal_values_are_not_flagged_under_reasonable_threshold():
    config = DetectorConfig(detector_type="zscore", threshold=3.0, window_size=4)
    samples = [
        sample(10.0, timestamp=0.0),
        sample(10.1, timestamp=1.0),
        sample(9.9, timestamp=2.0),
        sample(10.0, timestamp=3.0),
        sample(10.05, timestamp=4.0),
    ]

    results = detect_samples(samples, config)

    assert not results[-1].predicted_anomaly


def test_confusion_matrix_counts_tp_fp_tn_fn_correctly():
    samples = [
        sample(1.0, anomaly=True),
        sample(2.0, anomaly=False),
        sample(3.0, anomaly=False),
        sample(4.0, anomaly=True),
    ]
    results = [
        DetectionResult(True, 4.0, 2.0, "test"),
        DetectionResult(True, 3.0, 2.0, "test"),
        DetectionResult(False, 0.1, 2.0, "test"),
        DetectionResult(False, 0.5, 2.0, "test"),
    ]

    metrics = calculate_edge_ai_metrics(samples, results)

    assert metrics.true_positive == 1
    assert metrics.false_positive == 1
    assert metrics.true_negative == 1
    assert metrics.false_negative == 1


def test_precision_recall_f1_formulas_are_correct_on_known_inputs():
    samples = [
        sample(0.0, anomaly=True),
        sample(0.0, anomaly=True),
        sample(0.0, anomaly=True),
        sample(0.0, anomaly=False),
        sample(0.0, anomaly=False),
        sample(0.0, anomaly=False),
    ]
    results = [
        DetectionResult(True, 1.0, 0.5, "tp"),
        DetectionResult(True, 1.0, 0.5, "tp"),
        DetectionResult(False, 0.0, 0.5, "fn"),
        DetectionResult(True, 1.0, 0.5, "fp"),
        DetectionResult(False, 0.0, 0.5, "tn"),
        DetectionResult(False, 0.0, 0.5, "tn"),
    ]

    metrics = calculate_edge_ai_metrics(samples, results)

    assert metrics.precision == pytest.approx(2 / 3)
    assert metrics.recall == pytest.approx(2 / 3)
    assert metrics.f1 == pytest.approx(2 / 3)
    assert metrics.false_positive_rate == pytest.approx(1 / 3)
    assert metrics.false_negative_rate == pytest.approx(1 / 3)


def test_communication_saving_formula_is_correct():
    samples = [sample(float(index)) for index in range(4)]
    results = [
        DetectionResult(True, 1.0, 0.5, "tx"),
        DetectionResult(False, 0.0, 0.5, "quiet"),
        DetectionResult(False, 0.0, 0.5, "quiet"),
        DetectionResult(False, 0.0, 0.5, "quiet"),
    ]

    metrics = calculate_edge_ai_metrics(
        samples,
        results,
        energy_per_packet_j=0.25,
    )

    assert metrics.baseline_packets == 4
    assert metrics.transmitted_packets == 1
    assert metrics.communication_saving_ratio == pytest.approx(0.75)
    assert metrics.energy_saved_j == pytest.approx(0.75)


def test_higher_threshold_reduces_false_positives_but_may_increase_false_negatives():
    samples = [
        sample(0.0, timestamp=0.0),
        sample(1.0, timestamp=1.0),
        sample(-1.0, timestamp=2.0),
        sample(0.0, timestamp=3.0),
        sample(1.4, anomaly=False, timestamp=4.0),
        sample(2.8, anomaly=True, timestamp=5.0),
    ]

    low_results = detect_samples(
        samples,
        DetectorConfig(detector_type="zscore", threshold=1.5, window_size=4),
    )
    high_results = detect_samples(
        samples,
        DetectorConfig(detector_type="zscore", threshold=3.0, window_size=4),
    )
    low_metrics = calculate_edge_ai_metrics(samples, low_results)
    high_metrics = calculate_edge_ai_metrics(samples, high_results)

    assert high_metrics.false_positive <= low_metrics.false_positive
    assert high_metrics.false_negative >= low_metrics.false_negative


def test_no_divide_by_zero_in_empty_and_no_positive_cases():
    empty_metrics = calculate_edge_ai_metrics([], [])
    normal_only = [sample(1.0), sample(2.0)]
    normal_results = [
        DetectionResult(False, 0.0, 2.0, "normal"),
        DetectionResult(False, 0.0, 2.0, "normal"),
    ]

    normal_metrics = calculate_edge_ai_metrics(normal_only, normal_results)

    assert empty_metrics.precision == 0.0
    assert empty_metrics.recall == 0.0
    assert empty_metrics.f1 == 0.0
    assert empty_metrics.false_positive_rate == 0.0
    assert empty_metrics.false_negative_rate == 0.0
    assert empty_metrics.communication_saving_ratio == 0.0
    assert normal_metrics.precision == 0.0
    assert normal_metrics.recall == 0.0
    assert normal_metrics.f1 == 0.0
    assert normal_metrics.false_positive_rate == 0.0
    assert normal_metrics.false_negative_rate == 0.0
