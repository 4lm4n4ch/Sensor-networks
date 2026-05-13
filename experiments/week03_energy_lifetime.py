"""Week 3 energy lifetime experiment."""

from __future__ import annotations

import csv
from pathlib import Path
import sys

import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.energy import (
    Battery,
    DutyCycleConfig,
    EnergyModel,
    EnergyState,
    PowerProfile,
)


CSV_PATH = Path("reports/week03_energy_lifetime.csv")
FIGURE_PATH = Path("reports/figures/week03_lifetime_vs_duty_cycle.png")


def build_duty_cycle(active_time_ratio: float, cycle_time_s: float) -> DutyCycleConfig:
    """Create a deterministic duty cycle with TX/RX sharing active time."""
    if not 0.0 <= active_time_ratio <= 1.0:
        raise ValueError("active_time_ratio must be in [0, 1]")

    active_time_s = active_time_ratio * cycle_time_s
    sleep_time_s = cycle_time_s - active_time_s
    return DutyCycleConfig(
        tx_time_s=0.25 * active_time_s,
        rx_time_s=0.50 * active_time_s,
        idle_time_s=0.25 * active_time_s,
        sleep_time_s=sleep_time_s,
    )


def main() -> None:
    """Estimate and plot lifetime for multiple active-time ratios."""
    power_profile = PowerProfile(
        tx_w=0.060,
        rx_w=0.045,
        idle_w=0.010,
        sleep_w=0.0001,
    )
    battery = Battery(capacity_j=10_000.0)
    model = EnergyModel(
        power_profile=power_profile,
        battery=battery,
        current_state=EnergyState.SLEEP,
    )

    active_time_ratios = [0.01, 0.02, 0.05, 0.10, 0.20, 0.40, 0.80]
    cycle_time_s = 10.0
    rows = []

    for active_time_ratio in active_time_ratios:
        duty_cycle = build_duty_cycle(active_time_ratio, cycle_time_s)
        estimate = model.estimate_lifetime(duty_cycle)
        rows.append(
            {
                "active_time_ratio": estimate.active_time_ratio,
                "duty_cycle_percent": estimate.active_time_ratio * 100.0,
                "average_power_w": estimate.average_power_w,
                "lifetime_seconds": estimate.lifetime_seconds,
                "lifetime_hours": estimate.lifetime_hours,
                "lifetime_days": estimate.lifetime_days,
            }
        )

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    ax.plot(
        [row["duty_cycle_percent"] for row in rows],
        [row["lifetime_days"] for row in rows],
        marker="o",
        linewidth=2.0,
    )
    ax.set_title("Week 3 Energy Model: Lifetime vs Duty Cycle")
    ax.set_xlabel("Active-time ratio per cycle (%)")
    ax.set_ylabel("Estimated lifetime (days)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURE_PATH)
    plt.close(fig)

    print(f"Saved {CSV_PATH}")
    print(f"Saved {FIGURE_PATH}")


if __name__ == "__main__":
    main()
