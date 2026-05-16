"""Week 10 experiment: replay protection and security overhead."""

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

from wsnsim.models.security import (  # noqa: E402
    SecurePacketMetadata,
    SecurityConfig,
    SecurityLayer,
)


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week10_security_overhead.csv"
REPLAY_FIGURE_PATH = FIGURES_DIR / "week10_replay_accept_reject_vs_attack_rate.png"
TOTAL_BYTES_FIGURE_PATH = FIGURES_DIR / "week10_total_transmitted_bytes.png"
OVERHEAD_RATIO_FIGURE_PATH = FIGURES_DIR / "week10_security_overhead_ratio.png"
BYTES_PER_PACKET_FIGURE_PATH = (
    FIGURES_DIR / "week10_security_overhead_bytes_per_packet.png"
)
CPU_FIGURE_PATH = FIGURES_DIR / "week10_security_cpu_energy.png"


@dataclass(frozen=True)
class ExperimentScenario:
    """Fixed Week 10 security-overhead scenario."""

    seed: int = 42069
    n_packets: int = 1000
    payload_bytes: int = 64
    auth_tag_bytes: int = 8
    nonce_bytes: int = 4
    sender_id: int = 1
    receiver_id: int = 0


@dataclass(frozen=True)
class TrafficEvent:
    """One legitimate packet or replayed old packet attempt."""

    metadata: SecurePacketMetadata
    is_replay: bool


def build_traffic(
    scenario: ExperimentScenario,
    replay_attack_rate: float,
) -> list[TrafficEvent]:
    """Build deterministic traffic with selected packets replayed once."""
    if replay_attack_rate < 0.0 or replay_attack_rate > 1.0:
        raise ValueError("replay_attack_rate must be in [0, 1]")

    replay_count = round(scenario.n_packets * replay_attack_rate)
    rng = np.random.default_rng(scenario.seed + int(replay_attack_rate * 1000))
    replay_indices = set(
        int(index)
        for index in rng.choice(
            scenario.n_packets,
            size=replay_count,
            replace=False,
        )
    )

    traffic: list[TrafficEvent] = []
    for sequence_number in range(scenario.n_packets):
        metadata = SecurePacketMetadata(
            sender_id=scenario.sender_id,
            receiver_id=scenario.receiver_id,
            sequence_number=sequence_number,
            nonce=sequence_number + 100_000,
            auth_tag_bytes=scenario.auth_tag_bytes,
            timestamp_s=float(sequence_number),
        )
        traffic.append(TrafficEvent(metadata=metadata, is_replay=False))
        if sequence_number in replay_indices:
            traffic.append(TrafficEvent(metadata=metadata, is_replay=True))

    return traffic


