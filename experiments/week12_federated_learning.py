"""Week 12 experiment: Federated Learning communication trade-offs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.federated import (  # noqa: E402
    FederatedConfig,
    FederatedSimulationResult,
    run_federated_simulation,
)


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week12_federated_learning.csv"
REPORT_PATH = REPORTS_DIR / "week12_federated_learning_report.md"
UPDATE_PERIOD_FIGURE_PATH = FIGURES_DIR / "week12_update_period_vs_comm_cost.png"
CONVERGENCE_FIGURE_PATH = FIGURES_DIR / "week12_rounds_vs_convergence.png"
BASELINE_FIGURE_PATH = FIGURES_DIR / "week12_fl_vs_centralized_comm_cost.png"
ACCURACY_FIGURE_PATH = FIGURES_DIR / "week12_comm_cost_vs_proxy_accuracy.png"


@dataclass(frozen=True)
class ExperimentScenario:
    """Fixed Week 12 FL communication-cost scenario."""

    seed: int = 42069
    n_nodes: int = 25
    model_size_params: int = 8
    rounds: int = 20
    local_steps: int = 2
    participation_rate: float = 1.0
    learning_rate: float = 0.35
    samples_per_node: int = 250
    raw_sample_bytes: int = 16
    bytes_per_param: int = 4
    message_overhead_bytes: int = 16

    def config(
        self,
        *,
        update_period: int,
        rounds: int | None = None,
    ) -> FederatedConfig:
        """Return a Week 12 FL configuration."""
        return FederatedConfig(
            seed=self.seed,
            n_nodes=self.n_nodes,
            model_size_params=self.model_size_params,
            rounds=self.rounds if rounds is None else rounds,
            local_steps=self.local_steps,
            update_period=update_period,
            participation_rate=self.participation_rate,
            learning_rate=self.learning_rate,
            samples_per_node=self.samples_per_node,
            raw_sample_bytes=self.raw_sample_bytes,
            bytes_per_param=self.bytes_per_param,
            message_overhead_bytes=self.message_overhead_bytes,
        )


def result_to_row(
    result: FederatedSimulationResult,
) -> dict[str, int | float]:
    """Convert one FL run into a CSV row."""
    config = result.config
    return {
        "seed": config.seed,
        "n_nodes": config.n_nodes,
        "rounds": config.rounds,
        "update_period": config.update_period,
        "active_rounds": config.active_rounds,
        "participation_rate": config.participation_rate,
        "participating_nodes_per_round": config.participating_nodes_per_round,
        "local_steps": config.local_steps,
        "model_size_params": config.model_size_params,
        "bytes_per_param": config.bytes_per_param,
        "message_overhead_bytes": config.message_overhead_bytes,
        "samples_per_node": config.samples_per_node,
        "raw_sample_bytes": config.raw_sample_bytes,
        "fl_upload_bytes": result.total_fl_upload_bytes,
        "fl_download_bytes": result.total_fl_download_bytes,
        "fl_total_bytes": result.total_fl_bytes,
        "centralized_total_bytes": result.centralized_total_bytes,
        "communication_saving_ratio": result.communication_saving_ratio,
        "distance_to_target": result.distance_to_target,
        "proxy_loss": result.proxy_loss,
        "proxy_accuracy": result.proxy_accuracy,
    }


def run_sweep(
    scenario: ExperimentScenario,
    update_periods: list[int],
) -> list[FederatedSimulationResult]:
    """Run deterministic update-period sweep."""
    return [
        run_federated_simulation(scenario.config(update_period=update_period))
        for update_period in update_periods
    ]


def write_csv(rows: list[dict[str, int | float]]) -> None:
    """Write Week 12 FL sweep results to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_outputs(results: list[FederatedSimulationResult]) -> None:
    """Generate Week 12 communication/convergence figures."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _plot_update_period_vs_comm_cost(results)
    _plot_rounds_vs_convergence(results[0])
    _plot_fl_vs_centralized(results)
    _plot_comm_cost_vs_proxy_accuracy(results)


def _plot_update_period_vs_comm_cost(
    results: list[FederatedSimulationResult],
) -> None:
    """Plot update period versus FL communication cost."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    periods = [result.config.update_period for result in results]
    ax.plot(
        periods,
        [result.total_fl_bytes for result in results],
        color="#2b6cb0",
        marker="o",
        linewidth=1.8,
        label="FL total bytes",
    )
    ax.plot(
        periods,
        [result.centralized_total_bytes for result in results],
        color="#d95f02",
        linestyle="--",
        linewidth=1.5,
        label="Centralized raw upload",
    )
    ax.set_title("Week 12 update period vs communication cost")
    ax.set_xlabel("Update period (rounds between uploads)")
    ax.set_ylabel("Total bytes")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(UPDATE_PERIOD_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_rounds_vs_convergence(result: FederatedSimulationResult) -> None:
    """Plot convergence proxy over rounds for the most frequent update case."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    rounds = [metric.round_index + 1 for metric in result.round_metrics]
    ax.plot(
        rounds,
        [metric.distance_to_target for metric in result.round_metrics],
        color="#4daf4a",
        marker="o",
        linewidth=1.8,
        label="Distance to target",
    )
    ax.set_title("Week 12 rounds vs convergence proxy")
    ax.set_xlabel("FL round")
    ax.set_ylabel("Distance to target")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(CONVERGENCE_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_fl_vs_centralized(results: list[FederatedSimulationResult]) -> None:
    """Plot FL bytes against centralized raw-data upload bytes."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    labels = [f"P={result.config.update_period}" for result in results]
    x_values = list(range(len(results)))
    width = 0.36
    ax.bar(
        [x - width / 2 for x in x_values],
        [result.total_fl_bytes for result in results],
        width=width,
        color="#756bb1",
        label="FL model exchange",
    )
    ax.bar(
        [x + width / 2 for x in x_values],
        [result.centralized_total_bytes for result in results],
        width=width,
        color="#e7298a",
        label="Centralized raw upload",
    )
    ax.set_title("Week 12 FL vs centralized communication cost")
    ax.set_xlabel("Update-period scenario")
    ax.set_ylabel("Total bytes")
    ax.set_xticks(x_values)
    ax.set_xticklabels(labels)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(BASELINE_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_comm_cost_vs_proxy_accuracy(
    results: list[FederatedSimulationResult],
) -> None:
    """Plot communication cost against the bounded proxy accuracy."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.scatter(
        [result.total_fl_bytes for result in results],
        [result.proxy_accuracy for result in results],
        color="#1b9e77",
        s=52,
        zorder=3,
    )
    for result in results:
        ax.annotate(
            f"P={result.config.update_period}",
            (result.total_fl_bytes, result.proxy_accuracy),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=8,
        )
    ax.set_title("Week 12 communication cost vs proxy accuracy")
    ax.set_xlabel("FL total bytes")
    ax.set_ylabel("Proxy accuracy = 1 / (1 + distance)")
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(ACCURACY_FIGURE_PATH, dpi=150)
    plt.close(fig)


def write_report(
    results: list[FederatedSimulationResult],
    scenario: ExperimentScenario,
) -> None:
    """Write the Week 12 Federated Learning mini report."""
    best_accuracy = max(results, key=lambda result: result.proxy_accuracy)
    lowest_comm = min(results, key=lambda result: result.total_fl_bytes)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Week 12 - Federated Learning in WSN",
                "",
                "## Goal",
                "",
                "Federated Learning is relevant for WSNs because sensor nodes "
                "can keep raw measurements local and exchange compact model "
                "updates with a sink or gateway. This Week 12 model focuses on "
                "the communication trade-off: repeated model upload/download "
                "messages versus one centralized upload of all raw samples.",
                "",
                "## Implemented module",
                "",
                "`wsnsim.models.federated` implements `FederatedConfig`, "
                "`FederatedNode`, `FederatedServer`, `fedavg`, "
                "`estimate_fl_comm_bytes`, `estimate_centralized_comm_bytes`, "
                "and `run_federated_simulation`. Nodes hold deterministic local "
                "target vectors, perform simple local movement toward those "
                "targets, and the server aggregates participating model vectors "
                "with sample-weighted FedAvg.",
                "",
                "## Simulation setup",
                "",
                f"- Number of nodes: `{scenario.n_nodes}`",
                f"- Model size: `{scenario.model_size_params}` parameters",
                f"- Rounds: `{scenario.rounds}`",
                f"- Local update rule: `{scenario.local_steps}` steps with "
                f"learning rate `{scenario.learning_rate}` toward local "
                "synthetic statistics",
                "- Update-period sweep: `1, 2, 4, 5` rounds",
                f"- Participation rate: `{scenario.participation_rate}`",
                f"- Deterministic seed: `{scenario.seed}`",
                "",
                "## Communication cost model",
                "",
                "Each FL model message costs:",
                "",
                "```text",
                "message_overhead_bytes + model_size_params * bytes_per_param",
                "```",
                "",
                "For each active communication round, participating nodes "
                "download the global model and upload a local model update. The "
                "centralized baseline uploads all raw samples once:",
                "",
                "```text",
                "n_nodes * samples_per_node * (raw_sample_bytes + overhead)",
                "```",
                "",
                "This is a simplified byte model: it does not simulate packet "
                "loss, MAC contention, routing hops, or compression.",
                "",
                "## Results",
                "",
                f"- CSV path: `{CSV_PATH}`",
                f"- Figure: `{UPDATE_PERIOD_FIGURE_PATH}`",
                f"- Figure: `{CONVERGENCE_FIGURE_PATH}`",
                f"- Figure: `{BASELINE_FIGURE_PATH}`",
                f"- Figure: `{ACCURACY_FIGURE_PATH}`",
                f"- Best proxy accuracy: update period "
                f"`{best_accuracy.config.update_period}` with accuracy "
                f"`{best_accuracy.proxy_accuracy:.3f}` and FL bytes "
                f"`{best_accuracy.total_fl_bytes}`.",
                f"- Lowest FL communication: update period "
                f"`{lowest_comm.config.update_period}` with FL bytes "
                f"`{lowest_comm.total_fl_bytes}` and proxy accuracy "
                f"`{lowest_comm.proxy_accuracy:.3f}`.",
                "",
                "## Interpretation",
                "",
                "FL saves communication when the model exchanged over several "
                "rounds is smaller than the raw sensor history. Increasing the "
                "update period reduces active communication rounds, so byte cost "
                "falls. The remaining cost is repeated model broadcast and model "
                "upload. The proxy convergence metric shows the expected trade-"
                "off: less frequent updates save bytes but usually leave the "
                "global model farther from the synthetic target.",
                "",
                "## Reproducibility",
                "",
                "```bash",
                ".venv/bin/python -m pytest -q tests/test_federated.py",
                ".venv/bin/python experiments/week12_federated_learning.py",
                "```",
                "",
                "## Known limitations",
                "",
                "- Toy numeric model, not a trained neural network.",
                "- Simplified local learning toward synthetic statistics.",
                "- No real privacy guarantee or secure aggregation.",
                "- No wireless contention, routing-hop, or packet-loss model.",
                "- No integration with Week 10 security overhead.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    """Run the Week 12 FL update-period sweep."""
    scenario = ExperimentScenario()
    update_periods = [1, 2, 4, 5]
    results = run_sweep(scenario, update_periods)
    rows = [result_to_row(result) for result in results]

    write_csv(rows)
    plot_outputs(results)
    write_report(results, scenario)

    best_accuracy = max(results, key=lambda result: result.proxy_accuracy)
    lowest_comm = min(results, key=lambda result: result.total_fl_bytes)
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {UPDATE_PERIOD_FIGURE_PATH}")
    print(f"Wrote {CONVERGENCE_FIGURE_PATH}")
    print(f"Wrote {BASELINE_FIGURE_PATH}")
    print(f"Wrote {ACCURACY_FIGURE_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(
        "Summary: best proxy accuracy at update_period="
        f"{best_accuracy.config.update_period} "
        f"({best_accuracy.proxy_accuracy:.3f}); lowest communication at "
        f"update_period={lowest_comm.config.update_period} "
        f"({lowest_comm.total_fl_bytes} B)."
    )


if __name__ == "__main__":
    main()
