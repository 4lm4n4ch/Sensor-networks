"""Clock drift and RSSI-based localization models for Week 8."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite, log10
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class ClockConfig:
    """Configuration for one node's local clock.

    ``drift_ppm`` is converted as ``1.0 + drift_ppm * 1e-6``.
    ``offset_s`` is an additive offset in seconds.
    """

    node_id: int
    drift_ppm: float = 0.0
    offset_s: float = 0.0

    @property
    def drift_factor(self) -> float:
        """Return multiplicative drift factor from ppm."""
        return 1.0 + self.drift_ppm * 1e-6

    def __post_init__(self) -> None:
        """Validate the clock mapping is invertible."""
        if self.drift_factor <= 0.0:
            raise ValueError("drift_factor must be positive")


@dataclass(frozen=True)
class TimeSyncResult:
    """Result of a simple one-shot offset synchronization."""

    node_id: int
    sync_true_time_s: float
    raw_local_time_s: float
    reference_time_s: float
    estimated_offset_s: float
    error_before_s: float
    error_after_s: float


@dataclass
class NodeClock:
    """Node-local clock with ppm drift and optional offset correction."""

    config: ClockConfig
    correction_s: float = 0.0

    def local_time(self, true_time_s: float) -> float:
        """Return raw local time for a true simulation time."""
        if true_time_s < 0.0:
            raise ValueError("true_time_s must be non-negative")
        return self.config.offset_s + true_time_s * self.config.drift_factor

    def corrected_local_time(self, true_time_s: float) -> float:
        """Return local time after applying a simple offset correction."""
        return self.local_time(true_time_s) + self.correction_s

    def true_time(self, local_time_s: float) -> float:
        """Invert raw local time back to true time."""
        return (local_time_s - self.config.offset_s) / self.config.drift_factor

    def drift_error_s(self, true_time_s: float) -> float:
        """Return raw local clock error relative to true time."""
        return self.local_time(true_time_s) - true_time_s

    def synchronize_offset(
        self,
        true_time_s: float,
        *,
        reference_time_s: float | None = None,
    ) -> TimeSyncResult:
        """Apply one-shot offset correction against a reference clock.

        This intentionally corrects only the instantaneous offset at
        ``true_time_s``. It does not estimate or remove drift rate.
        """
        reference_s = true_time_s if reference_time_s is None else reference_time_s
        raw_local_s = self.local_time(true_time_s)
        correction_s = reference_s - raw_local_s
        error_before_s = raw_local_s - reference_s
        self.correction_s = correction_s
        error_after_s = self.corrected_local_time(true_time_s) - reference_s
        return TimeSyncResult(
            node_id=self.config.node_id,
            sync_true_time_s=true_time_s,
            raw_local_time_s=raw_local_s,
            reference_time_s=reference_s,
            estimated_offset_s=correction_s,
            error_before_s=error_before_s,
            error_after_s=error_after_s,
        )


@dataclass(frozen=True)
class AnchorNode:
    """Known-position anchor node."""

    id: int
    x_m: float
    y_m: float


@dataclass(frozen=True)
class UnknownNode:
    """Unknown node with a true position used for simulation validation."""

    id: int
    true_x_m: float
    true_y_m: float


@dataclass(frozen=True)
class RSSILocalizationConfig:
    """RSSI path-loss and measurement-noise parameters."""

    tx_power_dbm: float = 0.0
    d0_m: float = 1.0
    path_loss_d0_db: float = 40.0
    path_loss_exponent: float = 2.7
    sigma_db: float = 0.0
    seed: int | None = 42

    def __post_init__(self) -> None:
        """Validate path-loss and noise parameters."""
        if self.d0_m <= 0.0:
            raise ValueError("d0_m must be positive")
        if self.path_loss_exponent <= 0.0:
            raise ValueError("path_loss_exponent must be positive")
        if self.sigma_db < 0.0:
            raise ValueError("sigma_db must be non-negative")


@dataclass(frozen=True)
class RSSIMeasurement:
    """One RSSI measurement from an anchor to an unknown node."""

    anchor_id: int
    rssi_dbm: float
    estimated_distance_m: float


@dataclass(frozen=True)
class LocalizationResult:
    """Result of one 2D localization estimate."""

    estimated_x_m: float | None
    estimated_y_m: float | None
    true_x_m: float
    true_y_m: float
    error_m: float
    success: bool
    reason: str | None = None


class LocalizationError(ValueError):
    """Raised when trilateration cannot produce a reliable estimate."""


def distance_between_points(
    x1_m: float,
    y1_m: float,
    x2_m: float,
    y2_m: float,
) -> float:
    """Return Euclidean distance in meters."""
    return hypot(x2_m - x1_m, y2_m - y1_m)


def distance_between_anchor_and_unknown(
    anchor: AnchorNode,
    unknown: UnknownNode,
) -> float:
    """Return Euclidean anchor-to-unknown distance in meters."""
    return distance_between_points(
        anchor.x_m,
        anchor.y_m,
        unknown.true_x_m,
        unknown.true_y_m,
    )


def rssi_from_distance(
    distance_m: float,
    config: RSSILocalizationConfig | None = None,
    *,
    noise_db: float = 0.0,
) -> float:
    """Return RSSI in dBm from log-distance path loss plus noise."""
    cfg = config if config is not None else RSSILocalizationConfig()
    if distance_m <= 0.0:
        raise ValueError("distance_m must be positive")
    effective_distance_m = max(distance_m, cfg.d0_m)
    path_loss_db = (
        cfg.path_loss_d0_db
        + 10.0
        * cfg.path_loss_exponent
        * log10(effective_distance_m / cfg.d0_m)
    )
    return cfg.tx_power_dbm - path_loss_db + noise_db


def distance_from_rssi(
    rssi_dbm: float,
    config: RSSILocalizationConfig | None = None,
) -> float:
    """Invert log-distance RSSI to an estimated distance in meters."""
    cfg = config if config is not None else RSSILocalizationConfig()
    if not isfinite(rssi_dbm):
        raise ValueError("rssi_dbm must be finite")
    exponent = (
        cfg.tx_power_dbm
        - cfg.path_loss_d0_db
        - rssi_dbm
    ) / (10.0 * cfg.path_loss_exponent)
    estimated_distance_m = cfg.d0_m * (10.0 ** exponent)
    if estimated_distance_m <= 0.0 or not isfinite(estimated_distance_m):
        raise ValueError("estimated distance must be positive and finite")
    return estimated_distance_m


def generate_rssi_measurements(
    anchors: Iterable[AnchorNode],
    unknown: UnknownNode,
    config: RSSILocalizationConfig | None = None,
    *,
    rng: np.random.Generator | None = None,
) -> list[RSSIMeasurement]:
    """Generate deterministic RSSI measurements and inverse distances."""
    cfg = config if config is not None else RSSILocalizationConfig()
    local_rng = rng if rng is not None else np.random.default_rng(cfg.seed)
    measurements: list[RSSIMeasurement] = []
    for anchor in anchors:
        true_distance_m = distance_between_anchor_and_unknown(anchor, unknown)
        safe_distance_m = max(true_distance_m, cfg.d0_m)
        noise_db = (
            0.0
            if cfg.sigma_db == 0.0
            else float(local_rng.normal(0.0, cfg.sigma_db))
        )
        rssi_dbm = rssi_from_distance(safe_distance_m, cfg, noise_db=noise_db)
        measurements.append(
            RSSIMeasurement(
                anchor_id=anchor.id,
                rssi_dbm=rssi_dbm,
                estimated_distance_m=distance_from_rssi(rssi_dbm, cfg),
            )
        )
    return measurements


def trilaterate_2d(
    anchors: Iterable[AnchorNode],
    distances_m: Iterable[float],
    *,
    condition_threshold: float = 1e12,
) -> tuple[float, float]:
    """Estimate a 2D position from anchor coordinates and distances.

    Uses the standard linearized least-squares system formed by subtracting
    the first range equation from all others.
    """
    anchor_list = list(anchors)
    distance_list = [float(distance_m) for distance_m in distances_m]
    if len(anchor_list) != len(distance_list):
        raise LocalizationError("anchors and distances must have the same length")
    if len(anchor_list) < 3:
        raise LocalizationError("at least 3 anchors are required")
    if any(distance_m <= 0.0 for distance_m in distance_list):
        raise LocalizationError("all distances must be positive")

    reference = anchor_list[0]
    reference_distance_m = distance_list[0]
    rows: list[list[float]] = []
    rhs: list[float] = []
    for anchor, distance_m in zip(anchor_list[1:], distance_list[1:]):
        rows.append(
            [
                2.0 * (anchor.x_m - reference.x_m),
                2.0 * (anchor.y_m - reference.y_m),
            ]
        )
        rhs.append(
            reference_distance_m**2
            - distance_m**2
            + anchor.x_m**2
            - reference.x_m**2
            + anchor.y_m**2
            - reference.y_m**2
        )

    matrix = np.asarray(rows, dtype=float)
    vector = np.asarray(rhs, dtype=float)
    rank = np.linalg.matrix_rank(matrix)
    if rank < 2:
        raise LocalizationError("anchor geometry is rank-deficient or collinear")
    condition_number = np.linalg.cond(matrix)
    if not isfinite(condition_number) or condition_number > condition_threshold:
        raise LocalizationError("anchor geometry is ill-conditioned")

    solution, _, _, _ = np.linalg.lstsq(matrix, vector, rcond=None)
    estimated_x_m = float(solution[0])
    estimated_y_m = float(solution[1])
    if not isfinite(estimated_x_m) or not isfinite(estimated_y_m):
        raise LocalizationError("trilateration produced a non-finite estimate")
    return estimated_x_m, estimated_y_m


def localize_from_measurements(
    anchors: Iterable[AnchorNode],
    unknown: UnknownNode,
    measurements: Iterable[RSSIMeasurement],
) -> LocalizationResult:
    """Run trilateration and return a success/failure result object."""
    anchor_by_id = {anchor.id: anchor for anchor in anchors}
    measurement_list = list(measurements)
    try:
        ordered_anchors = [
            anchor_by_id[measurement.anchor_id]
            for measurement in measurement_list
        ]
        estimated_x_m, estimated_y_m = trilaterate_2d(
            ordered_anchors,
            [measurement.estimated_distance_m for measurement in measurement_list],
        )
        error_m = distance_between_points(
            estimated_x_m,
            estimated_y_m,
            unknown.true_x_m,
            unknown.true_y_m,
        )
        return LocalizationResult(
            estimated_x_m=estimated_x_m,
            estimated_y_m=estimated_y_m,
            true_x_m=unknown.true_x_m,
            true_y_m=unknown.true_y_m,
            error_m=error_m,
            success=True,
        )
    except (KeyError, LocalizationError, ValueError) as exc:
        return LocalizationResult(
            estimated_x_m=None,
            estimated_y_m=None,
            true_x_m=unknown.true_x_m,
            true_y_m=unknown.true_y_m,
            error_m=float("inf"),
            success=False,
            reason=str(exc),
        )
