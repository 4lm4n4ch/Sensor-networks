"""Week 8 experiment: clock drift and RSSI localization under noise."""

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

from wsnsim.models.sync_localization import (  # noqa: E402
    AnchorNode,
    ClockConfig,
    NodeClock,
    RSSILocalizationConfig,
    UnknownNode,
    generate_rssi_measurements,
    localize_from_measurements,
)


REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
CSV_PATH = REPORTS_DIR / "week08_localization_error.csv"
DETAILS_CSV_PATH = REPORTS_DIR / "week08_localization_details.csv"
BOXPLOT_FIGURE_PATH = FIGURES_DIR / "week08_localization_error_boxplot.png"
FAILURE_FIGURE_PATH = FIGURES_DIR / "week08_localization_failure_rate.png"
SCATTER_FIGURE_PATH = FIGURES_DIR / "week08_localization_scatter_clean.png"
DRIFT_FIGURE_PATH = FIGURES_DIR / "week08_clock_drift_error.png"


@dataclass(frozen=True)
class ExperimentScenario:
    """Fixed Week 8 localization scenario."""

    seed: int = 2026
    area_width_m: float = 100.0
    area_height_m: float = 100.0
    n_unknown_nodes: int = 80
    scatter_sigma_db: float = 4.0
    scatter_sample_count: int = 12

    @property
    def caption(self) -> str:
        """Return a compact figure caption."""
        return (
            f"seed={self.seed}, area={self.area_width_m:g}x"
            f"{self.area_height_m:g} m, anchors=(0,0),(100,0),(0,100),(100,100), "
            f"unknowns={self.n_unknown_nodes}"
        )


def make_anchors(scenario: ExperimentScenario) -> list[AnchorNode]:
    """Return corner anchors for a rectangular area."""
    return [
        AnchorNode(0, 0.0, 0.0),
        AnchorNode(1, scenario.area_width_m, 0.0),
        AnchorNode(2, 0.0, scenario.area_height_m),
        AnchorNode(3, scenario.area_width_m, scenario.area_height_m),
    ]


def make_unknown_nodes(scenario: ExperimentScenario) -> list[UnknownNode]:
    """Generate deterministic unknown positions inside the area."""
    rng = np.random.default_rng(scenario.seed)
    nodes: list[UnknownNode] = []
    for node_id in range(scenario.n_unknown_nodes):
        nodes.append(
            UnknownNode(
                id=node_id,
                true_x_m=float(rng.uniform(1.0, scenario.area_width_m - 1.0)),
                true_y_m=float(rng.uniform(1.0, scenario.area_height_m - 1.0)),
            )
        )
    return nodes


def run_localization_for_sigma(
    scenario: ExperimentScenario,
    anchors: list[AnchorNode],
    unknown_nodes: list[UnknownNode],
    sigma_db: float,
) -> tuple[dict[str, float | int], list[dict[str, float | int | str | bool]]]:
    """Run all unknown nodes for one RSSI noise sigma."""
    rng = np.random.default_rng(scenario.seed + int(sigma_db * 1000))
    config = RSSILocalizationConfig(
        sigma_db=sigma_db,
        seed=scenario.seed,
        path_loss_exponent=2.7,
    )
    errors_m: list[float] = []
    detail_rows: list[dict[str, float | int | str | bool]] = []
    failed_localizations = 0
    min_valid_m = -scenario.area_width_m
    max_valid_x_m = scenario.area_width_m * 2.0
    max_valid_y_m = scenario.area_height_m * 2.0

    for unknown in unknown_nodes:
        measurements = generate_rssi_measurements(
            anchors,
            unknown,
            config,
            rng=rng,
        )
        result = localize_from_measurements(anchors, unknown, measurements)
        success = result.success
        failure_reason = result.reason or ""
        estimated_x_m = result.estimated_x_m
        estimated_y_m = result.estimated_y_m

        if success and (
            estimated_x_m is None
            or estimated_y_m is None
            or not np.isfinite(estimated_x_m)
            or not np.isfinite(estimated_y_m)
        ):
            success = False
            failure_reason = "non_finite_estimate"

        if success and (
            estimated_x_m < min_valid_m
            or estimated_x_m > max_valid_x_m
            or estimated_y_m < min_valid_m
            or estimated_y_m > max_valid_y_m
        ):
            success = False
            failure_reason = "estimate_outside_bounds"

        if success:
            errors_m.append(result.error_m)
        else:
            failed_localizations += 1
            estimated_x_m = None
            estimated_y_m = None

        detail_rows.append(
            {
                "sigma_db": sigma_db,
                "node_id": unknown.id,
                "true_x_m": unknown.true_x_m,
                "true_y_m": unknown.true_y_m,
                "estimated_x_m": "" if estimated_x_m is None else estimated_x_m,
                "estimated_y_m": "" if estimated_y_m is None else estimated_y_m,
                "error_m": "" if not success else result.error_m,
                "success": success,
                "failure_reason": failure_reason,
            }
        )

    row = {
        "sigma_db": sigma_db,
        "seed": scenario.seed,
        "area_width_m": scenario.area_width_m,
        "area_height_m": scenario.area_height_m,
        "n_unknown_nodes": scenario.n_unknown_nodes,
        "n_anchors": len(anchors),
        "mean_error_m": float(np.mean(errors_m)) if errors_m else float("inf"),
        "median_error_m": float(np.median(errors_m)) if errors_m else float("inf"),
        "p25_error_m": float(np.percentile(errors_m, 25)) if errors_m else float("inf"),
        "p75_error_m": float(np.percentile(errors_m, 75)) if errors_m else float("inf"),
        "p90_error_m": float(np.percentile(errors_m, 90)) if errors_m else float("inf"),
        "max_error_m": float(np.max(errors_m)) if errors_m else float("inf"),
        "failed_localizations": failed_localizations,
        "failure_rate": failed_localizations / scenario.n_unknown_nodes,
    }
    return row, detail_rows


