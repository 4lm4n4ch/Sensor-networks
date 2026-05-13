from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsnsim.models.channel import ChannelConfig, LogDistanceChannel


OUTPUT_PATH = Path("reports/figures/week02_prr_vs_distance.png")


def mean_logistic_prr(
    *,
    distance_m: float,
    sigma_db: float,
    samples: int,
    packet_size_bytes: int,
    seed: int,
) -> float:
    """Estimate mean logistic PRR at one distance under shadowing."""
    config = ChannelConfig(shadowing_sigma_db=sigma_db, seed=seed)
    channel = LogDistanceChannel(config)
    prr_values = [
        channel.calculate_link_stats(
            distance_m,
            packet_size_bytes,
            include_shadowing=sigma_db > 0.0,
        ).prr_logistic
        for _ in range(samples)
    ]
    return float(np.mean(prr_values))


def main() -> None:
    """Sweep distance and save a PRR-vs-distance figure."""
    distances_m = np.linspace(1.0, 150.0, 150)
    packet_size_bytes = 64
    monte_carlo_samples = 400

    curves = {
        "sigma = 0 dB": [
            mean_logistic_prr(
                distance_m=float(distance_m),
                sigma_db=0.0,
                samples=1,
                packet_size_bytes=packet_size_bytes,
                seed=42,
            )
            for distance_m in distances_m
        ],
        "sigma = 4 dB, Monte Carlo mean": [
            mean_logistic_prr(
                distance_m=float(distance_m),
                sigma_db=4.0,
                samples=monte_carlo_samples,
                packet_size_bytes=packet_size_bytes,
                seed=42 + index,
            )
            for index, distance_m in enumerate(distances_m)
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    for label, prr_values in curves.items():
        ax.plot(distances_m, prr_values, label=label, linewidth=2.0)

    ax.set_title("Week 2 Radio Channel: PRR vs Distance")
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("Packet reception probability (0 to 1)")
    ax.set_xlim(1.0, 150.0)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_PATH)
    plt.close(fig)

    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
