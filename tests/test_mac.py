"""Tests for Week 4 MAC protocols and collision behavior."""

import pytest

from wsnsim.models.mac import (
    AlohaMAC,
    CollisionDomain,
    CSMAMAC,
    MACPacket,
    MacEventType,
    PacketStatus,
    Transmission,
    transmission_intervals_overlap,
)
from wsnsim.sim import Scheduler


def packet(packet_id: int, source_id: int = 1, created_at_s: float = 0.0) -> MACPacket:
    """Create a small deterministic MAC packet."""
    return MACPacket(
        packet_id=packet_id,
        source_id=source_id,
        destination_id=99,
        created_at_s=created_at_s,
        size_bytes=32,
    )


def block_channel(medium: CollisionDomain, duration_s: float = 10.0) -> None:
    """Create a long active transmission that keeps the medium busy."""
    medium.start_transmission(
        Transmission(
            packet=packet(10_000, source_id=0),
            start_time_s=0.0,
            duration_s=duration_s,
        )
    )


def test_aloha_same_time_transmissions_collide():
    scheduler = Scheduler(seed=1)
    medium = CollisionDomain()
    mac = AlohaMAC(scheduler=scheduler, medium=medium)

    first = packet(1, source_id=1)
    second = packet(2, source_id=2)
    mac.send(first, at_time_s=0.0, duration_s=1.0)
    mac.send(second, at_time_s=0.0, duration_s=1.0)

    scheduler.run()

    assert mac.results[first.packet_id].status == PacketStatus.COLLIDED
    assert mac.results[second.packet_id].status == PacketStatus.COLLIDED
    assert mac.results[first.packet_id].collision_count == 1
    assert mac.results[second.packet_id].collision_count == 1


def test_aloha_non_overlapping_transmissions_do_not_collide():
    scheduler = Scheduler(seed=2)
    medium = CollisionDomain()
    mac = AlohaMAC(scheduler=scheduler, medium=medium)

    first = packet(1, source_id=1)
    second = packet(2, source_id=2)
    mac.send(first, at_time_s=0.0, duration_s=1.0)
    mac.send(second, at_time_s=1.0, duration_s=1.0)

    scheduler.run()

    assert mac.results[first.packet_id].status == PacketStatus.DELIVERED
    assert mac.results[second.packet_id].status == PacketStatus.DELIVERED
    assert mac.results[first.packet_id].collision_count == 0
    assert mac.results[second.packet_id].collision_count == 0


def test_csma_busy_channel_backs_off_instead_of_transmitting_immediately():
    scheduler = Scheduler(seed=3)
    medium = CollisionDomain()
    block_channel(medium)
    mac = CSMAMAC(
        scheduler=scheduler,
        medium=medium,
        slot_time_s=0.01,
        cw_min=3,
        cw_max=7,
        max_retries=5,
        seed=123,
    )
    waiting_packet = packet(1, source_id=1)

    mac.send(waiting_packet, at_time_s=0.0, duration_s=1.0)
    scheduler.run(until=0.0)

    event_types = [event.event_type for event in mac.events]
    assert MacEventType.CARRIER_SENSE in event_types
    assert MacEventType.BACKOFF in event_types
    assert MacEventType.TRANSMISSION_START not in event_types
    assert mac.results[waiting_packet.packet_id].start_times_s == []


def test_csma_backoff_is_reproducible_with_fixed_seed():
    def run_once() -> list[float]:
        scheduler = Scheduler(seed=4)
        medium = CollisionDomain()
        block_channel(medium)
        mac = CSMAMAC(
            scheduler=scheduler,
            medium=medium,
            slot_time_s=0.01,
            cw_min=7,
            cw_max=15,
            max_retries=4,
            seed=77,
        )
        waiting_packet = packet(1, source_id=1)
        mac.send(waiting_packet, at_time_s=0.0, duration_s=1.0)
        scheduler.run(until=0.0)
        return mac.results[waiting_packet.packet_id].backoffs_s

    first_run = run_once()

    assert first_run
    assert first_run == run_once()


def test_collision_detection_uses_interval_overlap_not_only_equal_start_times():
    assert transmission_intervals_overlap(0.0, 1.0, 0.5, 1.0)
    assert not transmission_intervals_overlap(0.0, 1.0, 1.0, 1.0)

    scheduler = Scheduler(seed=5)
    medium = CollisionDomain()
    mac = AlohaMAC(scheduler=scheduler, medium=medium)
    first = packet(1, source_id=1)
    second = packet(2, source_id=2)

    mac.send(first, at_time_s=0.0, duration_s=1.0)
    mac.send(second, at_time_s=0.5, duration_s=1.0)
    scheduler.run()

    assert mac.results[first.packet_id].status == PacketStatus.COLLIDED
    assert mac.results[second.packet_id].status == PacketStatus.COLLIDED


def test_csma_retry_limit_drops_packet_when_channel_remains_busy():
    scheduler = Scheduler(seed=6)
    medium = CollisionDomain()
    block_channel(medium)
    mac = CSMAMAC(
        scheduler=scheduler,
        medium=medium,
        slot_time_s=0.01,
        cw_min=0,
        cw_max=0,
        max_retries=2,
        seed=99,
    )
    waiting_packet = packet(1, source_id=1)

    mac.send(waiting_packet, at_time_s=0.0, duration_s=1.0)
    scheduler.run()

    result = mac.results[waiting_packet.packet_id]
    assert result.status == PacketStatus.DROPPED
    assert result.drop_reason == "max_retries_busy"
    assert result.backoffs_s == pytest.approx([0.0, 0.0])
    assert result.attempts == 0