def run_mode(
    *,
    scenario: ExperimentScenario,
    replay_attack_rate: float,
    security_enabled: bool,
) -> dict[str, float | int | bool | str]:
    """Run one baseline or secured security-overhead condition."""
    config = SecurityConfig(
        enabled=security_enabled,
        replay_protection=security_enabled,
        auth_tag_bytes=scenario.auth_tag_bytes,
        nonce_bytes=scenario.nonce_bytes,
        sequence_window=0,
        cpu_cost_per_byte_j=2.0e-9,
        verify_cost_per_byte_j=3.0e-9,
        seed=scenario.seed,
    )
    security = SecurityLayer(config)
    traffic = build_traffic(scenario, replay_attack_rate)
    replay_packets = 0
    replay_accepted = 0
    replay_rejected = 0

    for event in traffic:
        decision = security.check_packet(
            event.metadata,
            payload_bytes=scenario.payload_bytes,
            include_auth_generation=not event.is_replay,
        )
        if event.is_replay:
            replay_packets += 1
            if decision.accepted:
                replay_accepted += 1
            else:
                replay_rejected += 1

    metrics = security.metrics
    packets_sent = len(traffic)
    legitimate_packets = scenario.n_packets
    total_payload_bytes = packets_sent * scenario.payload_bytes
    total_security_overhead_bytes = metrics.overhead_bytes_total
    total_transmitted_bytes = total_payload_bytes + total_security_overhead_bytes
    acceptance_rate = (
        metrics.packets_accepted / packets_sent
        if packets_sent
        else 0.0
    )
    rejection_rate = (
        metrics.packets_rejected / packets_sent
        if packets_sent
        else 0.0
    )
    cpu_energy_j_per_packet = (
        metrics.cpu_energy_j_total / packets_sent if packets_sent else 0.0
    )
    latency_overhead_s_per_packet = (
        metrics.latency_overhead_s_total / packets_sent if packets_sent else 0.0
    )
    security_overhead_ratio = (
        total_security_overhead_bytes / total_transmitted_bytes
        if total_transmitted_bytes
        else 0.0
    )

    return {
        "security_enabled": security_enabled,
        "mode": "replay_protection" if security_enabled else "baseline",
        "replay_attack_rate": replay_attack_rate,
        "seed": scenario.seed,
        "n_packets": scenario.n_packets,
        "payload_bytes": scenario.payload_bytes,
        "auth_tag_bytes": scenario.auth_tag_bytes,
        "nonce_bytes": scenario.nonce_bytes,
        "security_overhead_bytes_per_packet": (
            config.overhead_bytes_per_packet
        ),
        "packets_sent": packets_sent,
        "legitimate_packets": legitimate_packets,
        "replay_packets": replay_packets,
        "packets_accepted": metrics.packets_accepted,
        "packets_rejected": metrics.packets_rejected,
        "replay_accepted": replay_accepted,
        "replay_rejected": replay_rejected,
        "acceptance_rate": acceptance_rate,
        "rejection_rate": rejection_rate,
        "total_payload_bytes": total_payload_bytes,
        "total_security_overhead_bytes": total_security_overhead_bytes,
        "total_transmitted_bytes": total_transmitted_bytes,
        "security_overhead_ratio": security_overhead_ratio,
        "cpu_energy_j_total": metrics.cpu_energy_j_total,
        "cpu_energy_j_per_packet": cpu_energy_j_per_packet,
        "latency_overhead_s_total": metrics.latency_overhead_s_total,
        "latency_overhead_s_per_packet": latency_overhead_s_per_packet,
    }


def run_sweep(
    scenario: ExperimentScenario,
    replay_attack_rates: list[float],
) -> list[dict[str, float | int | bool | str]]:
    """Run baseline and secured modes for every replay rate."""
    rows: list[dict[str, float | int | bool | str]] = []
    for replay_attack_rate in replay_attack_rates:
        rows.append(
            run_mode(
                scenario=scenario,
                replay_attack_rate=replay_attack_rate,
                security_enabled=False,
            )
        )
        rows.append(
            run_mode(
                scenario=scenario,
                replay_attack_rate=replay_attack_rate,
                security_enabled=True,
            )
        )
    return rows


def write_csv(rows: list[dict[str, float | int | bool | str]]) -> None:
    """Write Week 10 security-overhead results to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_outputs(rows: list[dict[str, float | int | bool | str]]) -> None:
    """Generate replay-abuse and security-overhead figures."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_rows = [row for row in rows if not row["security_enabled"]]
    secured_rows = [row for row in rows if row["security_enabled"]]

    _plot_replay_accept_reject(baseline_rows, secured_rows)
    _plot_total_transmitted_bytes(baseline_rows, secured_rows)
    _plot_overhead_ratio(baseline_rows, secured_rows)
    _plot_cpu_energy(baseline_rows, secured_rows)
    _plot_overhead_bytes_per_packet(baseline_rows, secured_rows)


