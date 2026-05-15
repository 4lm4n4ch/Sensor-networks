"""Week 13 experiment: WSN design-space exploration and Pareto selection."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from math import ceil, log10
from pathlib import Path
import sys

import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.channel import ChannelConfig, LogDistanceChannel  # noqa: E402
from wsnsim.models.optimization import (  # noqa: E402
    DesignPoint,
    Objective,
    OptimizationResult,
    dominance_counts,
    grid_search,
    pareto_front,
    rank_pareto_candidates,
)
from wsnsim.models.security import SecurityConfig  # noqa: E402


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week13_design_space_optimization.csv"
REPORT_PATH = REPORTS_DIR / "week13_design_space_report.md"
PARETO_ENERGY_FIGURE_PATH = (
    FIGURES_DIR / "week13_pareto_energy_vs_pdr.png"
)
PARETO_LATENCY_FIGURE_PATH = (
    FIGURES_DIR / "week13_pareto_latency_vs_energy.png"
)
DESIGN_SPACE_FIGURE_PATH = FIGURES_DIR / "week13_design_space_scatter.png"


OBJECTIVES = [
    Objective("pdr", "maximize"),
    Objective("energy_per_delivered_packet", "minimize"),
    Objective("latency_mean", "minimize"),
    Objective("total_tx_bytes", "minimize"),
]


@dataclass(frozen=True)
class Week13Scenario:
    """Fixed assumptions for the Week 13 analytic design evaluator."""

    samples_per_node: int = 12
    payload_bytes: int = 48
    route_span_m: float = 100.0
    bitrate_bps: float = 250_000.0
    battery_j_per_node: float = 1_000.0
    tx_energy_per_bit_j_at_25m: float = 50e-9
    rx_energy_per_bit_j: float = 45e-9


def parameter_grid() -> dict[str, list[object]]:
    """Return the deterministic Week 13 design-space grid."""
    return {
        "seed": [2026, 2027],
        "node_count": [20, 35],
        "mac": ["aloha", "csma"],
        "retry_limit": [0, 2, 4],
        "radio_range_m": [25.0, 40.0, 55.0],
        "aggregation_threshold": [0.0, 0.35],
        "security_enabled": [False, True],
    }


def evaluate_design_point(
    design_point: DesignPoint,
    scenario: Week13Scenario | None = None,
) -> dict[str, float]:
    """Evaluate one candidate using deterministic WSN trade-off proxies."""
    resolved = scenario if scenario is not None else Week13Scenario()
    params = design_point.parameters
    seed = int(params["seed"])
    node_count = int(params["node_count"])
    mac = str(params["mac"])
    retry_limit = int(params["retry_limit"])
    radio_range_m = float(params["radio_range_m"])
    aggregation_threshold = float(params["aggregation_threshold"])
    security_enabled = bool(params["security_enabled"])

    security = SecurityConfig(enabled=security_enabled, seed=seed)
    payload_bytes = resolved.payload_bytes + security.overhead_bytes_per_packet
    tx_power_dbm = _tx_power_for_range(radio_range_m)
    link_distance_m = max(5.0, radio_range_m * 0.72)
    channel = LogDistanceChannel(
        ChannelConfig(
            tx_power_dbm=tx_power_dbm,
            shadowing_sigma_db=0.0,
            seed=seed,
        )
    )
    link_prr = channel.calculate_link_stats(
        link_distance_m,
        payload_bytes,
        include_shadowing=False,
    ).prr_logistic

    hop_count = max(1, int(ceil(resolved.route_span_m / radio_range_m)))
    topology_factor = _clamp(0.62 + 0.38 * (radio_range_m / 55.0), 0.0, 1.0)
    contention_load = node_count / 35.0
    aggregation_saving = _clamp(aggregation_threshold * 1.35, 0.0, 0.78)
    offered_load = contention_load * (1.0 - 0.45 * aggregation_saving)
    mac_factor = _mac_delivery_factor(mac, offered_load)

    attempts_allowed = retry_limit + 1
    link_delivery = 1.0 - (1.0 - link_prr) ** attempts_allowed
    pdr = _clamp(
        topology_factor * mac_factor * (link_delivery ** hop_count),
        0.0,
        1.0,
    )

    generated_packets = max(
        1,
        int(round(node_count * resolved.samples_per_node * (1.0 - aggregation_saving))),
    )
    expected_attempts_per_hop = _expected_attempts(link_prr, attempts_allowed)
    data_tx_count = generated_packets * hop_count * expected_attempts_per_hop
    ack_tx_count = data_tx_count * link_prr if retry_limit > 0 else 0.0
    total_tx_bytes = int(round(data_tx_count * payload_bytes + ack_tx_count * 8))
    raw_reference_bytes = (
        node_count
        * resolved.samples_per_node
        * hop_count
        * resolved.payload_bytes
    )
    communication_saving_ratio = 1.0 - (total_tx_bytes / raw_reference_bytes)

    tx_energy_per_bit_j = (
        resolved.tx_energy_per_bit_j_at_25m * (radio_range_m / 25.0) ** 2
    )
    radio_energy_j = (
        total_tx_bytes * 8 * tx_energy_per_bit_j
        + total_tx_bytes * 8 * resolved.rx_energy_per_bit_j * 0.65
    )
    security_cpu_energy_j = (
        total_tx_bytes
        * (
            security.cpu_cost_per_byte_j
            + security.verify_cost_per_byte_j
        )
        if security_enabled
        else 0.0
    )
    total_energy_j = radio_energy_j + security_cpu_energy_j
    delivered_packets = generated_packets * pdr
    energy_per_delivered_packet = total_energy_j / max(delivered_packets, 1.0)

    airtime_s = payload_bytes * 8 / resolved.bitrate_bps
    mac_backoff_s = _mac_latency_overhead(mac, offered_load)
    retry_backoff_s = retry_limit * 0.004 * (1.0 - link_prr)
    security_latency_s = (
        payload_bytes * security.latency_cost_per_byte_s
        if security_enabled
        else 0.0
    )
    latency_mean = hop_count * (
        airtime_s * expected_attempts_per_hop
        + mac_backoff_s
        + retry_backoff_s
        + security_latency_s
    )
    lifetime_proxy = resolved.battery_j_per_node / max(total_energy_j / node_count, 1e-12)

    return {
        "pdr": pdr,
        "latency_mean": latency_mean,
        "energy_per_delivered_packet": energy_per_delivered_packet,
        "total_tx_bytes": float(total_tx_bytes),
        "communication_saving_ratio": communication_saving_ratio,
        "lifetime_proxy": lifetime_proxy,
        "hop_count": float(hop_count),
        "link_prr": link_prr,
        "generated_packets": float(generated_packets),
    }


def run_design_space() -> list[OptimizationResult]:
    """Evaluate the full Week 13 grid."""
    scenario = Week13Scenario()
    return grid_search(
        parameter_grid(),
        lambda point: evaluate_design_point(point, scenario),
    )


def result_to_row(
    result: OptimizationResult,
    *,
    is_pareto: bool,
    dominates_count: int,
    dominated_by_count: int,
    recommendation_rank: int,
) -> dict[str, int | float | str | bool]:
    """Convert one optimization result to a CSV row."""
    params = result.design_point.parameters
    metrics = result.metrics
    return {
        "config_id": result.config_id,
        "seed": int(params["seed"]),
        "node_count": int(params["node_count"]),
        "mac": str(params["mac"]),
        "retry_limit": int(params["retry_limit"]),
        "radio_range_m": float(params["radio_range_m"]),
        "aggregation_threshold": float(params["aggregation_threshold"]),
        "security_enabled": bool(params["security_enabled"]),
        "pdr": float(metrics["pdr"]),
        "latency_mean": float(metrics["latency_mean"]),
        "energy_per_delivered_packet": float(
            metrics["energy_per_delivered_packet"]
        ),
        "total_tx_bytes": int(round(float(metrics["total_tx_bytes"]))),
        "communication_saving_ratio": float(
            metrics["communication_saving_ratio"]
        ),
        "lifetime_proxy": float(metrics["lifetime_proxy"]),
        "hop_count": int(round(float(metrics["hop_count"]))),
        "link_prr": float(metrics["link_prr"]),
        "generated_packets": int(round(float(metrics["generated_packets"]))),
        "is_pareto": is_pareto,
        "dominates_count": dominates_count,
        "dominated_by_count": dominated_by_count,
        "recommendation_rank": recommendation_rank,
    }


def annotate_results(
    results: list[OptimizationResult],
) -> list[dict[str, int | float | str | bool]]:
    """Add Pareto and recommendation fields to result rows."""
    front = pareto_front(results, OBJECTIVES)
    front_ids = {result.config_id for result in front}
    counts = dominance_counts(results, OBJECTIVES)
    ranked = rank_pareto_candidates(results, OBJECTIVES)
    rank_by_id = {
        result.config_id: rank
        for rank, result in enumerate(ranked, start=1)
    }
    return [
        result_to_row(
            result,
            is_pareto=result.config_id in front_ids,
            dominates_count=counts[result.config_id][0],
            dominated_by_count=counts[result.config_id][1],
            recommendation_rank=rank_by_id[result.config_id],
        )
        for result in results
    ]


def write_csv(rows: list[dict[str, int | float | str | bool]]) -> None:
    """Write Week 13 design-space results."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_outputs(rows: list[dict[str, int | float | str | bool]]) -> None:
    """Generate Week 13 Pareto and design-space figures."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _plot_pareto_energy_vs_pdr(rows)
    _plot_latency_vs_energy(rows)
    _plot_design_space_scatter(rows)


def write_report(rows: list[dict[str, int | float | str | bool]]) -> None:
    """Write the Week 13 mini report."""
    pareto_rows = [row for row in rows if bool(row["is_pareto"])]
    recommended = min(rows, key=lambda row: int(row["recommendation_rank"]))
    efficient = min(pareto_rows, key=lambda row: float(row["energy_per_delivered_packet"]))
    reliable = max(pareto_rows, key=lambda row: float(row["pdr"]))
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Week 13 - Design Space and Optimization",
                "",
                "## Goal",
                "",
                "Design-space exploration helps compare WSN configurations "
                "under competing objectives. Here the simulator evaluates a "
                "small deterministic parameter grid and extracts Pareto-"
                "efficient configurations that are not strictly worse than "
                "another candidate on reliability, energy, latency, and bytes.",
                "",
                "## Design variables",
                "",
                "- `node_count`: changes contention and total sensing traffic.",
                "- `mac`: compares ALOHA and CSMA behavior.",
                "- `retry_limit`: changes reliability versus retry overhead.",
                "- `radio_range_m`: changes hop count, link budget, and TX energy.",
                "- `aggregation_threshold`: suppresses redundant readings.",
                "- `security_enabled`: adds authentication bytes, CPU energy, "
                "and processing latency.",
                "",
                "## Objectives",
                "",
                "- Maximize `pdr`.",
                "- Minimize `energy_per_delivered_packet`.",
                "- Minimize `latency_mean`.",
                "- Minimize `total_tx_bytes`.",
                "",
                "## Method",
                "",
                "The experiment uses a deterministic grid with two seeds and "
                f"{len(rows)} total configurations. Each candidate is evaluated with a "
                "lightweight analytic WSN model: channel PRR comes from the "
                "Week 2 log-distance channel, retry behavior follows the Week "
                "7 link-attempt logic, aggregation reduces generated packets, "
                "and Week 10 security settings add byte, CPU-energy, and "
                "latency overhead. Pareto dominance means a candidate is at "
                "least as good on every objective and strictly better on one "
                "objective. Non-dominated candidates form the Pareto front.",
                "",
                "## Results",
                "",
                f"- CSV path: `{CSV_PATH}`",
                f"- Figure: `{PARETO_ENERGY_FIGURE_PATH}`",
                f"- Figure: `{PARETO_LATENCY_FIGURE_PATH}`",
                f"- Figure: `{DESIGN_SPACE_FIGURE_PATH}`",
                f"- Evaluated configurations: `{len(rows)}`",
                f"- Pareto-efficient configurations: `{len(pareto_rows)}`",
                "",
                "## Interpretation",
                "",
                "Energy-efficient configurations use aggregation and avoid "
                "unnecessary security/retry overhead when the channel is "
                "already strong. Reliability-oriented configurations favor "
                "CSMA, more retries, and larger radio range because those "
                "choices improve delivery probability. The balanced "
                "recommendation is "
                f"`{recommended['config_id']}`: MAC `{recommended['mac']}`, "
                f"retry limit `{recommended['retry_limit']}`, range "
                f"`{recommended['radio_range_m']}` m, aggregation threshold "
                f"`{recommended['aggregation_threshold']}`, security "
                f"`{recommended['security_enabled']}`. It is recommended "
                "because it lies on the Pareto front and has the best average "
                "normalized score across the implemented objectives.",
                "",
                f"The lowest-energy Pareto point is `{efficient['config_id']}` "
                f"with `{float(efficient['energy_per_delivered_packet']):.6f}` "
                "J per delivered packet. The highest-reliability Pareto point "
                f"is `{reliable['config_id']}` with PDR "
                f"`{float(reliable['pdr']):.3f}`.",
                "",
                "## Reproducibility",
                "",
                "```bash",
                ".venv/bin/python -m pytest -q tests/test_optimization.py",
                ".venv/bin/python experiments/week13_design_space_optimization.py",
                "```",
                "",
                "## Known limitations",
                "",
                "- The parameter grid is intentionally small.",
                "- The evaluator is analytic and simplified rather than a full "
                "packet-level end-to-end simulation.",
                "- Stochastic repetition is limited to two deterministic seeds.",
                "- No advanced optimizer or metaheuristic is used.",
                "- The model is not calibrated against a real deployment.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _plot_pareto_energy_vs_pdr(
    rows: list[dict[str, int | float | str | bool]],
) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    _scatter_pareto(
        ax,
        rows,
        x_key="energy_per_delivered_packet",
        y_key="pdr",
    )
    ax.set_title("Week 13 Pareto front: energy vs PDR")
    ax.set_xlabel("Energy per delivered packet (J)")
    ax.set_ylabel("Packet delivery ratio")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(PARETO_ENERGY_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_latency_vs_energy(
    rows: list[dict[str, int | float | str | bool]],
) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    _scatter_pareto(
        ax,
        rows,
        x_key="latency_mean",
        y_key="energy_per_delivered_packet",
    )
    ax.set_title("Week 13 Pareto front: latency vs energy")
    ax.set_xlabel("Mean latency (s)")
    ax.set_ylabel("Energy per delivered packet (J)")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(PARETO_LATENCY_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_design_space_scatter(
    rows: list[dict[str, int | float | str | bool]],
) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for mac, color in [("aloha", "#d95f02"), ("csma", "#1b9e77")]:
        subset = [row for row in rows if row["mac"] == mac]
        ax.scatter(
            [float(row["total_tx_bytes"]) for row in subset],
            [float(row["pdr"]) for row in subset],
            c=color,
            s=[
                28 + 28 * float(row["aggregation_threshold"])
                for row in subset
            ],
            alpha=0.68,
            label=mac.upper(),
        )
    pareto_subset = [row for row in rows if bool(row["is_pareto"])]
    ax.scatter(
        [float(row["total_tx_bytes"]) for row in pareto_subset],
        [float(row["pdr"]) for row in pareto_subset],
        facecolors="none",
        edgecolors="#222222",
        linewidths=1.1,
        s=72,
        label="Pareto",
    )
    ax.set_title("Week 13 design-space scatter")
    ax.set_xlabel("Total transmitted bytes")
    ax.set_ylabel("Packet delivery ratio")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(DESIGN_SPACE_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _scatter_pareto(
    ax: plt.Axes,
    rows: list[dict[str, int | float | str | bool]],
    *,
    x_key: str,
    y_key: str,
) -> None:
    non_pareto = [row for row in rows if not bool(row["is_pareto"])]
    pareto = [row for row in rows if bool(row["is_pareto"])]
    ax.scatter(
        [float(row[x_key]) for row in non_pareto],
        [float(row[y_key]) for row in non_pareto],
        color="#9aa0a6",
        s=30,
        alpha=0.55,
        label="Dominated",
    )
    ax.scatter(
        [float(row[x_key]) for row in pareto],
        [float(row[y_key]) for row in pareto],
        color="#c0392b",
        s=48,
        alpha=0.88,
        label="Pareto",
    )


def _expected_attempts(link_prr: float, attempts_allowed: int) -> float:
    failure = 1.0 - link_prr
    return sum(failure ** attempt for attempt in range(attempts_allowed))


def _mac_delivery_factor(mac: str, offered_load: float) -> float:
    if mac == "csma":
        return _clamp(0.985 - 0.055 * offered_load, 0.70, 0.99)
    if mac == "aloha":
        return _clamp(0.93 - 0.16 * offered_load, 0.45, 0.94)
    raise ValueError("mac must be 'aloha' or 'csma'")


def _mac_latency_overhead(mac: str, offered_load: float) -> float:
    if mac == "csma":
        return 0.0035 + 0.004 * offered_load
    if mac == "aloha":
        return 0.0015 + 0.008 * offered_load
    raise ValueError("mac must be 'aloha' or 'csma'")


def _tx_power_for_range(radio_range_m: float) -> float:
    """Return a simple range-dependent TX power proxy in dBm."""
    return 2.0 + 14.0 * log10(radio_range_m / 25.0)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def main() -> None:
    """Run the Week 13 design-space optimization workflow."""
    results = run_design_space()
    rows = annotate_results(results)
    write_csv(rows)
    plot_outputs(rows)
    write_report(rows)

    pareto_rows = [row for row in rows if bool(row["is_pareto"])]
    recommended = min(rows, key=lambda row: int(row["recommendation_rank"]))
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {PARETO_ENERGY_FIGURE_PATH}")
    print(f"Wrote {PARETO_LATENCY_FIGURE_PATH}")
    print(f"Wrote {DESIGN_SPACE_FIGURE_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(
        "Summary: evaluated "
        f"{len(rows)} configurations; {len(pareto_rows)} are Pareto-efficient. "
        f"Recommended {recommended['config_id']} with "
        f"PDR={float(recommended['pdr']):.3f}, "
        "energy/delivered="
        f"{float(recommended['energy_per_delivered_packet']):.6f} J, "
        f"latency={float(recommended['latency_mean']):.4f} s."
    )


if __name__ == "__main__":
    main()
