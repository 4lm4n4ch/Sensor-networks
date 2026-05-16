"""Week 4 mini-experiment: compare ALOHA and simplified CSMA.

The experiment uses identical generated traffic arrivals for both protocols at
each load point. Results are saved as CSV and plotted for packet delivery ratio,
collision count, and average delay.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.mac import (
    AlohaMAC,
    BaseMAC,
    CollisionDomain,
    CSMAMAC,
    MACPacket,
    PacketStatus,
)
from wsnsim.sim import Scheduler


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week04_mac_aloha_csma.csv"
PDR_FIGURE_PATH = FIGURES_DIR / "week04_mac_pdr_vs_load.png"
COLLISION_DELAY_FIGURE_PATH = FIGURES_DIR / "week04_mac_collision_delay_vs_load.png"


@dataclass(frozen=True)
class TrafficArrival:
    """One generated application send request."""

    time_s: float
    source_id: int
    destination_id: int
    packet_id: int


def generate_poisson_arrivals(
    *,
    offered_load_pps: float,
    duration_s: float,
    node_count: int,
    seed: int,
) -> list[TrafficArrival]:
    """Generate network-wide Poisson packet arrivals."""
    rng = np.random.default_rng(seed)
    arrivals: list[TrafficArrival] = []
    time_s = 0.0
    packet_id = 0

    while True:
        time_s += float(rng.exponential(1.0 / offered_load_pps))
        if time_s >= duration_s:
            break
        source_id = int(rng.integers(0, node_count))
        destination_id = int((source_id + rng.integers(1, node_count)) % node_count)
        arrivals.append(
            TrafficArrival(
                time_s=time_s,
                source_id=source_id,
                destination_id=destination_id,
                packet_id=packet_id,
            )
        )
        packet_id += 1

    return arrivals


def run_protocol(
    *,
    protocol_name: str,
    arrivals: list[TrafficArrival],
    packet_duration_s: float,
    seed: int,
) -> dict[str, float | int | str]:
    """Run one MAC protocol over a fixed arrival trace and return metrics."""
    scheduler = Scheduler(seed=seed)
    medium = CollisionDomain()

    if protocol_name == "ALOHA":
        mac: BaseMAC = AlohaMAC(scheduler=scheduler, medium=medium)
    elif protocol_name == "CSMA":
        mac = CSMAMAC(
            scheduler=scheduler,
            medium=medium,
            slot_time_s=0.005,
            cw_min=3,
            cw_max=31,
            max_retries=5,
            seed=seed,
        )
    else:
        raise ValueError(f"Unknown protocol: {protocol_name}")

    for arrival in arrivals:
        packet = MACPacket(
            packet_id=arrival.packet_id,
            source_id=arrival.source_id,
            destination_id=arrival.destination_id,
            created_at_s=arrival.time_s,
            size_bytes=64,
        )
        mac.send(packet, at_time_s=arrival.time_s, duration_s=packet_duration_s)

    scheduler.run()

    results = list(mac.results.values())
    sent = len(results)
    successes = sum(result.status == PacketStatus.DELIVERED for result in results)
    collided = sum(result.collision_count for result in results)
    dropped = sum(result.status == PacketStatus.DROPPED for result in results)
    delivered_delays_s = [
        result.delay_s for result in results if result.delay_s is not None
    ]
    average_delay_s = (
        float(np.mean(delivered_delays_s)) if delivered_delays_s else float("nan")
    )
    pdr = successes / sent if sent else 0.0

    return {
        "protocol": protocol_name,
        "packets_sent": sent,
        "packets_successful": successes,
        "packets_collided": collided,
        "packets_dropped": dropped,
        "packet_delivery_ratio": pdr,
        "average_delay_s": average_delay_s,
    }


def write_csv(rows: list[dict[str, float | int | str]]) -> None:
    """Write experiment rows to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "offered_load_pps",
        "protocol",
        "packets_sent",
        "packets_successful",
        "packets_collided",
        "packets_dropped",
        "packet_delivery_ratio",
        "average_delay_s",
    ]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_results(rows: list[dict[str, float | int | str]]) -> None:
    """Generate Week 4 comparison plots."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    protocols = ["ALOHA", "CSMA"]
    loads = sorted({float(row["offered_load_pps"]) for row in rows})

    fig, ax = plt.subplots(figsize=(9, 5))
    for protocol in protocols:
        values = [
            float(
                next(
                    row["packet_delivery_ratio"]
                    for row in rows
                    if row["protocol"] == protocol
                    and float(row["offered_load_pps"]) == load
                )
            )
            for load in loads
        ]
        ax.plot(loads, values, marker="o", label=protocol)
    ax.set_title("Week 4 MAC: packet delivery ratio vs traffic load")
    ax.set_xlabel("Offered load (packets/s)")
    ax.set_ylabel("Packet delivery ratio")
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(PDR_FIGURE_PATH, dpi=150)
    plt.close(fig)

    fig, (ax_collisions, ax_delay) = plt.subplots(1, 2, figsize=(12, 5))
    for protocol in protocols:
        collision_values = [
            int(
                next(
                    row["packets_collided"]
                    for row in rows
                    if row["protocol"] == protocol
                    and float(row["offered_load_pps"]) == load
                )
            )
            for load in loads
        ]
        delay_values = [
            float(
                next(
                    row["average_delay_s"]
                    for row in rows
                    if row["protocol"] == protocol
                    and float(row["offered_load_pps"]) == load
                )
            )
            for load in loads
        ]
        ax_collisions.plot(loads, collision_values, marker="o", label=protocol)
        ax_delay.plot(loads, delay_values, marker="o", label=protocol)

    ax_collisions.set_title("Collided packets")
    ax_collisions.set_xlabel("Offered load (packets/s)")
    ax_collisions.set_ylabel("Collision count")
    ax_collisions.grid(True, alpha=0.3)
    ax_collisions.legend()

    ax_delay.set_title("Average delay")
    ax_delay.set_xlabel("Offered load (packets/s)")
    ax_delay.set_ylabel("Seconds")
    ax_delay.grid(True, alpha=0.3)
    ax_delay.legend()

    fig.tight_layout()
    fig.savefig(COLLISION_DELAY_FIGURE_PATH, dpi=150)
    plt.close(fig)


def main() -> None:
    """Run the Week 4 MAC comparison experiment."""
    load_settings_pps = [10.0, 25.0, 50.0]
    simulation_duration_s = 20.0
    node_count = 10
    packet_duration_s = 0.02
    base_seed = 42069

    rows: list[dict[str, float | int | str]] = []
    for load_index, offered_load_pps in enumerate(load_settings_pps):
        arrivals = generate_poisson_arrivals(
            offered_load_pps=offered_load_pps,
            duration_s=simulation_duration_s,
            node_count=node_count,
            seed=base_seed + load_index,
        )
        for protocol in ["ALOHA", "CSMA"]:
            row = run_protocol(
                protocol_name=protocol,
                arrivals=arrivals,
                packet_duration_s=packet_duration_s,
                seed=base_seed + load_index,
            )
            row["offered_load_pps"] = offered_load_pps
            rows.append(row)

    write_csv(rows)
    plot_results(rows)

    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {PDR_FIGURE_PATH}")
    print(f"Wrote {COLLISION_DELAY_FIGURE_PATH}")


if __name__ == "__main__":
    main()
