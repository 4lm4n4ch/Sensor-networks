"""Radio channel models for packet delivery estimation."""

from __future__ import annotations

from dataclasses import dataclass
from math import erfc, exp, log10, sqrt

import numpy as np

from wsnsim.core.link import LinkStats


@dataclass(frozen=True)
class ChannelConfig:
    """Configuration for a log-distance radio channel.

    Attributes:
        tx_power_dbm: Transmit power in dBm.
        d0_m: Reference distance in meters.
        path_loss_d0_db: Path loss at the reference distance in dB.
        path_loss_exponent: Log-distance path loss exponent.
        shadowing_sigma_db: Standard deviation of log-normal shadowing in dB.
        noise_floor_dbm: Receiver noise floor in dBm.
        snr_threshold_db: Logistic PRR midpoint in dB.
        transition_width_db: Logistic transition width in dB.
        seed: Seed for the channel-local random number generator.
    """

    tx_power_dbm: float = 0.0
    d0_m: float = 1.0
    path_loss_d0_db: float = 40.0
    path_loss_exponent: float = 2.7
    shadowing_sigma_db: float = 4.0
    noise_floor_dbm: float = -100.0
    snr_threshold_db: float = 10.0
    transition_width_db: float = 2.0
    seed: int | None = 42

    def __post_init__(self) -> None:
        """Validate physical and numerical channel parameters."""
        if self.d0_m <= 0.0:
            raise ValueError("d0_m must be positive")
        if self.path_loss_exponent <= 0.0:
            raise ValueError("path_loss_exponent must be positive")
        if self.shadowing_sigma_db < 0.0:
            raise ValueError("shadowing_sigma_db must be non-negative")
        if self.transition_width_db <= 0.0:
            raise ValueError("transition_width_db must be positive")


class LogDistanceChannel:
    """Log-distance path loss channel with optional shadowing."""

    def __init__(self, config: ChannelConfig):
        """Create a channel with a local, reproducible RNG."""
        self.config = config
        self._rng = np.random.default_rng(config.seed)

    def calculate_link_stats(
        self,
        distance_m: float,
        packet_size_bytes: int,
        *,
        include_shadowing: bool = True,
        shadowing_db: float | None = None,
        include_success: bool = False,
        prr_mode: str = "logistic",
    ) -> LinkStats:
        """Calculate all link metrics for one transmission attempt.

        Shadowing is pinned once per call and reused for every returned metric.
        If ``shadowing_db`` is supplied, it overrides the stochastic draw.
        """
        if distance_m < 0.0:
            raise ValueError("distance_m must not be negative")
        if packet_size_bytes < 0:
            raise ValueError("packet_size_bytes must not be negative")

        pinned_shadowing_db = self._resolve_shadowing_db(
            include_shadowing=include_shadowing,
            shadowing_db=shadowing_db,
        )
        effective_distance_m = max(distance_m, self.config.d0_m)
        path_loss_db = self.path_loss_db_from_shadowing(
            effective_distance_m=effective_distance_m,
            shadowing_db=pinned_shadowing_db,
        )
        rssi_dbm = self.rssi_dbm_from_path_loss(path_loss_db)
        snr_db = self.snr_db_from_rssi(rssi_dbm)
        snr_linear = self.db_to_linear(snr_db)
        prr_logistic = self.logistic_prr_from_snr_db(snr_db)
        ber = self.ber_bpsk_awgn_from_snr_linear(snr_linear)
        prr_ber = self.prr_from_ber(ber, packet_size_bytes)
        per = 1.0 - prr_ber

        success = None
        if include_success:
            prr_value = self._select_prr(prr_mode, prr_logistic, prr_ber)
            success = bool(self._rng.random() < prr_value)

        return LinkStats(
            distance_m=distance_m,
            effective_distance_m=effective_distance_m,
            shadowing_db=pinned_shadowing_db,
            path_loss_db=path_loss_db,
            rssi_dbm=rssi_dbm,
            snr_db=snr_db,
            snr_linear=snr_linear,
            prr_logistic=prr_logistic,
            ber=ber,
            per=per,
            prr_ber=prr_ber,
            success=success,
        )

    def path_loss_db_from_shadowing(
        self,
        *,
        effective_distance_m: float,
        shadowing_db: float,
    ) -> float:
        """Return log-distance path loss in dB for a pinned shadowing value."""
        distance_ratio = effective_distance_m / self.config.d0_m
        return (
            self.config.path_loss_d0_db
            + 10.0 * self.config.path_loss_exponent * log10(distance_ratio)
            + shadowing_db
        )

    def rssi_dbm_from_path_loss(self, path_loss_db: float) -> float:
        """Return RSSI in dBm from path loss in dB."""
        return self.config.tx_power_dbm - path_loss_db

    def snr_db_from_rssi(self, rssi_dbm: float) -> float:
        """Return SNR in dB from RSSI and receiver noise floor."""
        return rssi_dbm - self.config.noise_floor_dbm

    @staticmethod
    def db_to_linear(value_db: float) -> float:
        """Convert a dB value to a linear power ratio."""
        return 10.0 ** (value_db / 10.0)

    def logistic_prr_from_snr_db(self, snr_db: float) -> float:
        """Return logistic packet reception probability from SNR in dB."""
        x = (snr_db - self.config.snr_threshold_db) / self.config.transition_width_db
        if x >= 0.0:
            return 1.0 / (1.0 + exp(-x))
        exp_x = exp(x)
        return exp_x / (1.0 + exp_x)

    @staticmethod
    def ber_bpsk_awgn_from_snr_linear(snr_linear: float) -> float:
        """Return BPSK bit error rate under AWGN from linear SNR."""
        return 0.5 * erfc(sqrt(snr_linear))

    @staticmethod
    def prr_from_ber(ber: float, packet_size_bytes: int) -> float:
        """Return packet reception probability from BER and packet size."""
        packet_bits = packet_size_bytes * 8
        return (1.0 - ber) ** packet_bits

    def _resolve_shadowing_db(
        self,
        *,
        include_shadowing: bool,
        shadowing_db: float | None,
    ) -> float:
        """Return the single shadowing value to use for this transmission."""
        if shadowing_db is not None:
            return shadowing_db
        if not include_shadowing:
            return 0.0
        return float(self._rng.normal(0.0, self.config.shadowing_sigma_db))

    @staticmethod
    def _select_prr(
        prr_mode: str,
        prr_logistic: float,
        prr_ber: float,
    ) -> float:
        """Choose which PRR model controls stochastic success."""
        if prr_mode == "logistic":
            return prr_logistic
        if prr_mode == "ber":
            return prr_ber
        raise ValueError("prr_mode must be 'logistic' or 'ber'")


Channel = LogDistanceChannel
