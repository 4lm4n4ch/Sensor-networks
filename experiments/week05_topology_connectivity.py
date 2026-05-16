"""Week 5 experiment: topology deployment and connectivity graphs.

The experiment saves one topology graph figure, one range-sweep figure, and a
CSV with average degree and sink reachability metrics.
"""

from __future__ import annotations

import csv
from pathlib import Path
import sys

import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.topology import Node, Topology, TopologyConfig


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week05_topology_connectivity.csv"
TOPOLOGY_FIGURE_PATH = FIGURES_DIR / "week05_topology_graph.png"
RANGE_FIGURE_PATH = FIGURES_DIR / "week05_connectivity_vs_range.png"


def plot_topology_graph(
    topology: Topology,
    *,
    communication_range_m: float,
    seed: int | None,
) -> None:
    """Plot node positions with current neighbor links."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 7))
    plotted_link_label = False
    for source_id, neighbors in topology.adjacency().items():
        source = topology.nodes[source_id]
        for target_id in sorted(neighbors):
            if target_id <= source_id:
                continue
            target = topology.nodes[target_id]
            ax.plot(
                [source.x_m, target.x_m],
                [source.y_m, target.y_m],
                color="0.72",
                linewidth=0.8,
                label="Neighbor link" if not plotted_link_label else None,
                zorder=1,
            )
            plotted_link_label = True

    sensors = [node for node in topology.node_list() if node.role != "sink"]
    sink = topology.nodes[topology.sink_id] if topology.sink_id is not None else None
    _scatter_nodes(ax, sensors, label="Sensor nodes", color="#377eb8", marker="o")
    if sink is not None:
        ax.scatter(
            [sink.x_m],
            [sink.y_m],
            s=160,
            color="#e41a1c",
            marker="*",
            edgecolors="black",
            linewidths=0.8,
            label="Sink",
            zorder=3,
        )

    ax.set_title(
        "Week 5 topology graph "
        f"(seed={seed}, range={communication_range_m:.0f} m)"
    )
    ax.set_xlabel("X position (m)")
    ax.set_ylabel("Y position (m)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(TOPOLOGY_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _scatter_nodes(
    ax: plt.Axes,
    nodes: list[Node],
    *,
    label: str,
    color: str,
    marker: str,
) -> None:
    """Scatter plot a list of nodes if non-empty."""
    if not nodes:
        return
    ax.scatter(
        [node.x_m for node in nodes],
        [node.y_m for node in nodes],
        s=42,
        color=color,
        marker=marker,
        edgecolors="white",
        linewidths=0.4,
        label=label,
        zorder=2,
    )


def sweep_ranges(
    topology: Topology,
    communication_ranges_m: list[float],
) -> list[dict[str, float | bool]]:
    """Evaluate graph metrics across communication range thresholds."""
    rows: list[dict[str, float | bool]] = []
    for communication_range_m in communication_ranges_m:
        topology.build_distance_graph(communication_range_m)
        rows.append(
            {
                "communication_range_m": communication_range_m,
                "average_degree": topology.average_degree(),
                "sink_reachability_ratio": topology.sink_reachability_ratio(),
                "all_nodes_reach_sink": topology.all_nodes_can_reach_sink(),
            }
        )
    return rows


def write_csv(rows: list[dict[str, float | bool]]) -> None:
    """Write range-sweep results to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "communication_range_m",
        "average_degree",
        "sink_reachability_ratio",
        "all_nodes_reach_sink",
    ]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_range_sweep(rows: list[dict[str, float | bool]], *, seed: int | None) -> None:
    """Plot average degree and sink reachability vs communication range."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    ranges_m = [float(row["communication_range_m"]) for row in rows]
    average_degrees = [float(row["average_degree"]) for row in rows]
    sink_ratios = [float(row["sink_reachability_ratio"]) for row in rows]

    fig, ax_degree = plt.subplots(figsize=(9, 5))
    degree_line = ax_degree.plot(
        ranges_m,
        average_degrees,
        marker="o",
        color="#377eb8",
        label="Average degree",
    )
    ax_degree.set_xlabel("Communication range (m)")
    ax_degree.set_ylabel("Average node degree")
    ax_degree.grid(True, alpha=0.3)

    ax_ratio = ax_degree.twinx()
    ratio_line = ax_ratio.plot(
        ranges_m,
        sink_ratios,
        marker="s",
        color="#4daf4a",
        label="Sink reachability ratio",
    )
    ax_ratio.set_ylabel("Nodes reachable from sink (fraction)")
    ax_ratio.set_ylim(0.0, 1.05)

    lines = degree_line + ratio_line
    labels = [line.get_label() for line in lines]
    ax_degree.legend(lines, labels, loc="lower right")
    ax_degree.set_title(
        "Week 5 connectivity vs communication range "
        f"(seed={seed}, 100 m x 100 m area)"
    )

    fig.tight_layout()
    fig.savefig(RANGE_FIGURE_PATH, dpi=150)
    plt.close(fig)


def main() -> None:
    """Run the Week 5 topology connectivity experiment."""
    seed = 42069
    graph_range_m = 28.0
    config = TopologyConfig(
        node_count=40,
        area_width_m=100.0,
        area_height_m=100.0,
        seed=seed,
        sink_position="center",
        communication_range_m=graph_range_m,
    )
    topology = Topology.random_uniform(config)

    topology.build_distance_graph()
    plot_topology_graph(
        topology,
        communication_range_m=graph_range_m,
        seed=seed,
    )

    communication_ranges_m = [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0]
    rows = sweep_ranges(topology, communication_ranges_m)
    write_csv(rows)
    plot_range_sweep(rows, seed=seed)

    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {TOPOLOGY_FIGURE_PATH}")
    print(f"Wrote {RANGE_FIGURE_PATH}")


if __name__ == "__main__":
    main()
