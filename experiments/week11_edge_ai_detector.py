"""Week 11 experiment: edge AI anomaly detector trade-offs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.edge_ai import (  # noqa: E402
    DetectorConfig,
    EdgeAIMetrics,
    SensorSample,
    SignalGeneratorConfig,
    calculate_edge_ai_metrics,
    detect_samples,
    generate_sensor_samples,
)


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week11_edge_ai_detector.csv"
COMM_FIGURE_PATH = FIGURES_DIR / "week11_comm_saving_vs_threshold.png"
FP_FN_FIGURE_PATH = FIGURES_DIR / "week11_fp_fn_vs_threshold.png"
TRADEOFF_FIGURE_PATH = FIGURES_DIR / "week11_comm_vs_detection_tradeoff.png"
SIGNAL_FIGURE_PATH = FIGURES_DIR / "week11_signal_detection_example.png"
REPORT_PATH = REPORTS_DIR / "week11_edge_ai_report.md"


@dataclass(frozen=True)
class ExperimentScenario:
    """Fixed Week 11 edge anomaly-detection scenario."""

    seed: int = 2026
    n_nodes: int = 25
    n_timesteps: int = 200
    baseline_mean: float = 20.0
    baseline_std: float = 1.0
    anomaly_probability: float = 0.05
    anomaly_magnitude: float = 3.0
    window_size: int = 20
    detector_type: str = "zscore"
    energy_per_packet_j: float = 5.0e-5

    @property
    def signal_config(self) -> SignalGeneratorConfig:
        """Return the signal-generator config for this scenario."""
        return SignalGeneratorConfig(
            seed=self.seed,
            n_nodes=self.n_nodes,
            n_timesteps=self.n_timesteps,
            baseline_mean=self.baseline_mean,
            baseline_std=self.baseline_std,
            anomaly_probability=self.anomaly_probability,
            anomaly_magnitude=self.anomaly_magnitude,
        )

    @property
    def total_samples(self) -> int:
        """Return the number of generated sensor samples."""
        return self.n_nodes * self.n_timesteps


def run_threshold(
    *,
    samples: list[SensorSample],
    scenario: ExperimentScenario,
    threshold: float,
) -> tuple[dict[str, float | int], EdgeAIMetrics]:
    """Run the configured detector for one threshold and return a CSV row."""
    detector_config = DetectorConfig(
        detector_type="zscore",
        threshold=threshold,
        window_size=scenario.window_size,
    )
    results = detect_samples(samples, detector_config)
    metrics = calculate_edge_ai_metrics(
        samples,
        results,
        energy_per_packet_j=scenario.energy_per_packet_j,
    )

    row: dict[str, float | int] = {
        "threshold": threshold,
        "seed": scenario.seed,
        "n_nodes": scenario.n_nodes,
        "n_timesteps": scenario.n_timesteps,
        "anomaly_probability": scenario.anomaly_probability,
        "baseline_packets": metrics.baseline_packets,
        "transmitted_packets": metrics.transmitted_packets,
        "communication_saving_ratio": metrics.communication_saving_ratio,
        "true_positive": metrics.true_positive,
        "false_positive": metrics.false_positive,
        "true_negative": metrics.true_negative,
        "false_negative": metrics.false_negative,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "false_positive_rate": metrics.false_positive_rate,
        "false_negative_rate": metrics.false_negative_rate,
        "energy_saved_j": metrics.energy_saved_j or 0.0,
    }
    return row, metrics


def run_sweep(
    scenario: ExperimentScenario,
    thresholds: list[float],
) -> tuple[list[dict[str, float | int]], list[SensorSample]]:
    """Run the edge AI detector threshold sweep."""
    samples = generate_sensor_samples(scenario.signal_config)
    rows: list[dict[str, float | int]] = []
    for threshold in thresholds:
        row, _ = run_threshold(
            samples=samples,
            scenario=scenario,
            threshold=threshold,
        )
        rows.append(row)
    return rows, samples


def write_csv(rows: list[dict[str, float | int]]) -> None:
    """Write Week 11 edge AI sweep results to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_outputs(
    rows: list[dict[str, float | int]],
    samples: list[SensorSample],
    scenario: ExperimentScenario,
) -> None:
    """Generate the Week 11 communication/detection trade-off figures."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _plot_comm_saving(rows)
    _plot_fp_fn(rows)
    _plot_tradeoff(rows)
    _plot_signal_example(samples, scenario)


def _plot_comm_saving(rows: list[dict[str, float | int]]) -> None:
    """Plot communication saving ratio versus detector threshold."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.plot(
        [float(row["threshold"]) for row in rows],
        [float(row["communication_saving_ratio"]) for row in rows],
        color="#2b6cb0",
        marker="o",
        linewidth=1.8,
    )
    ax.set_title("Week 11 communication saving vs threshold")
    ax.set_xlabel("Detector threshold")
    ax.set_ylabel("Communication saving ratio")
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(COMM_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_fp_fn(rows: list[dict[str, float | int]]) -> None:
    """Plot false-positive and false-negative rates versus threshold."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    thresholds = [float(row["threshold"]) for row in rows]
    ax.plot(
        thresholds,
        [float(row["false_positive_rate"]) for row in rows],
        color="#d95f02",
        marker="s",
        linewidth=1.8,
        label="False positive rate",
    )
    ax.plot(
        thresholds,
        [float(row["false_negative_rate"]) for row in rows],
        color="#4daf4a",
        marker="o",
        linewidth=1.8,
        label="False negative rate",
    )
    ax.set_title("Week 11 FP/FN rates vs threshold")
    ax.set_xlabel("Detector threshold")
    ax.set_ylabel("Rate")
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(FP_FN_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_tradeoff(rows: list[dict[str, float | int]]) -> None:
    """Plot communication saving against missed-anomaly rate."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    x_values = [float(row["false_negative_rate"]) for row in rows]
    y_values = [float(row["communication_saving_ratio"]) for row in rows]
    thresholds = [float(row["threshold"]) for row in rows]
    ax.scatter(
        x_values,
        y_values,
        color="#756bb1",
        s=46,
        zorder=3,
    )
    ax.plot(x_values, y_values, color="#756bb1", alpha=0.55, linewidth=1.4)
    for x_value, y_value, threshold in zip(x_values, y_values, thresholds):
        ax.annotate(
            f"{threshold:g}",
            (x_value, y_value),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=8,
        )
    ax.set_title("Week 11 communication vs detection trade-off")
    ax.set_xlabel("False negative rate")
    ax.set_ylabel("Communication saving ratio")
    ax.set_xlim(left=0.0)
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(TRADEOFF_FIGURE_PATH, dpi=150)
    plt.close(fig)


def _plot_signal_example(
    samples: list[SensorSample],
    scenario: ExperimentScenario,
) -> None:
    """Plot one node's signal with true and detected anomaly markers."""
    detector_config = DetectorConfig(
        detector_type="zscore",
        threshold=2.5,
        window_size=scenario.window_size,
    )
    results = detect_samples(samples, detector_config)
    node_id = 0
    node_pairs = [
        (sample, result)
        for sample, result in zip(samples, results)
        if sample.node_id == node_id
    ]
    node_samples = [pair[0] for pair in node_pairs]
    node_results = [pair[1] for pair in node_pairs]
    timestamps = [sample.timestamp_s for sample in node_samples]
    values = [sample.value for sample in node_samples]
    true_points = [
        (sample.timestamp_s, sample.value)
        for sample in node_samples
        if sample.is_anomaly
    ]
    detected_points = [
        (sample.timestamp_s, sample.value)
        for sample, result in node_pairs
        if result.predicted_anomaly
    ]

    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    ax.plot(
        timestamps,
        values,
        color="#2b6cb0",
        linewidth=1.4,
        label="Sensor value",
    )
    if true_points:
        ax.scatter(
            [point[0] for point in true_points],
            [point[1] for point in true_points],
            color="#e41a1c",
            marker="x",
            s=44,
            label="True anomaly",
            zorder=4,
        )
    if detected_points:
        ax.scatter(
            [point[0] for point in detected_points],
            [point[1] for point in detected_points],
            facecolors="none",
            edgecolors="#4daf4a",
            marker="o",
            s=54,
            linewidths=1.4,
            label="Detected anomaly",
            zorder=3,
        )

    score_ax = ax.twinx()
    score_ax.plot(
        timestamps,
        [min(result.score, 8.0) for result in node_results],
        color="#7f7f7f",
        linewidth=1.0,
        alpha=0.65,
        label="Z-score",
    )
    score_ax.axhline(
        detector_config.threshold,
        color="#7f7f7f",
        linestyle="--",
        linewidth=1.0,
    )
    score_ax.set_ylabel("Z-score")
    score_ax.set_ylim(bottom=0.0)

    ax.set_title("Week 11 example edge detection trace")
    ax.set_xlabel("Time step (s)")
    ax.set_ylabel("Sensor value")
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    score_handles, score_labels = score_ax.get_legend_handles_labels()
    ax.legend(handles + score_handles, labels + score_labels, loc="best")
    fig.tight_layout()
    fig.savefig(SIGNAL_FIGURE_PATH, dpi=150)
    plt.close(fig)


def write_report(
    rows: list[dict[str, float | int]],
    scenario: ExperimentScenario,
) -> None:
    """Write the Week 11 mini report."""
    best_f1_row = max(rows, key=lambda row: float(row["f1"]))
    highest_saving_row = max(
        rows,
        key=lambda row: float(row["communication_saving_ratio"]),
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Week 11: Edge AI Anomaly Detection",
                "",
                "## Question / Hypothesis",
                "",
                "Can simple edge anomaly detection reduce WSN communication by "
                "transmitting only anomaly events while keeping missed anomalies "
                "and false alarms measurable?",
                "",
                "## Scenario and Settings",
                "",
                f"- Seed: `{scenario.seed}`",
                f"- Nodes: `{scenario.n_nodes}`",
                f"- Timesteps: `{scenario.n_timesteps}`",
                f"- Baseline samples: `{scenario.total_samples}`",
                f"- Baseline signal: Gaussian noise around "
                f"`{scenario.baseline_mean}` with std `{scenario.baseline_std}`",
                f"- Anomaly probability: `{scenario.anomaly_probability}`",
                f"- Anomaly magnitude: `{scenario.anomaly_magnitude}`",
                f"- Detector: rolling z-score, window size "
                f"`{scenario.window_size}`",
                "",
                "## Detector Description",
                "",
                "Each node runs a streaming z-score detector against its own "
                "recent history. Baseline forwarding sends every reading to the "
                "sink. Edge AI mode sends only samples classified as anomalies, "
                "so detections are also the communication events.",
                "",
                "## Metrics",
                "",
                "The experiment reports TP, FP, TN, FN, precision, recall, F1, "
                "false-positive rate, false-negative rate, baseline packets, "
                "transmitted packets, communication saving ratio, and a simple "
                "optional packet-energy saving estimate.",
                "",
                "Undefined precision/recall-style metrics are written as `0.0` "
                "when their denominator is empty.",
                "",
                "## Results",
                "",
                f"- Best F1 threshold: `{best_f1_row['threshold']}` with "
                f"F1 `{float(best_f1_row['f1']):.3f}`, saving "
                f"`{float(best_f1_row['communication_saving_ratio']):.3f}`, "
                f"FNR `{float(best_f1_row['false_negative_rate']):.3f}`.",
                f"- Highest saving threshold: `{highest_saving_row['threshold']}` "
                f"with saving "
                f"`{float(highest_saving_row['communication_saving_ratio']):.3f}` "
                f"and FNR "
                f"`{float(highest_saving_row['false_negative_rate']):.3f}`.",
                "",
                "Figures:",
                "",
                f"- `{COMM_FIGURE_PATH}`",
                f"- `{FP_FN_FIGURE_PATH}`",
                f"- `{TRADEOFF_FIGURE_PATH}`",
                f"- `{SIGNAL_FIGURE_PATH}`",
                "",
                "## Interpretation",
                "",
                "Increasing the threshold generally raises communication saving "
                "because fewer samples are transmitted as anomaly events. The "
                "cost is lower sensitivity: false positives tend to fall, while "
                "false negatives can rise as weaker anomalies are filtered out. "
                "The threshold is therefore an explicit WSN trade-off between "
                "battery/network load and event detection quality.",
                "",
                "## Reproducibility",
                "",
                "```bash",
                ".venv/bin/python experiments/week11_edge_ai_detector.py",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    """Run the Week 11 edge AI threshold sweep."""
    scenario = ExperimentScenario()
    thresholds = [1.5, 2.0, 2.5, 3.0, 3.5]
    rows, samples = run_sweep(scenario, thresholds)

    write_csv(rows)
    plot_outputs(rows, samples, scenario)
    write_report(rows, scenario)

    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {COMM_FIGURE_PATH}")
    print(f"Wrote {FP_FN_FIGURE_PATH}")
    print(f"Wrote {TRADEOFF_FIGURE_PATH}")
    print(f"Wrote {SIGNAL_FIGURE_PATH}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