def _plot_replay_accept_reject(
    baseline_rows: list[dict[str, float | int | bool | str]],
    secured_rows: list[dict[str, float | int | bool | str]],
) -> None:
    """Plot baseline replay acceptance against protected replay rejection."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    attack_rates = [float(row["replay_attack_rate"]) for row in baseline_rows]
    baseline_counts = [int(row["replay_accepted"]) for row in baseline_rows]
    secured_counts = [int(row["replay_rejected"]) for row in secured_rows]
    bar_width = 0.018

    ax.bar(
        [rate - bar_width / 2 for rate in attack_rates],
        baseline_counts,
        width=bar_width,
        color="#d95f02",
        alpha=0.85,
        label="Baseline: replay accepted",
        align="center",
    )
    ax.bar(
        [rate + bar_width / 2 for rate in attack_rates],
        secured_counts,
        width=bar_width,
        color="#2b6cb0",
        alpha=0.85,
        label="Replay protection: replay rejected",
        align="center",
    )
    ax.set_title("Week 10 replay accepted/rejected vs attack rate")
    ax.set_xlabel("Replay attack rate")
    ax.set_ylabel("Replay packet count")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(REPLAY_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_total_transmitted_bytes(
    baseline_rows: list[dict[str, float | int | bool | str]],
    secured_rows: list[dict[str, float | int | bool | str]],
) -> None:
    """Plot total transmitted bytes including payload and security metadata."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for label, rows, color, marker in [
        ("Baseline", baseline_rows, "#7f7f7f", "s"),
        ("Replay protection", secured_rows, "#4daf4a", "o"),
    ]:
        ax.plot(
            [float(row["replay_attack_rate"]) for row in rows],
            [int(row["total_transmitted_bytes"]) for row in rows],
            color=color,
            marker=marker,
            linewidth=1.8,
            label=label,
        )
    ax.set_title("Week 10 total transmitted bytes vs replay attack rate")
    ax.set_xlabel("Replay attack rate")
    ax.set_ylabel("Total transmitted bytes (payload + security metadata)")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(TOTAL_BYTES_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_overhead_ratio(
    baseline_rows: list[dict[str, float | int | bool | str]],
    secured_rows: list[dict[str, float | int | bool | str]],
) -> None:
    """Plot security metadata share of total transmitted bytes."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for label, rows, color, marker in [
        ("Baseline", baseline_rows, "#7f7f7f", "s"),
        ("Replay protection", secured_rows, "#756bb1", "o"),
    ]:
        ax.plot(
            [float(row["replay_attack_rate"]) for row in rows],
            [float(row["security_overhead_ratio"]) for row in rows],
            color=color,
            marker=marker,
            linewidth=1.8,
            label=label,
        )
    ax.set_title("Week 10 security overhead ratio vs replay attack rate")
    ax.set_xlabel("Replay attack rate")
    ax.set_ylabel("Security overhead ratio (security / total)")
    ax.set_ylim(bottom=0.0)
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(OVERHEAD_RATIO_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_cpu_energy(
    baseline_rows: list[dict[str, float | int | bool | str]],
    secured_rows: list[dict[str, float | int | bool | str]],
) -> None:
    """Plot total security CPU energy overhead."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for label, rows, color, marker in [
        ("Baseline", baseline_rows, "#7f7f7f", "s"),
        ("Replay protection", secured_rows, "#e41a1c", "o"),
    ]:
        ax.plot(
            [float(row["replay_attack_rate"]) for row in rows],
            [float(row["cpu_energy_j_total"]) for row in rows],
            color=color,
            marker=marker,
            linewidth=1.8,
            label=label,
        )
    ax.set_title("Week 10 security CPU energy overhead vs replay attack rate")
    ax.set_xlabel("Replay attack rate")
    ax.set_ylabel("Total CPU security overhead (J)")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(CPU_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_overhead_bytes_per_packet(
    baseline_rows: list[dict[str, float | int | bool | str]],
    secured_rows: list[dict[str, float | int | bool | str]],
) -> None:
    """Plot the fixed nonce plus authentication-tag overhead per packet."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for label, rows, color, marker in [
        ("Baseline", baseline_rows, "#7f7f7f", "s"),
        ("Replay protection", secured_rows, "#4daf4a", "o"),
    ]:
        ax.plot(
            [float(row["replay_attack_rate"]) for row in rows],
            [
                int(row["security_overhead_bytes_per_packet"])
                for row in rows
            ],
            color=color,
            marker=marker,
            linewidth=1.8,
            label=label,
        )
    ax.set_title("Week 10 fixed security overhead per packet")
    ax.set_xlabel("Replay attack rate")
    ax.set_ylabel("Security overhead (B/packet)")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(BYTES_PER_PACKET_FIGURE_PATH, dpi=150)
    plt.close(fig)


def main() -> None:
    """Run the Week 10 replay-protection overhead experiment."""
    scenario = ExperimentScenario()
    replay_attack_rates = [0.0, 0.05, 0.1, 0.2, 0.4]
    rows = run_sweep(scenario, replay_attack_rates)

    write_csv(rows)
    plot_outputs(rows)

    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {REPLAY_FIGURE_PATH}")
    print(f"Wrote {TOTAL_BYTES_FIGURE_PATH}")
    print(f"Wrote {OVERHEAD_RATIO_FIGURE_PATH}")
    print(f"Wrote {CPU_FIGURE_PATH}")
    print(f"Wrote {BYTES_PER_PACKET_FIGURE_PATH}")


if __name__ == "__main__":
    main()
