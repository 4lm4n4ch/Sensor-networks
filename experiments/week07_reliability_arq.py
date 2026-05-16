"""Week 7 experiment: ACK/retry reliability trade-off sweep."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.channel import ChannelConfig, LogDistanceChannel  # noqa: E402
from wsnsim.models.reliability import (  # noqa: E402
    LinkReliabilityARQ,
    ReliabilityConfig,
    ReliabilityMetrics,
)
from wsnsim.sim import Scheduler  # noqa: E402


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week07_reliability_arq.csv"
FIGURE_PATH = FIGURES_DIR / "week07_reliability_arq_tradeoff.png"


@dataclass(frozen=True)
class ExperimentScenario:
    """Fixed Week 7 link scenario except retry limit."""

    seed: int = 42069
    packet_count: int = 200
    source_id: int = 1
    destination_id: int = 2
    payload_bytes: int = 64
    distance_m: float = 70.0
    packet_period_s: float = 0.1
    ack_timeout_s: float = 0.02
    base_backoff_s: float = 0.005
    max_backoff_s: float = 0.08
    backoff_multiplier: float = 2.0

    @property
    def caption(self) -> str:
        """Return a compact caption for generated figures."""
        return (
            f"seed={self.seed}, packets={self.packet_count}, "
            f"payload={self.payload_bytes} B, distance={self.distance_m:g} m, "
            "ACK enabled, log-distance channel, per-bit energy model"
        )


def run_retry_limit(
    scenario: ExperimentScenario,
    retry_limit: int,
) -> ReliabilityMetrics:
    """Run the same link scenario for one retry limit."""
    scheduler = Scheduler(seed=scenario.seed)
    channel = LogDistanceChannel(
        ChannelConfig(
            seed=scenario.seed,
            shadowing_sigma_db=0.0,
        )
    )
    config = ReliabilityConfig(
        ack_enabled=True,
        retry_limit=retry_limit,
        ack_timeout_s=scenario.ack_timeout_s,
        base_backoff_s=scenario.base_backoff_s,
        max_backoff_s=scenario.max_backoff_s,
        backoff_multiplier=scenario.backoff_multiplier,
        seed=scenario.seed,
        ack_size_bytes=8,
        include_shadowing=False,
    )
    arq = LinkReliabilityARQ(
        scheduler=scheduler,
        config=config,
        channel=channel,
        distance_m=scenario.distance_m,
    )

    for packet_index in range(scenario.packet_count):
        arq.send_packet(
            packet_id=f"p{packet_index}",
            source_id=scenario.source_id,
            destination_id=scenario.destination_id,
            size_bytes=scenario.payload_bytes,
            at_time_s=packet_index * scenario.packet_period_s,
        )
    scheduler.run()
    return arq.metrics


def row_for_metrics(
    scenario: ExperimentScenario,
    retry_limit: int,
    metrics: ReliabilityMetrics,
) -> dict[str, float | int | str]:
    """Convert metrics to one CSV row."""
    return {
        "protocol": "ACK-ARQ",
        "seed": scenario.seed,
        "packet_count": scenario.packet_count,
        "payload_bytes": scenario.payload_bytes,
        "distance_m": scenario.distance_m,
        "retry_limit": retry_limit,
        "ack_timeout_s": scenario.ack_timeout_s,
        "base_backoff_s": scenario.base_backoff_s,
        "generated_packets": metrics.generated_packets,
        "delivered_packets": metrics.delivered_packets,
        "failed_packets": metrics.failed_packets,
        "total_attempts": metrics.total_attempts,
        "total_retries": metrics.total_retries,
        "ack_packets": metrics.ack_packets,
        "timeout_count": metrics.timeout_count,
        "pdr": metrics.pdr,
        "average_attempts_per_packet": metrics.average_attempts_per_packet,
        "average_latency_s": metrics.average_latency_s,
        "total_energy_j": metrics.total_energy_j,
        "energy_per_generated_packet_j": (
            metrics.total_energy_j / metrics.generated_packets
            if metrics.generated_packets
            else 0.0
        ),
        "energy_per_delivered_packet_j": (
            metrics.total_energy_j / metrics.delivered_packets
            if metrics.delivered_packets
            else float("inf")
        ),
    }


def write_csv(rows: list[dict[str, float | int | str]]) -> None:
    """Write retry-limit sweep metrics to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_outputs(
    rows: list[dict[str, float | int | str]],
    scenario: ExperimentScenario,
) -> None:
    """Plot PDR, latency, and energy versus retry limit."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    retry_limits = [int(row["retry_limit"]) for row in rows]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))
    plot_specs = [
        ("pdr", "Packet delivery ratio", "Week 7 reliability PDR"),
        ("average_latency_s", "Average latency (s)", "Latency cost"),
        ("energy_per_generated_packet_j", "Energy / generated packet (J)", "Energy cost"),
    ]
    for ax, (metric_key, ylabel, title) in zip(axes, plot_specs):
        values = [float(row[metric_key]) for row in rows]
        ax.plot(
            retry_limits,
            values,
            color="#2b6cb0",
            marker="o",
            linewidth=1.8,
            markersize=5,
        )
        ax.set_title(title)
        ax.set_xlabel("Retry limit")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        if metric_key == "pdr":
            ax.set_ylim(0.0, 1.05)

    fig.text(
        0.5,
        -0.02,
        scenario.caption,
        ha="center",
        va="top",
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(FIGURE_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)


def run_sweep(
    scenario: ExperimentScenario,
    retry_limits: list[int],
) -> list[dict[str, float | int | str]]:
    """Run the retry-limit sweep."""
    rows: list[dict[str, float | int | str]] = []
    for retry_limit in retry_limits:
        metrics = run_retry_limit(scenario, retry_limit)
        rows.append(row_for_metrics(scenario, retry_limit, metrics))
    return rows


def main() -> None:
    """Run the Week 7 reliability experiment."""
    scenario = ExperimentScenario()
    retry_limits = [0, 1, 2, 3, 5]
    rows = run_sweep(scenario, retry_limits)

    write_csv(rows)
    plot_outputs(rows, scenario)

    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {FIGURE_PATH}")


if __name__ == "__main__":
    main()
