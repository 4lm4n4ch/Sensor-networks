"""Week 9 experiment: data aggregation and compression trade-offs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.aggregation import (  # noqa: E402
    AggregationConfig,
    AggregationResult,
    SensorReading,
    delta_suppression,
    generate_synthetic_readings,
    raw_forwarding,
    tree_aggregation,
)
from wsnsim.models.topology import Topology, TopologyConfig  # noqa: E402


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week09_aggregation_compression.csv"
FIGURE_PATH = FIGURES_DIR / "week09_aggregation_compression_tradeoff.png"


@dataclass(frozen=True)
class ExperimentScenario:
    """Fixed Week 9 aggregation scenario."""

    seed: int = 2026
    node_count: int = 25
    area_width_m: float = 100.0
    area_height_m: float = 100.0
    communication_range_m: float = 36.0
    sample_count: int = 60
    sample_period_s: float = 1.0
    noise_std: float = 0.05
    anomaly_time_s: float = 36.0

    @property
    def caption(self) -> str:
        """Return a compact caption for generated figures."""
        return (
            f"seed={self.seed}, N={self.node_count}, topology=grid, "
            f"samples={self.sample_count}, range={self.communication_range_m:g} m, "
            "cost counted as BFS sink-tree link transmissions"
        )


def build_topology(scenario: ExperimentScenario) -> Topology:
    """Build the deterministic grid topology used by the experiment."""
    config = TopologyConfig(
        node_count=scenario.node_count,
        area_width_m=scenario.area_width_m,
        area_height_m=scenario.area_height_m,
        seed=scenario.seed,
        sink_position="center",
        communication_range_m=scenario.communication_range_m,
    )
    topology = Topology.grid(config)
    topology.build_distance_graph()
    return topology


def make_readings(
    topology: Topology,
    scenario: ExperimentScenario,
) -> list[SensorReading]:
    """Generate smooth synthetic sensor readings for all non-sink nodes."""
    if topology.sink_id is None:
        raise ValueError("topology must have a sink")

    node_ids = [
        node.id
        for node in topology.node_list()
        if node.id != topology.sink_id
    ]
    timestamps_s = [
        index * scenario.sample_period_s
        for index in range(scenario.sample_count)
    ]
    return generate_synthetic_readings(
        node_ids,
        timestamps_s,
        seed=scenario.seed,
        noise_std=scenario.noise_std,
        anomaly_time_s=scenario.anomaly_time_s,
    )


def row_for_result(
    *,
    protocol: str,
    scenario: ExperimentScenario,
    topology: Topology,
    config: AggregationConfig,
    result: AggregationResult,
    delta_threshold: float | str,
) -> dict[str, float | int | str]:
    """Convert one strategy result to a CSV row."""
    return {
        "protocol": protocol,
        "seed": scenario.seed,
        "node_count": scenario.node_count,
        "topology": "grid",
        "communication_range_m": scenario.communication_range_m,
        "average_degree": topology.average_degree(),
        "sink_reachability_ratio": topology.sink_reachability_ratio(),
        "sample_count": scenario.sample_count,
        "aggregation_method": config.aggregation_method,
        "delta_threshold": delta_threshold,
        "quantization_step": config.quantization_step,
        "raw_packet_bytes": config.raw_packet_bytes,
        "aggregate_packet_bytes": config.aggregate_packet_bytes,
        "aggregate_value": result.aggregate_value,
        "transmitted_packets": result.transmitted_packets,
        "transmitted_bytes": result.transmitted_bytes,
        "mse": result.mse,
        "mae": result.mae,
        "compression_ratio": result.compression_ratio,
        "communication_saving_ratio": result.communication_saving_ratio,
    }


def run_comparison(
    scenario: ExperimentScenario,
    delta_thresholds: list[float],
) -> list[dict[str, float | int | str]]:
    """Compare raw forwarding, tree aggregation, and delta suppression."""
    topology = build_topology(scenario)
    samples = make_readings(topology, scenario)
    base_config = AggregationConfig(
        aggregation_method="average",
        delta_threshold=0.0,
        quantization_step=0.0,
        seed=scenario.seed,
        reading_payload_bytes=8,
        aggregate_payload_bytes=8,
        packet_overhead_bytes=16,
    )

    rows: list[dict[str, float | int | str]] = []
    raw_result = raw_forwarding(samples, base_config, topology=topology)
    rows.append(
        row_for_result(
            protocol="Raw forwarding",
            scenario=scenario,
            topology=topology,
            config=base_config,
            result=raw_result,
            delta_threshold="",
        )
    )

    tree_result = tree_aggregation(samples, base_config, topology=topology)
    rows.append(
        row_for_result(
            protocol="Tree average aggregation",
            scenario=scenario,
            topology=topology,
            config=base_config,
            result=tree_result,
            delta_threshold="",
        )
    )

    for delta_threshold in delta_thresholds:
        delta_config = AggregationConfig(
            aggregation_method="average",
            delta_threshold=delta_threshold,
            quantization_step=0.0,
            seed=scenario.seed,
            reading_payload_bytes=8,
            aggregate_payload_bytes=8,
            packet_overhead_bytes=16,
        )
        delta_result = delta_suppression(
            samples,
            delta_config,
            topology=topology,
        )
        rows.append(
            row_for_result(
                protocol="Delta suppression",
                scenario=scenario,
                topology=topology,
                config=delta_config,
                result=delta_result,
                delta_threshold=delta_threshold,
            )
        )

    return rows


def write_csv(rows: list[dict[str, float | int | str]]) -> None:
    """Write strategy comparison metrics to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_outputs(
    rows: list[dict[str, float | int | str]],
    scenario: ExperimentScenario,
) -> None:
    """Plot communication savings and reconstruction error."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    delta_rows = [
        row
        for row in rows
        if row["protocol"] == "Delta suppression"
    ]

    thresholds = [float(row["delta_threshold"]) for row in delta_rows]
    savings = [float(row["communication_saving_ratio"]) for row in delta_rows]
    mse_values = [float(row["mse"]) for row in delta_rows]
    tree_row = next(row for row in rows if row["protocol"] == "Tree average aggregation")

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    axes[0].plot(
        thresholds,
        savings,
        color="#2b6cb0",
        marker="o",
        linewidth=1.8,
        label="Delta suppression",
    )
    axes[0].axhline(
        float(tree_row["communication_saving_ratio"]),
        color="#4daf4a",
        linestyle="--",
        linewidth=1.5,
        label="Tree aggregation",
    )
    axes[0].set_title("Week 9 communication saving")
    axes[0].set_xlabel("Delta threshold")
    axes[0].set_ylabel("Saving ratio")
    axes[0].set_ylim(0.0, 1.05)
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="best")

    axes[1].plot(
        thresholds,
        mse_values,
        color="#e41a1c",
        marker="s",
        linewidth=1.8,
    )
    axes[1].set_title("Delta reconstruction error")
    axes[1].set_xlabel("Delta threshold")
    axes[1].set_ylabel("MSE")
    axes[1].grid(True, alpha=0.3)

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


def main() -> None:
    """Run the Week 9 aggregation/compression comparison."""
    scenario = ExperimentScenario()
    delta_thresholds = [0.0, 0.1, 0.25, 0.5, 1.0, 2.0]
    rows = run_comparison(scenario, delta_thresholds)

    write_csv(rows)
    plot_outputs(rows, scenario)

    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {FIGURE_PATH}")


if __name__ == "__main__":
    main()