def run_sigma_sweep(
    scenario: ExperimentScenario,
    sigma_values_db: list[float],
) -> tuple[list[dict[str, float | int]], list[AnchorNode], list[dict[str, float | int | str | bool]]]:
    """Run the localization-noise sweep."""
    anchors = make_anchors(scenario)
    unknown_nodes = make_unknown_nodes(scenario)
    rows: list[dict[str, float | int]] = []
    detail_rows: list[dict[str, float | int | str | bool]] = []
    scatter_rows: list[dict[str, float | int | str | bool]] = []

    for sigma_db in sigma_values_db:
        row, sigma_detail_rows = run_localization_for_sigma(
            scenario,
            anchors,
            unknown_nodes,
            sigma_db,
        )
        rows.append(row)
        detail_rows.extend(sigma_detail_rows)
        if sigma_db == scenario.scatter_sigma_db:
            scatter_rows = sigma_detail_rows

    return rows, anchors, detail_rows, scatter_rows


def write_summary_csv(rows: list[dict[str, float | int]]) -> None:
    """Write localization error summary metrics to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_details_csv(rows: list[dict[str, float | int | str | bool]]) -> None:
    """Write detailed per-node localization results to CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with DETAILS_CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_error_boxplot(
    rows: list[dict[str, float | int]],
    details: list[dict[str, float | int | str | bool]],
    scenario: ExperimentScenario,
) -> None:
    """Plot localization error distributions against RSSI noise."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    sigma_values = [float(row["sigma_db"]) for row in rows]
    grouped_errors = []
    for sigma_db in sigma_values:
        grouped_errors.append(
            [
                float(row["error_m"])
                for row in details
                if float(row["sigma_db"]) == sigma_db and bool(row["success"])
            ]
        )

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.boxplot(
        grouped_errors,
        tick_labels=[f"{sigma:g}" for sigma in sigma_values],
        showfliers=True,
        patch_artist=True,
        medianprops={"color": "#1a202c", "linewidth": 1.6},
        boxprops={"facecolor": "#bfdbfe", "edgecolor": "#2b6cb0"},
        whiskerprops={"color": "#2b6cb0"},
        capprops={"color": "#2b6cb0"},
        flierprops={
            "marker": "o",
            "markersize": 3,
            "markerfacecolor": "#c05621",
            "markeredgecolor": "#c05621",
            "alpha": 0.55,
        },
    )
    ax.set_title("Week 8 RSSI localization error distribution")
    ax.set_xlabel("RSSI noise / shadowing sigma (dB)")
    ax.set_ylabel("Localization error (m)")
    ax.grid(True, alpha=0.3)
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
    fig.savefig(BOXPLOT_FIGURE_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_failure_rate(
    rows: list[dict[str, float | int]],
    scenario: ExperimentScenario,
) -> None:
    """Plot failed localization percentage against RSSI noise."""
    sigma_values = [float(row["sigma_db"]) for row in rows]
    failure_percent = [100.0 * float(row["failure_rate"]) for row in rows]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(
        sigma_values,
        failure_percent,
        color="#742a2a",
        marker="o",
        linewidth=1.8,
        markersize=5,
    )
    ax.set_title("Week 8 localization failure rate vs RSSI noise")
    ax.set_xlabel("RSSI noise / shadowing sigma (dB)")
    ax.set_ylabel("Failed localizations (%)")
    ax.set_ylim(0.0, 100.0)
    ax.grid(True, alpha=0.3)
    ax.text(
        0.5,
        -0.24,
        "Failure = invalid solve, non-finite estimate, or estimate outside [-100, 200] m bounds",
        ha="center",
        va="top",
        transform=ax.transAxes,
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(FAILURE_FIGURE_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_localization_scatter(
    anchors: list[AnchorNode],
    scatter_rows: list[dict[str, float | int | str | bool]],
    scenario: ExperimentScenario,
) -> None:
    \"\"\"Plot true and estimated node positions for one noise level.\"\"\"\
    fig, ax = plt.subplots(figsize=(6.5, 6.0))
    anchor_x = [anchor.x_m for anchor in anchors]
    anchor_y = [anchor.y_m for anchor in anchors]
    ax.scatter(anchor_x, anchor_y, marker="^", s=90, color="#1a202c", label="Anchors")

    # All nodes, true position
    true_x_all = [float(row["true_x_m"]) for row in scatter_rows]
    true_y_all = [float(row["true_y_m"]) for row in scatter_rows]
    ax.scatter(true_x_all, true_y_all, s=18, color="#2b6cb0", alpha=0.45, label="True nodes")

    # All nodes, estimated position (only successful ones)
    estimated_x_all = [
        float(row["estimated_x_m"])
        for row in scatter_rows
        if bool(row["success"]) and row["estimated_x_m"] != ""
    ]
    estimated_y_all = [
        float(row["estimated_y_m"])
        for row in scatter_rows
        if bool(row["success"]) and row["estimated_y_m"] != ""
    ]
    ax.scatter(
        estimated_x_all,
        estimated_y_all,
        s=22,
        color="#c05621",
        alpha=0.55,
        label="Estimated nodes",
    )

    # Sampled nodes for error lines
    successful_scatter_rows = [row for row in scatter_rows if bool(row["success"])]
    rng_plot_sample = np.random.default_rng(scenario.seed + 1)  # Distinct RNG for plot sample
    sample_count = min(scenario.scatter_sample_count, len(successful_scatter_rows))
    sample_indices = rng_plot_sample.choice(
        len(successful_scatter_rows), size=sample_count, replace=False
    )
    sampled_nodes_with_errors = [
        successful_scatter_rows[int(idx)] for idx in sample_indices
    ]

    for row in sampled_nodes_with_errors:
        ax.plot(
            [float(row["true_x_m"]), float(row["estimated_x_m"])],
            [float(row["true_y_m"]), float(row["estimated_y_m"])],
            color="#718096",
            linewidth=0.9,
            alpha=0.55,
            zorder=0,  # Ensure lines are behind points
        )
    ax.scatter(
        [float(row["true_x_m"]) for row in sampled_nodes_with_errors],
        [float(row["true_y_m"]) for row in sampled_nodes_with_errors],
        s=34,
        facecolors="none",
        edgecolors="#2b6cb0",
        linewidths=1.0,
        label="Sampled true nodes",
    )
    ax.set_title(f"Week 8 localization example, sigma={scenario.scatter_sigma_db:g} dB")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_xlim(-20, scenario.area_width_m + 20)
    ax.set_ylim(-20, scenario.area_height_m + 20)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(SCATTER_FIGURE_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_clock_drift_error() -> None:
    """Plot clock error over time for representative drift values."""
    true_times_s = np.linspace(0.0, 3600.0, 200)
    drift_values_ppm = [-50.0, 0.0, 50.0, 100.0]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for drift_ppm in drift_values_ppm:
        clock = NodeClock(ClockConfig(node_id=int(drift_ppm), drift_ppm=drift_ppm))
        errors_ms = [
            1000.0 * clock.drift_error_s(float(time_s))
            for time_s in true_times_s
        ]
        ax.plot(true_times_s, errors_ms, linewidth=1.8, label=f"{drift_ppm:g} ppm")

    ax.set_title("Week 8 clock drift error")
    ax.set_xlabel("True time (s)")
    ax.set_ylabel("Clock error (ms)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(DRIFT_FIGURE_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    """Run the Week 8 sync/localization experiment."""
    scenario = ExperimentScenario()
    sigma_values_db = [0, 1, 2, 4, 6, 8]
    rows, anchors, detail_rows, scatter_rows = run_sigma_sweep(
        scenario,
        sigma_values_db,
    )

    write_summary_csv(rows)
    write_details_csv(detail_rows)
    plot_error_boxplot(rows, detail_rows, scenario)
    plot_failure_rate(rows, scenario)
    plot_localization_scatter(anchors, scatter_rows, scenario)
    plot_clock_drift_error()

    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {DETAILS_CSV_PATH}")
    print(f"Wrote {BOXPLOT_FIGURE_PATH}")
    print(f"Wrote {FAILURE_FIGURE_PATH}")
    print(f"Wrote {SCATTER_FIGURE_PATH}")
    print(f"Wrote {DRIFT_FIGURE_PATH}")


if __name__ == "__main__":
    main()
