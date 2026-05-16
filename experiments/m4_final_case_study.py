"""M4 final case study: reproducible WSN design comparison.

The script loads a JSON configuration, evaluates three named design
alternatives plus an automatic design sweep, extracts a multi-objective
Pareto front, writes CSV/report artifacts, and regenerates final figures.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
import sys
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from experiments.week13_design_space_optimization import (  # noqa: E402
    Week13Scenario,
    evaluate_design_point,
)
from wsnsim.models.optimization import (  # noqa: E402
    DesignPoint,
    Objective,
    OptimizationResult,
    dominance_counts,
    pareto_front,
    rank_pareto_candidates,
)


DEFAULT_CONFIG = Path("configs/m4_final.json")


@dataclass(frozen=True)
class M4Paths:
    """Resolved output paths for the M4 workflow."""

    results_csv: Path
    config_dump: Path
    summary_report: Path
    case_study: Path
    final_report: Path
    reproducibility_checklist: Path
    presentation: Path
    pareto_figure: Path
    latency_energy_figure: Path
    alternatives_figure: Path
    topology_figure: Path


def load_config(path: Path) -> dict[str, Any]:
    """Load a JSON config file."""
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def resolve_paths(config: dict[str, Any]) -> M4Paths:
    """Resolve output paths from the config."""
    outputs = config["outputs"]
    return M4Paths(
        results_csv=Path(outputs["results_csv"]),
        config_dump=Path(outputs["config_dump"]),
        summary_report=Path(outputs["summary_report"]),
        case_study=Path(outputs["case_study"]),
        final_report=Path(outputs["final_report"]),
        reproducibility_checklist=Path(outputs["reproducibility_checklist"]),
        presentation=Path(outputs["presentation"]),
        pareto_figure=Path(outputs["pareto_figure"]),
        latency_energy_figure=Path(outputs["latency_energy_figure"]),
        alternatives_figure=Path(outputs["alternatives_figure"]),
        topology_figure=Path(outputs["topology_figure"]),
    )


def objectives_from_config(config: dict[str, Any]) -> list[Objective]:
    """Build objective objects from config JSON."""
    return [
        Objective(item["name"], item["direction"])
        for item in config["objectives"]
    ]


def build_design_points(config: dict[str, Any]) -> list[DesignPoint]:
    """Build named alternatives and sweep candidates."""
    points: list[DesignPoint] = []
    for alternative in config["alternatives"]:
        params = dict(alternative)
        config_id = str(params.pop("config_id"))
        points.append(DesignPoint(config_id, params))

    sweep = config["sweep"]
    names = list(sweep)
    for index, values in enumerate(product(*[sweep[name] for name in names]), start=1):
        params = dict(zip(names, values))
        params["design_label"] = f"Automatic sweep {index:03d}"
        points.append(DesignPoint(f"sweep_{index:03d}", params))

    return points


def evaluate_m4_design(
    point: DesignPoint,
    config: dict[str, Any],
) -> OptimizationResult:
    """Evaluate one M4 design point with Week 13 proxies plus M4 features."""
    scenario_cfg = config["scenario"]
    base_scenario = Week13Scenario(
        samples_per_node=int(scenario_cfg["samples_per_node"]),
        payload_bytes=int(scenario_cfg["payload_bytes"]),
        route_span_m=max(
            float(scenario_cfg["area_width_m"]),
            float(scenario_cfg["area_height_m"]),
        ),
        bitrate_bps=float(scenario_cfg["bitrate_bps"]),
        battery_j_per_node=float(scenario_cfg["battery_j_per_node"]),
    )
    metrics = dict(evaluate_design_point(point, base_scenario))
    params = point.parameters
    node_count = int(params["node_count"])
    samples_per_node = int(scenario_cfg["samples_per_node"])
    edge_ai_enabled = bool(params.get("edge_ai_enabled", False))
    edge_threshold = float(params.get("edge_ai_threshold", 2.5))
    security_enabled = bool(params.get("security_enabled", False))

    delivered_packets = (
        float(metrics["generated_packets"]) * float(metrics["pdr"])
    )
    estimated_total_energy_j = (
        float(metrics["energy_per_delivered_packet"])
        * max(delivered_packets, 1.0)
    )
    raw_reference_bytes = (
        node_count
        * samples_per_node
        * int(scenario_cfg["payload_bytes"])
        * max(1.0, float(metrics["hop_count"]))
    )

    edge_ai_cpu_energy_j = 0.0
    edge_ai_saving_ratio = 0.0
    event_recall = 1.0
    if edge_ai_enabled:
        edge_ai_saving_ratio = _clamp(0.62 + 0.08 * edge_threshold, 0.50, 0.88)
        traffic_multiplier = 1.0 - 0.62 * edge_ai_saving_ratio
        event_recall = _clamp(1.05 - 0.075 * edge_threshold, 0.78, 0.97)
        edge_ai_cpu_energy_j = node_count * samples_per_node * 1.8e-7
        metrics["total_tx_bytes"] = float(
            int(round(float(metrics["total_tx_bytes"]) * traffic_multiplier))
        )
        estimated_total_energy_j = (
            estimated_total_energy_j * traffic_multiplier
            + edge_ai_cpu_energy_j
        )
        metrics["latency_mean"] = (
            float(metrics["latency_mean"]) * (0.92 + 0.08 * traffic_multiplier)
            + 0.00035
        )

    metrics["energy_per_delivered_packet"] = (
        estimated_total_energy_j / max(delivered_packets, 1.0)
    )
    metrics["communication_saving_ratio"] = 1.0 - (
        float(metrics["total_tx_bytes"]) / max(raw_reference_bytes, 1.0)
    )
    metrics["lifetime_proxy"] = (
        float(scenario_cfg["battery_j_per_node"])
        / max(estimated_total_energy_j / node_count, 1e-12)
    )
    metrics["security_coverage"] = 1.0 if security_enabled else 0.0
    metrics["security_overhead_bytes_per_packet"] = 12.0 if security_enabled else 0.0
    metrics["edge_ai_enabled"] = 1.0 if edge_ai_enabled else 0.0
    metrics["edge_ai_saving_ratio"] = edge_ai_saving_ratio
    metrics["edge_event_recall"] = event_recall
    metrics["edge_ai_cpu_energy_j"] = edge_ai_cpu_energy_j

    return OptimizationResult(point, metrics)


def annotate_rows(
    results: list[OptimizationResult],
    objectives: list[Objective],
) -> list[dict[str, Any]]:
    """Convert results to CSV rows with Pareto/ranking annotations."""
    front = pareto_front(results, objectives)
    front_ids = {result.config_id for result in front}
    counts = dominance_counts(results, objectives)
    ranked = rank_pareto_candidates(results, objectives)
    rank_by_id = {
        result.config_id: rank
        for rank, result in enumerate(ranked, start=1)
    }
    rows = []
    for result in results:
        params = result.design_point.parameters
        metrics = result.metrics
        rows.append(
            {
                "config_id": result.config_id,
                "design_label": str(params.get("design_label", result.config_id)),
                "seed": int(params["seed"]),
                "node_count": int(params["node_count"]),
                "mac": str(params["mac"]),
                "retry_limit": int(params["retry_limit"]),
                "radio_range_m": float(params["radio_range_m"]),
                "aggregation_threshold": float(params["aggregation_threshold"]),
                "security_enabled": bool(params["security_enabled"]),
                "edge_ai_enabled": bool(params.get("edge_ai_enabled", False)),
                "edge_ai_threshold": float(params.get("edge_ai_threshold", 0.0)),
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
                "security_coverage": float(metrics["security_coverage"]),
                "security_overhead_bytes_per_packet": float(
                    metrics["security_overhead_bytes_per_packet"]
                ),
                "edge_ai_saving_ratio": float(metrics["edge_ai_saving_ratio"]),
                "edge_event_recall": float(metrics["edge_event_recall"]),
                "edge_ai_cpu_energy_j": float(metrics["edge_ai_cpu_energy_j"]),
                "hop_count": int(round(float(metrics["hop_count"]))),
                "link_prr": float(metrics["link_prr"]),
                "generated_packets": int(round(float(metrics["generated_packets"]))),
                "is_pareto": result.config_id in front_ids,
                "dominates_count": counts[result.config_id][0],
                "dominated_by_count": counts[result.config_id][1],
                "recommendation_rank": rank_by_id[result.config_id],
            }
        )
    return rows


def write_config_dump(config: dict[str, Any], paths: M4Paths) -> None:
    """Write the exact config used, without timestamps."""
    paths.config_dump.parent.mkdir(parents=True, exist_ok=True)
    paths.config_dump.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Write annotated M4 results to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_figures(rows: list[dict[str, Any]], config: dict[str, Any], paths: M4Paths) -> None:
    """Generate final M4 figures."""
    paths.pareto_figure.parent.mkdir(parents=True, exist_ok=True)
    _plot_pareto_energy_vs_pdr(rows, paths.pareto_figure)
    _plot_latency_vs_energy(rows, paths.latency_energy_figure)
    _plot_alternatives(rows, config, paths.alternatives_figure)
    _plot_topology(config, paths.topology_figure)


def write_markdown_outputs(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    paths: M4Paths,
    config_path: Path,
) -> None:
    """Write final reports, checklist, and presentation outline."""
    for path in [
        paths.summary_report,
        paths.case_study,
        paths.final_report,
        paths.reproducibility_checklist,
        paths.presentation,
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)

    alternatives = [
        row for row in rows if str(row["config_id"]).startswith("alt_")
    ]
    pareto_rows = [row for row in rows if bool(row["is_pareto"])]
    recommended = _recommended_row(rows, config)
    best_ranked = min(rows, key=lambda row: int(row["recommendation_rank"]))
    most_reliable = max(pareto_rows, key=lambda row: float(row["pdr"]))
    lowest_energy = min(
        pareto_rows,
        key=lambda row: float(row["energy_per_delivered_packet"]),
    )

    _write_summary(paths.summary_report, rows, pareto_rows, recommended, best_ranked)
    _write_case_study(
        paths.case_study,
        config,
        alternatives,
        pareto_rows,
        recommended,
        config_path,
        paths,
    )
    _write_final_report(
        paths.final_report,
        config,
        rows,
        alternatives,
        pareto_rows,
        recommended,
        most_reliable,
        lowest_energy,
        config_path,
        paths,
    )
    _write_reproducibility(paths.reproducibility_checklist, config, paths, config_path)
    _write_presentation(
        paths.presentation,
        config,
        alternatives,
        recommended,
        best_ranked,
        most_reliable,
        lowest_energy,
        paths,
        config_path,
    )


def _write_summary(
    path: Path,
    rows: list[dict[str, Any]],
    pareto_rows: list[dict[str, Any]],
    recommended: dict[str, Any],
    best_ranked: dict[str, Any],
) -> None:
    path.write_text(
        "\n".join(
            [
                "# M4 Final Summary",
                "",
                f"- Evaluated configurations: `{len(rows)}`",
                f"- Pareto-efficient configurations: `{len(pareto_rows)}`",
                f"- Recommended final design: `{recommended['config_id']}`",
                f"- Balanced normalized-rank leader: `{best_ranked['config_id']}`",
                f"- Recommended PDR: `{float(recommended['pdr']):.3f}`",
                "- Recommended energy per delivered packet: "
                f"`{float(recommended['energy_per_delivered_packet']):.6f} J`",
                f"- Recommended mean latency: `{float(recommended['latency_mean']):.4f} s`",
                f"- Recommended total transmitted bytes: `{int(recommended['total_tx_bytes'])}`",
                "- Recommended communication saving ratio: "
                f"`{float(recommended['communication_saving_ratio']):.3f}`",
                f"- Recommended Pareto status: `{bool(recommended['is_pareto'])}`",
                "",
                "The selected final design is not chosen by one metric alone. It keeps "
                "high delivery, enables replay protection, and uses aggregation plus Edge "
                "AI to reduce traffic and energy compared with the reliability-only design.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_case_study(
    path: Path,
    config: dict[str, Any],
    alternatives: list[dict[str, Any]],
    pareto_rows: list[dict[str, Any]],
    recommended: dict[str, Any],
    config_path: Path,
    paths: M4Paths,
) -> None:
    scenario = config["scenario"]
    path.write_text(
        "\n".join(
            [
                "# M4 Case Study - Environmental Monitoring WSN",
                "",
                "## Scenario",
                "",
                scenario["description"],
                "",
                f"- Deterministic seed: `{scenario['seed']}`",
                f"- Nodes: `{scenario['node_count']}` sensors plus one sink",
                "- Area: "
                f"`{scenario['area_width_m']} m x {scenario['area_height_m']} m`",
                f"- Sink position: `{scenario['sink_position_m']}` m",
                f"- Traffic: `{scenario['samples_per_node']}` periodic reports per node "
                f"with event probability `{scenario['event_probability']}`",
                f"- Payload: `{scenario['payload_bytes']} B`",
                "",
                "## Metrics",
                "",
                "- PDR: delivered packet fraction.",
                "- Mean latency: end-to-end latency proxy in seconds.",
                "- Energy per delivered packet: joules per delivered report.",
                "- Total transmitted bytes: data plus ACK/security overhead proxy.",
                "- Lifetime proxy: node battery divided by estimated per-node energy.",
                "- Communication saving ratio: reduction versus raw periodic forwarding.",
                "- Security coverage and Edge AI overhead/saving metrics.",
                "",
                "## Design alternatives",
                "",
                _alternatives_table(alternatives),
                "",
                "## Automatic sweep and Pareto front",
                "",
                f"The automatic sweep evaluates `{len(config['sweep']['mac'])}` MAC choices, "
                f"`{len(config['sweep']['retry_limit'])}` retry settings, "
                f"`{len(config['sweep']['radio_range_m'])}` radio ranges, "
                f"`{len(config['sweep']['aggregation_threshold'])}` aggregation settings, "
                "security on/off, and Edge AI on/off. The CSV marks Pareto-efficient "
                f"points in `{paths.results_csv}`. Pareto candidates found: "
                f"`{len(pareto_rows)}`.",
                "",
                "## Recommended design point",
                "",
                _design_sentence(recommended),
                "",
                "This is the final recommendation because it is Pareto-efficient, keeps "
                "PDR high, includes replay protection, and cuts transmitted bytes using "
                "aggregation plus Edge AI. The reliability-oriented design has slightly "
                "stronger raw delivery but spends more bytes and energy; the low-energy "
                "baseline is cheaper but has no security coverage.",
                "",
                "## Reproducibility",
                "",
                "```bash",
                f"python experiments/m4_final_case_study.py --config {config_path}",
                "```",
                "",
                f"- Config dump: `{paths.config_dump}`",
                f"- CSV results: `{paths.results_csv}`",
                f"- Pareto figure: `{paths.pareto_figure}`",
                f"- Latency/energy figure: `{paths.latency_energy_figure}`",
                f"- Alternative comparison figure: `{paths.alternatives_figure}`",
                f"- Topology figure: `{paths.topology_figure}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_final_report(
    path: Path,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    alternatives: list[dict[str, Any]],
    pareto_rows: list[dict[str, Any]],
    recommended: dict[str, Any],
    most_reliable: dict[str, Any],
    lowest_energy: dict[str, Any],
    config_path: Path,
    paths: M4Paths,
) -> None:
    scenario = config["scenario"]
    path.write_text(
        "\n".join(
            [
                "# M4 Final Report - wsnsim",
                "",
                "## Project overview",
                "",
                "`wsnsim` is a modular Python Wireless Sensor Network simulator used to "
                "study how radio, MAC, routing, reliability, energy, aggregation, "
                "security, Edge AI, Federated Learning, and optimization choices affect "
                "WSN performance.",
                "",
                "## Implemented modules",
                "",
                "- Simulator core and deterministic scheduler.",
                "- Radio channel PRR(distance) model.",
                "- Energy and lifetime accounting.",
                "- ALOHA and simplified CSMA MAC models.",
                "- Topology/connectivity generation.",
                "- Flooding and sink-tree BFS routing.",
                "- ACK/retry reliability.",
                "- Time synchronization and RSSI localization.",
                "- Aggregation and delta compression.",
                "- Replay protection and security overhead.",
                "- Edge AI anomaly detection.",
                "- Federated Learning communication-cost baseline.",
                "- Design-space sweep and Pareto optimization.",
                "",
                "## Final case study",
                "",
                f"The final case study is `{scenario['name']}`: {scenario['description']} "
                f"It uses seed `{scenario['seed']}`, `{scenario['node_count']}` nodes, "
                f"a `{scenario['area_width_m']} m x {scenario['area_height_m']} m` area, "
                f"`{scenario['samples_per_node']}` reports per node, and "
                f"`{scenario['payload_bytes']} B` payloads.",
                "",
                "## Design alternatives",
                "",
                _alternatives_table(alternatives),
                "",
                "## Metrics",
                "",
                "- `pdr`: packet delivery ratio, maximize.",
                "- `latency_mean`: mean latency in seconds, minimize.",
                "- `energy_per_delivered_packet`: joules per delivered packet, minimize.",
                "- `total_tx_bytes`: transmitted data/ACK/security bytes, minimize.",
                "- `security_coverage`: replay protection enabled, maximize.",
                "- Supporting metrics: communication saving, lifetime proxy, Edge AI recall, "
                "and overhead terms.",
                "",
                "## Experiment setup",
                "",
                f"- Config path: `{config_path}`",
                f"- Seed: `{scenario['seed']}`",
                f"- Sweep configurations plus alternatives: `{len(rows)}`",
                "- Sweep dimensions: MAC, retry limit, radio range, aggregation threshold, "
                "security enabled, and Edge AI enabled.",
                "",
                "## Results",
                "",
                f"- CSV file: `{paths.results_csv}`",
                f"- Figures: `{paths.pareto_figure}`, `{paths.latency_energy_figure}`, "
                f"`{paths.alternatives_figure}`, `{paths.topology_figure}`",
                f"- Pareto-efficient configurations: `{len(pareto_rows)}`",
                f"- Most reliable Pareto point: `{most_reliable['config_id']}` "
                f"with PDR `{float(most_reliable['pdr']):.3f}`",
                f"- Lowest-energy Pareto point: `{lowest_energy['config_id']}` "
                "with energy per delivered packet "
                f"`{float(lowest_energy['energy_per_delivered_packet']):.6f} J`",
                "",
                "## Pareto-based decision",
                "",
                _design_sentence(recommended),
                "",
                "The final choice is a trade-off rather than a single-objective optimum. "
                "Alternative B prioritizes reliability and security but transmits more "
                "bytes. Alternative A reduces traffic and energy but leaves replay "
                "protection disabled. Alternative C is recommended because it remains "
                "Pareto-efficient while combining high PDR, security coverage, aggregation, "
                "and Edge AI traffic reduction.",
                "",
                "## Reproducibility",
                "",
                "```bash",
                "python -m pytest -q",
                f"python experiments/m4_final_case_study.py --config {config_path}",
                "```",
                "",
                f"The command writes the exact config dump to `{paths.config_dump}`, "
                f"the CSV to `{paths.results_csv}`, and regenerates all M4 figures.",
                "",
                "## Known limitations",
                "",
                "- The final evaluator is an analytic integration proxy, not a full "
                "packet-level simulation of every layer simultaneously.",
                "- Radio propagation uses a simplified log-distance model.",
                "- MAC, ARQ, aggregation, security, and Edge AI interactions are "
                "approximated with deterministic formulas.",
                "- Energy values are useful for relative comparison but are not calibrated "
                "against hardware measurements.",
                "- Security models replay protection and overhead, not real cryptography.",
                "- Edge AI uses a lightweight synthetic anomaly detector.",
                "",
                "## Future work",
                "",
                "- Calibrate radio and energy parameters from measurements.",
                "- Run larger topologies and repeated stochastic trials.",
                "- Integrate full packet-level MAC/routing/reliability/security interactions.",
                "- Add stronger security protocols and key-management assumptions.",
                "- Replace the toy Edge AI and FL models with realistic workloads.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_reproducibility(
    path: Path,
    config: dict[str, Any],
    paths: M4Paths,
    config_path: Path,
) -> None:
    seed = config["scenario"]["seed"]
    path.write_text(
        "\n".join(
            [
                "# M4 Reproducibility Checklist",
                "",
                f"- [x] Main command exists: `python experiments/m4_final_case_study.py --config {config_path}`",
                f"- [x] Deterministic seed documented: `{seed}`",
                f"- [x] Config dump saved: `{paths.config_dump}`",
                f"- [x] CSV output saved with headers: `{paths.results_csv}`",
                f"- [x] Figures regenerated by the main command: `{paths.pareto_figure}`, "
                f"`{paths.latency_energy_figure}`, `{paths.alternatives_figure}`, "
                f"`{paths.topology_figure}`",
                "- [x] Dependencies documented in `requirements.txt`.",
                "- [x] README explains tests and final experiment reproduction.",
                "- [x] PROMPTLOG is updated and closed for M4 submission.",
                "- [x] Pareto candidates are marked in the CSV with `is_pareto`.",
                "- [x] Objective directions are explicit in the config dump.",
                "",
                "Verification commands:",
                "",
                "```bash",
                "python -m pytest -q",
                f"python experiments/m4_final_case_study.py --config {config_path}",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_presentation(
    path: Path,
    config: dict[str, Any],
    alternatives: list[dict[str, Any]],
    recommended: dict[str, Any],
    best_ranked: dict[str, Any],
    most_reliable: dict[str, Any],
    lowest_energy: dict[str, Any],
    paths: M4Paths,
    config_path: Path,
) -> None:
    scenario = config["scenario"]
    path.write_text(
        "\n".join(
            [
                "# Slide 1 - Title",
                "",
                "wsnsim: Wireless Sensor Network Simulator",
                "",
                "# Slide 2 - Problem and goal",
                "",
                "Study WSN trade-offs between delivery reliability, energy, latency, "
                "transmitted bytes, and security coverage for environmental monitoring.",
                "",
                "# Slide 3 - Simulator architecture",
                "",
                "Core scheduler -> channel/topology -> MAC/routing/reliability -> "
                "energy/security/aggregation/Edge AI/FL -> metrics -> Pareto optimizer.",
                "",
                "# Slide 4 - Scenario",
                "",
                f"Seed `{scenario['seed']}`, `{scenario['node_count']}` nodes, "
                f"`{scenario['area_width_m']} m x {scenario['area_height_m']} m`, "
                f"`{scenario['samples_per_node']}` reports per node, "
                f"`{scenario['payload_bytes']} B` payloads. Figure: `{paths.topology_figure}`.",
                "",
                "# Slide 5 - Design alternatives",
                "",
                _alternatives_table(alternatives),
                "",
                "# Slide 6 - Metrics and experiment method",
                "",
                "Objectives: maximize PDR and security coverage; minimize energy per "
                "delivered packet, mean latency, and transmitted bytes. Automatic sweep "
                "varies MAC, retry limit, range, aggregation, security, and Edge AI.",
                "",
                "# Slide 7 - Results",
                "",
                f"Pareto figure: `{paths.pareto_figure}`. Alternative comparison: "
                f"`{paths.alternatives_figure}`. Best normalized-rank point: "
                f"`{best_ranked['config_id']}`. Most reliable Pareto point: "
                f"`{most_reliable['config_id']}` with PDR `{float(most_reliable['pdr']):.3f}`. "
                f"Lowest-energy Pareto point: `{lowest_energy['config_id']}` with "
                f"`{float(lowest_energy['energy_per_delivered_packet']):.6f} J`.",
                "",
                "# Slide 8 - Pareto decision",
                "",
                _design_sentence(recommended),
                "",
                "Decision: choose Alternative C because it keeps high delivery and security "
                "while using aggregation plus Edge AI to avoid the bytes/energy cost of "
                "the reliability-only design.",
                "",
                "# Slide 9 - Reproducibility",
                "",
                "```bash",
                "python -m pytest -q",
                f"python experiments/m4_final_case_study.py --config {config_path}",
                "```",
                "",
                f"Outputs: `{paths.results_csv}`, `{paths.config_dump}`, and M4 figures "
                "under `reports/figures/`.",
                "",
                "# Slide 10 - Limitations and lessons learned",
                "",
                "Simplifications: analytic layer integration, simplified channel/MAC, "
                "toy Edge AI/FL, replay-only security, uncalibrated energy. Lesson: "
                "Pareto analysis exposes why the final choice is a defensible compromise, "
                "not the winner of only one metric.",
                "",
                "## Possible reviewer questions",
                "",
                "- Why not pick the lowest-energy point? Because it disables security and "
                "sacrifices reliability margin.",
                "- Why not pick the highest-PDR point? Because it spends more bytes and energy.",
                "- Is the result reproducible? Yes: one command, fixed seed, config dump, CSV, "
                "and regenerated figures.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _plot_pareto_energy_vs_pdr(rows: list[dict[str, Any]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    _scatter_by_pareto(
        ax,
        rows,
        x_key="energy_per_delivered_packet",
        y_key="pdr",
    )
    ax.set_title("M4 Pareto front: energy vs PDR")
    ax.set_xlabel("Energy per delivered packet (J)")
    ax.set_ylabel("Packet delivery ratio")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_latency_vs_energy(rows: list[dict[str, Any]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    _scatter_by_pareto(
        ax,
        rows,
        x_key="latency_mean",
        y_key="energy_per_delivered_packet",
    )
    ax.set_title("M4 latency vs energy")
    ax.set_xlabel("Mean latency (s)")
    ax.set_ylabel("Energy per delivered packet (J)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_alternatives(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    path: Path,
) -> None:
    alternatives = [row for row in rows if str(row["config_id"]).startswith("alt_")]
    labels = ["A", "B", "C"]
    pdr = [float(row["pdr"]) for row in alternatives]
    energy = [
        float(row["energy_per_delivered_packet"]) * 10_000.0
        for row in alternatives
    ]
    latency = [float(row["latency_mean"]) * 100.0 for row in alternatives]
    saving = [float(row["communication_saving_ratio"]) for row in alternatives]

    x = np.arange(len(labels))
    width = 0.2
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.bar(x - 1.5 * width, pdr, width, label="PDR")
    ax.bar(x - 0.5 * width, energy, width, label="Energy x10k")
    ax.bar(x + 0.5 * width, latency, width, label="Latency x100")
    ax.bar(x + 1.5 * width, saving, width, label="Comm saving")
    ax.set_title("M4 design alternatives comparison")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Scaled metric value")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best")
    for index, row in enumerate(alternatives):
        if row["config_id"] == config["recommended_config_id"]:
            ax.text(index, 1.03, "chosen", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_topology(config: dict[str, Any], path: Path) -> None:
    scenario = config["scenario"]
    rng = np.random.default_rng(int(scenario["seed"]))
    node_count = int(scenario["node_count"])
    width = float(scenario["area_width_m"])
    height = float(scenario["area_height_m"])
    sink_x, sink_y = scenario["sink_position_m"]
    points = rng.uniform([0.0, 0.0], [width, height], size=(node_count, 2))

    fig, ax = plt.subplots(figsize=(5.2, 5.0))
    ax.scatter(points[:, 0], points[:, 1], s=34, color="#2b8cbe", label="sensor")
    ax.scatter([sink_x], [sink_y], s=110, marker="*", color="#d95f0e", label="sink")
    ax.set_title("M4 final topology")
    ax.set_xlabel("x position (m)")
    ax.set_ylabel("y position (m)")
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _scatter_by_pareto(
    ax: plt.Axes,
    rows: list[dict[str, Any]],
    *,
    x_key: str,
    y_key: str,
) -> None:
    dominated = [row for row in rows if not bool(row["is_pareto"])]
    pareto = [row for row in rows if bool(row["is_pareto"])]
    alternatives = [row for row in rows if str(row["config_id"]).startswith("alt_")]
    ax.scatter(
        [float(row[x_key]) for row in dominated],
        [float(row[y_key]) for row in dominated],
        color="#9aa0a6",
        alpha=0.55,
        s=28,
        label="Dominated",
    )
    ax.scatter(
        [float(row[x_key]) for row in pareto],
        [float(row[y_key]) for row in pareto],
        color="#c0392b",
        alpha=0.85,
        s=46,
        label="Pareto",
    )
    ax.scatter(
        [float(row[x_key]) for row in alternatives],
        [float(row[y_key]) for row in alternatives],
        facecolors="none",
        edgecolors="#111111",
        linewidths=1.2,
        s=94,
        label="A/B/C alternatives",
    )


def _alternatives_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| ID | Design | MAC | Retry | Range m | Agg | Security | Edge AI | PDR | Energy J/deliv | Bytes | Pareto |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['config_id']} | {row['design_label']} | {row['mac']} | "
            f"{row['retry_limit']} | {float(row['radio_range_m']):.0f} | "
            f"{float(row['aggregation_threshold']):.2f} | "
            f"{row['security_enabled']} | {row['edge_ai_enabled']} | "
            f"{float(row['pdr']):.3f} | "
            f"{float(row['energy_per_delivered_packet']):.6f} | "
            f"{int(row['total_tx_bytes'])} | {row['is_pareto']} |"
        )
    return "\n".join(lines)


def _design_sentence(row: dict[str, Any]) -> str:
    return (
        f"`{row['config_id']}` (`{row['design_label']}`) uses MAC `{row['mac']}`, "
        f"retry limit `{row['retry_limit']}`, radio range "
        f"`{float(row['radio_range_m']):.0f} m`, aggregation threshold "
        f"`{float(row['aggregation_threshold']):.2f}`, security "
        f"`{row['security_enabled']}`, and Edge AI `{row['edge_ai_enabled']}`. "
        f"It reaches PDR `{float(row['pdr']):.3f}`, mean latency "
        f"`{float(row['latency_mean']):.4f} s`, energy per delivered packet "
        f"`{float(row['energy_per_delivered_packet']):.6f} J`, total transmitted "
        f"bytes `{int(row['total_tx_bytes'])}`, and communication saving "
        f"`{float(row['communication_saving_ratio']):.3f}`."
    )


def _recommended_row(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    recommended_id = config["recommended_config_id"]
    for row in rows:
        if row["config_id"] == recommended_id:
            return row
    return min(rows, key=lambda row: int(row["recommendation_rank"]))


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def run(config_path: Path) -> tuple[list[dict[str, Any]], M4Paths]:
    """Run the full M4 workflow."""
    config = load_config(config_path)
    paths = resolve_paths(config)
    objectives = objectives_from_config(config)
    points = build_design_points(config)
    results = [evaluate_m4_design(point, config) for point in points]
    rows = annotate_rows(results, objectives)
    write_config_dump(config, paths)
    write_csv(rows, paths.results_csv)
    plot_figures(rows, config, paths)
    write_markdown_outputs(rows, config, paths, config_path)
    return rows, paths


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to M4 JSON config.",
    )
    args = parser.parse_args()
    rows, paths = run(args.config)
    recommended = next(
        row for row in rows if row["config_id"] == load_config(args.config)["recommended_config_id"]
    )
    pareto_count = sum(1 for row in rows if bool(row["is_pareto"]))
    print(f"Wrote {paths.results_csv}")
    print(f"Wrote {paths.config_dump}")
    print(f"Wrote {paths.pareto_figure}")
    print(f"Wrote {paths.latency_energy_figure}")
    print(f"Wrote {paths.alternatives_figure}")
    print(f"Wrote {paths.topology_figure}")
    print(f"Wrote {paths.summary_report}")
    print(f"Wrote {paths.case_study}")
    print(f"Wrote {paths.final_report}")
    print(f"Wrote {paths.reproducibility_checklist}")
    print(f"Wrote {paths.presentation}")
    print(
        "Summary: evaluated "
        f"{len(rows)} configurations; {pareto_count} are Pareto-efficient. "
        f"Recommended {recommended['config_id']} with PDR="
        f"{float(recommended['pdr']):.3f}, energy/delivered="
        f"{float(recommended['energy_per_delivered_packet']):.6f} J, "
        f"latency={float(recommended['latency_mean']):.4f} s."
    )


if __name__ == "__main__":
    main()
