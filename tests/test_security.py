"""Tests for Week 10 WSN security and replay protection."""

import pytest

from wsnsim.models.security import (
    SecurePacketMetadata,
    SecurityConfig,
    SecurityLayer,
)


def packet(sender: int, receiver: int, sequence: int) -> SecurePacketMetadata:
    """Create deterministic packet metadata for replay tests."""
    return SecurePacketMetadata(
        sender_id=sender,
        receiver_id=receiver,
        sequence_number=sequence,
        nonce=sequence + 1000,
        auth_tag_bytes=8,
        timestamp_s=sequence * 0.1,
    )


def test_increasing_sequence_numbers_are_accepted():
    security = SecurityLayer(SecurityConfig(seed=1))

    first = security.check_packet(packet(1, 0, 1), payload_bytes=64)
    second = security.check_packet(packet(1, 0, 2), payload_bytes=64)

    assert first.accepted
    assert second.accepted


def test_duplicate_sequence_number_is_rejected():
    security = SecurityLayer(SecurityConfig(seed=1))

    security.check_packet(packet(1, 0, 7), payload_bytes=64)
    replay = security.check_packet(packet(1, 0, 7), payload_bytes=64)

    assert not replay.accepted
    assert replay.reason == "replay_duplicate_sequence"


def test_old_sequence_number_is_rejected():
    security = SecurityLayer(SecurityConfig(seed=1))

    security.check_packet(packet(1, 0, 10), payload_bytes=64)
    old = security.check_packet(packet(1, 0, 9), payload_bytes=64)

    assert not old.accepted
    assert old.reason == "replay_old_sequence"


def test_replay_attack_is_rejected():
    security = SecurityLayer(SecurityConfig(seed=42069))
    legitimate = security.make_metadata(sender_id=2, receiver_id=0)

    accepted = security.check_packet(legitimate, payload_bytes=64)
    replayed = security.check_packet(
        legitimate,
        payload_bytes=64,
        include_auth_generation=False,
    )

    assert accepted.accepted
    assert not replayed.accepted
    assert security.metrics.replay_rejected == 1


def test_security_disabled_accepts_packets_without_overhead():
    security = SecurityLayer(SecurityConfig(enabled=False))

    decision = security.check_packet(packet(1, 0, 1), payload_bytes=64)

    assert decision.accepted
    assert decision.reason == "security_disabled"
    assert decision.overhead_bytes == 0
    assert decision.cpu_energy_j == 0.0
    assert decision.latency_overhead_s == 0.0


def test_overhead_bytes_are_calculated_correctly():
    security = SecurityLayer(
        SecurityConfig(auth_tag_bytes=16, nonce_bytes=8, seed=1)
    )

    decision = security.check_packet(packet(1, 0, 1), payload_bytes=64)

    assert decision.overhead_bytes == 24
    assert security.metrics.overhead_bytes_total == 24


def test_cpu_energy_overhead_is_calculated_correctly():
    config = SecurityConfig(
        auth_tag_bytes=8,
        nonce_bytes=4,
        cpu_cost_per_byte_j=2.0e-9,
        verify_cost_per_byte_j=3.0e-9,
        seed=1,
    )
    security = SecurityLayer(config)

    decision = security.check_packet(packet(1, 0, 1), payload_bytes=64)

    processed_bytes = 64 + 8 + 4
    expected_energy = processed_bytes * (2.0e-9 + 3.0e-9)
    assert decision.cpu_energy_j == pytest.approx(expected_energy)


def test_metrics_count_accepted_rejected_and_replay_packets_correctly():
    security = SecurityLayer(SecurityConfig(seed=1))

    security.check_packet(packet(1, 0, 1), payload_bytes=64)
    security.check_packet(packet(1, 0, 2), payload_bytes=64)
    security.check_packet(packet(1, 0, 2), payload_bytes=64)
    security.check_packet(packet(1, 0, 1), payload_bytes=64)

    assert security.metrics.packets_checked == 4
    assert security.metrics.packets_accepted == 2
    assert security.metrics.packets_rejected == 2
    assert security.metrics.replay_rejected == 2


def test_behavior_is_deterministic_with_fixed_seed():
    first = SecurityLayer(SecurityConfig(seed=42069))
    second = SecurityLayer(SecurityConfig(seed=42069))

    first_metadata = [
        first.make_metadata(sender_id=1, receiver_id=0)
        for _ in range(3)
    ]
    second_metadata = [
        second.make_metadata(sender_id=1, receiver_id=0)
        for _ in range(3)
    ]
    first_decisions = [
        first.check_packet(metadata, payload_bytes=64)
        for metadata in first_metadata
    ]
    second_decisions = [
        second.check_packet(metadata, payload_bytes=64)
        for metadata in second_metadata
    ]

    assert first_metadata == second_metadata
    assert first_decisions == second_decisions


def test_independent_senders_have_independent_sequence_tracking():
    security = SecurityLayer(SecurityConfig(seed=1))

    first_sender = security.check_packet(packet(1, 0, 1), payload_bytes=64)
    second_sender = security.check_packet(packet(2, 0, 1), payload_bytes=64)

    assert first_sender.accepted
    assert second_sender.accepted
