"""Week 6 experiment: compare flooding and BFS sink-tree routing."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.routing import (  # noqa: E402
    FloodingRouting,
    RoutingConfig,
    RoutingMetrics,
    RoutingPacket,
    SinkTreeRouting,
)
from wsnsim.models.topology import Topology, TopologyConfig  # noqa: E402


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week06_routing_compare.csv"
PDR_FIGURE_PATH = FIGURES_DIR / "week06_routing_pdr.png"
LATENCY_FIGURE_PATH = FIGURES_DIR / "week06_routing_latency.png"
ENERGY_FIGURE_PATH = FIGURES_DIR / "week06_routing_energy_per_bit.png"


@dataclass(frozen=True)
class ExperimentScenario:
    """Fixed Week 6 comparison parameters except communication range."""

    seed: int = 2026
    node_count: int = 25
    area_width_m: float = 100.0
    area_height_m: float = 100.0
    payload_bytes: int = 64
    ttl: int = 10
    hop_delay_s: float = 0.01

    @property
    def payload_bits(self) -> int:
        """Return payload size in bits."""
        return self.payload_bytes * 8

    @property
    def caption(self) -> str:
        """Return a compact caption for generated figures."""
        return (
            f"seed={self.seed}, N={self.node_count}, topology=random_uniform, "
            f"payload={self.payload_bytes} B, TTL={self.ttl}, "
            "deterministic neighbor-link delivery"
        )


def build_topology(
    scenario: ExperimentScenario,
    communication_range_m: float,
) -> Topology:
    """Build the shared deterministic topology."""
    config = TopologyConfig(
        node_count=scenario.node_count,
        area_width_m=scenario.area_width_m,
        area_height_m=scenario.area_height_m,
        seed=scenario.seed,
        sink_position="center",
        communication_range_m=communication_range_m,
    )
    topology = Topology.random_uniform(config)
    topology.build_distance_graph()
    return topology


def make_traffic(
    topology: Topology,
    scenario: ExperimentScenario,
) -> list[RoutingPacket]:
    """Create one data packet from each sensor to the sink."""
    sink_id = topology.sink_id
    if sink_id is None:
        raise ValueError("topology must have a sink")

    packets: list[RoutingPacket] = []
    for node in topology.node_list():
        if node.id == sink_id:
            continue
        packets.append(
            RoutingPacket(
                packet_id=f"sensor-{node.id}-sample-0",
                source_id=node.id,
                destination_id=sink_id,
                current_node_id=node.id,
                previous_node_id=None,
                created_time_s=0.0,
                ttl=scenario.ttl,
                payload_bits=scenario.payload_bits,
            )
        )
    return packets


def run_protocols(
    topology: Topology,
    packets: list[RoutingPacket],
    scenario: ExperimentScenario,
    communication_range_m: float,
) -> list[dict[str, float | int | str]]:
    """Run both routing baselines on the same topology and traffic."""
    config = RoutingConfig(
        seed=scenario.seed,
        hop_delay_s=scenario.hop_delay_s,
        use_link_success=False,
    )
    protocols: list[tuple[str, object]] = [
        ("Flooding", FloodingRouting(topology, config=config)),
        ("Sink-tree BFS", SinkTreeRouting(topology, config=config)),
    ]

    rows: list[dict[str, float | int | str]] = []
    for protocol_name, protocol in protocols:
        for packet in packets:
            protocol.route_packet(packet)
        metrics = protocol.metrics
        rows.append(
            metrics_row(
                protocol_name,
                metrics,
                scenario,
                topology,
                communication_range_m,
            )
        )
    return rows


def metrics_row(
    protocol_name: str,
    metrics: RoutingMetrics,
    scenario: ExperimentScenario,
    topology: Topology,
    communication_range_m: float,
) -> dict[str, float | int | str]:
    """Convert metrics to one CSV row."""
    return {
        "protocol": protocol_name,
        "seed": scenario.seed,
        "node_count": scenario.node_count,
        "topology": "random_uniform",
        "communication_range_m": communication_range_m,
        "average_degree": topology.average_degree(),
        "sink_reachability_ratio": topology.sink_reachability_ratio(),
        "payload_bytes": scenario.payload_bytes,
        "ttl": scenario.ttl,
        "generated_packets": metrics.generated_packets,
        "delivered_packets": metrics.delivered_packets,
        "dropped_packets": metrics.dropped_packets,
        "duplicate_packets": metrics.duplicate_packets,
        "control_overhead_packets": metrics.control_overhead_packets,
        "pdr": metrics.pdr,
        "average_latency_s": metrics.average_latency_s,
        "average_hop_count": metrics.average_hop_count,
        "total_energy_j": metrics.total_energy_j,
        "energy_per_delivered_bit_j": metrics.energy_per_delivered_bit_j,
        "energy_per_generated_bit_j": metrics.energy_per_generated_bit_j,
    }


def write_csv(rows: list[dict[str, float | int | str]]) -> None:
    """Write comparison metrics to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_metric(
    rows: list[dict[str, float | int | str]],
    *,
    metric_key: str,
    ylabel: str,
    title: str,
    output_path: Path,
    scenario: ExperimentScenario,
    log_y: bool = False,
) -> None:
    """Create a communication-range sweep plot for one routing metric."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    styles = {
        "Flooding": {"color": "#377eb8", "marker": "o", "linestyle": "-"},
        "Sink-tree BFS": {"color": "#4daf4a", "marker": "s", "linestyle": "--"},
    }
    for protocol_name, style in styles.items():
        protocol_rows = sorted(
            [row for row in rows if row["protocol"] == protocol_name],
            key=lambda row: float(row["communication_range_m"]),
        )
        ranges_m = [
            float(row["communication_range_m"])
            for row in protocol_rows
        ]
        values = [float(row[metric_key]) for row in protocol_rows]
        ax.plot(
            ranges_m,
            values,
            linewidth=1.8,
            markersize=5,
            label=protocol_name,
            **style,
        )

    ax.set_title(title)
    ax.set_xlabel("Communication range (m)")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    if metric_key == "pdr":
        ax.set_ylim(0.0, 1.05)
    if log_y:
        ax.set_yscale("log")
    ax.legend(loc="best")
    ax.text(
        0.5,
        -0.24,
        scenario.caption,
        ha="center",
        va="top",
        transform=ax.transAxes,
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_outputs(
    rows: list[dict[str, float | int | str]],
    scenario: ExperimentScenario,
) -> None:
    """Generate all Week 6 comparison plots."""
    plot_metric(
        rows,
        metric_key="pdr",
        ylabel="Packet delivery ratio",
        title="Week 6 routing PDR",
        output_path=PDR_FIGURE_PATH,
        scenario=scenario,
    )
    plot_metric(
        rows,
        metric_key="average_latency_s",
        ylabel="Average latency (s)",
        title="Week 6 routing latency",
        output_path=LATENCY_FIGURE_PATH,
        scenario=scenario,
    )
    plot_metric(
        rows,
        metric_key="energy_per_delivered_bit_j",
        ylabel="Energy per delivered bit (J/bit)",
        title="Week 6 routing energy per delivered bit",
        output_path=ENERGY_FIGURE_PATH,
        scenario=scenario,
        log_y=True,
    )


def run_sweep(
    scenario: ExperimentScenario,
    communication_ranges_m: list[float],
) -> list[dict[str, float | int | str]]:
    """Run both protocols for every communication range in the sweep."""
    rows: list[dict[str, float | int | str]] = []
    for communication_range_m in communication_ranges_m:
        topology = build_topology(scenario, communication_range_m)
        packets = make_traffic(topology, scenario)
        rows.extend(
            run_protocols(
                topology,
                packets,
                scenario,
                communication_range_m,
            )
        )
    return rows


def main() -> None:
    """Run the Week 6 routing comparison experiment."""
    scenario = ExperimentScenario()
    communication_ranges_m = [15, 20, 25, 30, 35, 40, 45, 50, 60]
    rows = run_sweep(scenario, communication_ranges_m)

    write_csv(rows)
    plot_outputs(rows, scenario)

    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {PDR_FIGURE_PATH}")
    print(f"Wrote {LATENCY_FIGURE_PATH}")
    print(f"Wrote {ENERGY_FIGURE_PATH}")


if __name__ == "__main__":
    main()
