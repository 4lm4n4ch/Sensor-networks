"""Tests for Week 7 link-level ACK/retry reliability."""

import pytest

from wsnsim.models.reliability import (
    LinkReliabilityARQ,
    ReliabilityConfig,
    ReliabilityEventType,
    ReliabilityMetrics,
    TransmissionAttempt,
)
from wsnsim.sim import Scheduler


def config(**overrides) -> ReliabilityConfig:
    """Create a compact ARQ config for deterministic tests."""
    values = {
        "ack_timeout_s": 0.02,
        "base_backoff_s": 0.005,
        "max_backoff_s": 0.05,
        "backoff_multiplier": 2.0,
        "seed": 123,
        "ack_size_bytes": 4,
        "processing_delay_s": 0.001,
        "propagation_delay_s": 0.001,
        "tx_energy_per_bit_j": 1e-6,
        "rx_energy_per_bit_j": 1e-6,
    }
    values.update(overrides)
    return ReliabilityConfig(**values)


def run_one(
    *,
    reliability_config: ReliabilityConfig | None = None,
    data_success=None,
    ack_success=None,
    size_bytes: int = 16,
) -> LinkReliabilityARQ:
    """Run one packet through a configured ARQ model."""
    scheduler = Scheduler(seed=1)
    arq = LinkReliabilityARQ(
        scheduler=scheduler,
        config=reliability_config or config(),
        data_success=data_success,
        ack_success=ack_success,
    )
    arq.send_packet(
        packet_id="p0",
        source_id=1,
        destination_id=2,
        size_bytes=size_bytes,
        at_time_s=0.0,
    )
    scheduler.run()
    return arq


def attempt_is_successful(attempt: TransmissionAttempt) -> bool:
    """Return success for every attempt."""
    return True


def attempt_always_fails(attempt: TransmissionAttempt) -> bool:
    """Return failure for every attempt."""
    return False


def test_successful_data_and_ack_marks_packet_delivered():
    arq = run_one(
        data_success=attempt_is_successful,
        ack_success=attempt_is_successful,
    )

    assert arq.metrics.generated_packets == 1
    assert arq.metrics.delivered_packets == 1
    assert arq.metrics.failed_packets == 0
    assert arq.metrics.pdr == pytest.approx(1.0)
    assert arq.attempts[0].success
    assert ReliabilityEventType.PACKET_DELIVERED in {
        event.event_type for event in arq.events
    }


def test_lost_data_packet_triggers_retry():
    arq = run_one(
        data_success=lambda attempt: attempt.attempt_index > 0,
        ack_success=attempt_is_successful,
    )

    assert arq.metrics.delivered_packets == 1
    assert arq.metrics.total_attempts == 2
    assert arq.metrics.total_retries == 1
    assert arq.attempts[0].failure_reason == "data_lost"


def test_lost_ack_triggers_retry_until_ack_arrives():
    arq = run_one(
        data_success=attempt_is_successful,
        ack_success=lambda attempt: attempt.attempt_index > 0,
    )

    assert arq.metrics.delivered_packets == 1
    assert arq.metrics.ack_packets == 2
    assert arq.metrics.timeout_count == 1
    assert arq.metrics.total_retries == 1
    assert arq.attempts[0].failure_reason == "ack_lost"


def test_retry_limit_zero_causes_no_retry():
    arq = run_one(
        reliability_config=config(retry_limit=0),
        data_success=attempt_always_fails,
        ack_success=attempt_is_successful,
    )

    assert arq.metrics.delivered_packets == 0
    assert arq.metrics.failed_packets == 1
    assert arq.metrics.total_attempts == 1
    assert arq.metrics.total_retries == 0


def test_retry_limit_is_respected():
    arq = run_one(
        reliability_config=config(retry_limit=2),
        data_success=attempt_always_fails,
        ack_success=attempt_is_successful,
    )

    assert arq.metrics.total_attempts == 3
    assert arq.metrics.total_retries == 2
    assert [attempt.attempt_index for attempt in arq.attempts] == [0, 1, 2]


def test_packet_is_dropped_after_retry_limit_exceeded():
    arq = run_one(
        reliability_config=config(retry_limit=1),
        data_success=attempt_always_fails,
        ack_success=attempt_is_successful,
    )

    assert arq.metrics.failed_packets == 1
    assert arq.metrics.pdr == pytest.approx(0.0)
    assert ReliabilityEventType.PACKET_DROPPED in {
        event.event_type for event in arq.events
    }


def test_backoff_is_deterministic_with_fixed_seed():
    def backoffs() -> list[float]:
        arq = run_one(
            reliability_config=config(retry_limit=2, seed=77),
            data_success=attempt_always_fails,
            ack_success=attempt_is_successful,
        )
        return [
            float(event.details["backoff_s"])
            for event in arq.events
            if event.event_type == ReliabilityEventType.BACKOFF
        ]

    first = backoffs()

    assert first
    assert all(backoff_s > 0.0 for backoff_s in first)
    assert first == pytest.approx(backoffs())


def test_metrics_compute_pdr_correctly():
    metrics = ReliabilityMetrics(generated_packets=4, delivered_packets=3)

    assert metrics.pdr == pytest.approx(0.75)


def test_total_attempts_and_retries_are_counted_correctly():
    arq = run_one(
        reliability_config=config(retry_limit=3),
        data_success=lambda attempt: attempt.attempt_index == 2,
        ack_success=attempt_is_successful,
    )

    assert arq.metrics.total_attempts == 3
    assert arq.metrics.total_retries == 2
    assert arq.metrics.average_attempts_per_packet == pytest.approx(3.0)


def test_latency_increases_when_retries_occur():
    first_try = run_one(
        data_success=attempt_is_successful,
        ack_success=attempt_is_successful,
    )
    second_try = run_one(
        data_success=lambda attempt: attempt.attempt_index > 0,
        ack_success=attempt_is_successful,
    )

    assert second_try.metrics.average_latency_s > first_try.metrics.average_latency_s


def test_energy_increases_when_retries_and_acks_are_used():
    no_ack = run_one(
        reliability_config=config(ack_enabled=False),
        data_success=attempt_is_successful,
        ack_success=attempt_is_successful,
    )
    retried = run_one(
        data_success=lambda attempt: attempt.attempt_index > 0,
        ack_success=attempt_is_successful,
    )

    assert retried.metrics.ack_packets == 1
    assert retried.metrics.total_energy_j > no_ack.metrics.total_energy_j


def test_no_divide_by_zero_in_empty_or_all_failed_cases():
    empty = ReliabilityMetrics()
    failed = run_one(
        reliability_config=config(retry_limit=0),
        data_success=attempt_always_fails,
        ack_success=attempt_always_fails,
    ).metrics

    assert empty.pdr == pytest.approx(0.0)
    assert empty.average_attempts_per_packet == pytest.approx(0.0)
    assert empty.average_latency_s == pytest.approx(0.0)
    assert failed.pdr == pytest.approx(0.0)
    assert failed.average_latency_s == pytest.approx(0.0)
